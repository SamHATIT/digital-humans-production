# ADR-002 — Agents Registry: Single YAML Source of Truth

- **Status**: Accepted (session 3, 2026-04-18).
- **Author**: Agent B (Contracts), consolidated by Agent D.
- **Supersedes**: six overlapping Python dicts scattered across the backend.
- **Source of truth**: `backend/config/agents_registry.yaml`.
- **Accessor**: `backend/app/services/agents_registry.py` — the only supported way to read agent metadata.

## Context

Agent metadata lived in six places, none of which knew about each other:

1. `AGENT_CONFIG` in `pm_orchestrator_service_v2.py` — name, script, complexity.
2. `AGENT_COLLECTIONS` in `rag_service.py` — RAG collections per agent.
3. `CATEGORY_AGENT_MAP` in `change_request_service.py` — CR category → agents impacted.
4. `agent_artifact_needs` in `artifact_service.py` — artifact types each agent reads.
5. `AGENT_CHAT_PROFILES` in `hitl_routes.py` — HITL chat system prompts.
6. `AGENT_COSTS` in `change_request_service.py` — cost estimates.

Symptoms:

- Renaming `Admin` → `Salesforce Admin` took 6 PRs (one per file).
- Adding the 11th agent (Lucas Trainer) introduced inconsistencies that survived three code reviews: Lucas was in `AGENT_CONFIG` but missing from `AGENT_COLLECTIONS`, so his RAG calls silently hit the default collection.
- CR routing used string agent ids; SDS pipeline used `agent_type` codes; chat used display names. Every service had its own resolver.
- No mechanism to add a 12th agent without touching ≥5 files.

## Decision

**One YAML file** (`backend/config/agents_registry.yaml`) declares every agent. Each entry carries:

```yaml
sophie:                    # canonical id
  name: Sophie             # display name
  role: Project Manager    # English role
  role_fr: Project Manager # French role (for UI)
  agent_type: pm           # legacy agent_type code (kept for back-compat)
  aliases: [pm, pm_orchestrator]
  script: salesforce_pm.py
  prompt_file: sophie_pm
  tier: pm                 # logical tier (orchestrator|worker — ADR-001)
  complexity: critical     # pipeline gating level
  color: purple            # UI badge
  cost_estimate_usd: 0.10
  rag_collections: [business, operations, technical]
  artifact_needs: [requirement, business_req, use_case, adr, spec]
  cr_categories: []
  deliverable_types: []
  chat:
    enabled: true
    always_available: true
    system_prompt: |
      Tu es Sophie, Project Manager …
```

**One Python accessor** — `app.services.agents_registry` exposes:

- `get_agent(id_or_alias) -> AgentSpec` — resolves any alias to the canonical spec.
- `resolve_agent_id(any_name) -> str` — canonicalise ids for comparisons.
- `list_agents() -> list[AgentSpec]` — for UI enumeration.
- `agents_for_cr_category(category) -> list[str]` — used by `change_request_service`.

The accessor loads the YAML once at import time, validates it against a Pydantic schema, and caches in memory.

## Consequences

### Positive

- Adding a 12th agent is a 5-step recipe (see `docs/agents.md` §Adding a 12th agent) — one YAML block plus its script and prompt pack. No service edits.
- Every consumer (`pm_orchestrator_service_v2`, `rag_service`, `change_request_service`, `artifact_service`, `hitl_routes`, `budget_service`) imports from one place — field renames are `grep -w` safe.
- Validation is strict at boot: a missing field, a dangling alias, or an unknown tier raises `ValueError` and prevents start-up.

### Negative

- The YAML is the bottleneck for any agent change — parallel edits need careful merge (one top-level block per agent minimises conflict surface).
- French and English strings live together; separation into two files would complicate lookup. Acceptable given the small corpus.

### Risks

- **Drift back into code**: if future work adds a new agent-adjacent concept (e.g. locale, toolset), there will be a temptation to create a new Python dict rather than extending the YAML. Mitigation: CI check in Agent B's test suite (`tests/session3_regression/agent_b/test_registry_single_source.py`) greps for forbidden dict literal names and fails the build.

## Alternatives considered

1. **One Python module** with a `dataclass` per agent — typed but still Python; harder for non-dev stakeholders to edit.
2. **Per-agent YAML files** (`agents/sophie.yaml`, `agents/olivia.yaml`, …) — better conflict isolation, worse for auditing the full roster in one view. Rejected.
3. **Database table** — runtime-editable but much heavier tooling for something that changes monthly. Rejected.

## Migration notes

- The 6 legacy dicts were removed in PR `refactor(agent-b): consolidate agent contracts into single registry` (commit `3942c96`).
- Tests that referenced the old dicts were rewritten to read from the registry — see `tests/session3_regression/agent_b/`.
- The agent_type codes (`pm`, `ba`, …) remain valid as aliases; no caller code had to change its id literals.

## Links

- `backend/config/agents_registry.yaml` — the registry.
- `backend/app/services/agents_registry.py` — accessor.
- `docs/agents.md` — human-readable agent roster.
- Session 3 audit report §3.2.
