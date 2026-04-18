# The 11 Agents

*Generated from `backend/config/agents_registry.yaml` (Agent B, session 3). Edit that file and regenerate — do not hand-edit this doc.*

Digital Humans is a team of 11 AI agents that collectively turn a client's business description into a Salesforce Solution Design Specification (SDS) and then into deployable Salesforce metadata. Each agent has a canonical first-name id (`sophie`, `olivia`, …) and one or more legacy `agent_type` aliases (`pm`, `ba`, …) preserved for backwards compatibility.

All agents are declared in `agents_registry.yaml` and accessed exclusively through `app.services.agents_registry`. Never re-introduce the legacy `AGENT_CONFIG`, `AGENT_COLLECTIONS`, `CATEGORY_AGENT_MAP`, `agent_artifact_needs`, `AGENT_CHAT_PROFILES`, or `AGENT_COSTS` dicts — they are consolidated here.

## Roster

| Id | Name | Role | Tier | Complexity | Cost (USD) | Script |
|----|------|------|------|------------|-----------:|--------|
| `sophie`  | Sophie | Project Manager          | orchestrator | critical | 0.10 | `salesforce_pm.py` |
| `olivia`  | Olivia | Business Analyst         | orchestrator | critical | 0.80 | `salesforce_business_analyst.py` |
| `marcus`  | Marcus | Solution Architect       | orchestrator | critical | 1.20 | `salesforce_solution_architect.py` |
| `emma`    | Emma   | Research Analyst         | orchestrator | complex  | 0.50 | `salesforce_research_analyst.py` |
| `diego`   | Diego  | Apex Developer           | worker       | complex  | 0.60 | `salesforce_developer_apex.py` |
| `zara`    | Zara   | LWC Developer            | worker       | complex  | 0.50 | `salesforce_developer_lwc.py` |
| `raj`     | Raj    | Salesforce Admin         | worker       | complex  | 0.40 | `salesforce_admin.py` |
| `elena`   | Elena  | QA Engineer              | worker       | complex  | 0.50 | `salesforce_qa_tester.py` |
| `jordan`  | Jordan | DevOps / CI-CD           | worker       | complex  | 0.30 | `salesforce_devops.py` |
| `aisha`   | Aisha  | Data Migration           | worker       | complex  | 0.40 | `salesforce_data_migration.py` |
| `lucas`   | Lucas  | Trainer                  | worker       | complex  | 0.30 | `salesforce_trainer.py` |

Tier drives LLM routing (`orchestrator` → Opus-class, `worker` → Sonnet-class; see `ADR-001-llm-strategy.md` and `deployment.md`).

## SDS pipeline

The 6 phases of the SDS generation pipeline, in order:

| Phase | Agent(s) | Mode | Output |
|-------|----------|------|--------|
| 1     | Sophie           | `extract_br` | Business Requirements (user-validated) |
| 2     | Olivia (xN)      | 1 call per BR | Use Cases |
| 2.5   | Emma             | `analyze`     | UC Digest |
| 3     | Marcus (x4)      | `as_is`, `gap`, `design`, `wbs` | Solution Design + WBS |
| 3.3   | Emma             | `validate`    | Coverage Report (triggers Marcus revision if <95%) |
| 4     | Elena, Jordan, Lucas, Aisha | parallel (`PARALLEL_MODE["sds_experts"]`) | Expert specs |
| 5     | Emma             | `write_sds`   | Final SDS markdown (see P9 for sectioned write-up) |
| 6     | —                | `export`      | DOCX via `sds_docx_generator_v3.py` |

## BUILD pipeline

`PhasedBuildExecutor` sequences the BUILD agents in 5 phases (sandbox 2-user limit, `PARALLEL_MODE["build_agents"] = False`):

1. **Foundations** — Raj (permissions, record types, page layouts)
2. **Backend** — Diego (Apex)
3. **Frontend** — Zara (LWC)
4. **Quality** — Elena, Raj (tests + config review)
5. **Deployment** — Jordan, Lucas (CI/CD + adoption material)

## Chat profiles (HITL)

Every agent has `chat.enabled = true` and a French-language `system_prompt` that templated on `{project_name}` is injected at runtime. Sophie also has `always_available = true` — she is the default escalation point when no other agent is in context.

## Change Request routing

`cr_category_overrides` in the YAML maps each CR category to the list of impacted agents (used by `change_request_service.py`):

- `business_rule` → olivia, marcus, diego, raj, elena
- `data_model`    → marcus, diego, aisha, elena
- `process`       → olivia, marcus, raj, elena
- `ui_ux`         → zara, elena
- `integration`   → marcus, diego, jordan
- `security`      → marcus, raj, elena
- `other`         → olivia, marcus

## Adding a 12th agent

1. Add a new block in `agents_registry.yaml` under `agents:` with canonical id, aliases, script file, prompt file, tier, RAG collections, and chat system prompt.
2. Drop the agent script into `backend/agents/roles/`.
3. Write the prompt pack under `backend/prompts/agents/<prompt_file>.yaml`.
4. Regenerate this doc.
5. Run the Agent B contract tests: `pytest tests/session3_regression/agent_b/ -q`.

No code changes to `agents_registry.py` are needed — the registry is YAML-driven.
