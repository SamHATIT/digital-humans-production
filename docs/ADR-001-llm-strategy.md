# ADR-001 — LLM Strategy: Two Logical Tiers × Three Deployment Profiles

- **Status**: Accepted (session 3, 2026-04-18).
- **Author**: Agent C (LLM Modernization), consolidated by Agent D.
- **Supersedes**: the hardcoded `ANTHROPIC_MODELS`, `OPENAI_MODELS`, and `AGENT_TIER_MAP` dicts previously scattered across `llm_service.py`, `llm_router_service.py` (v1), and `budget_service.py`.
- **Resolves findings**: N21, N22, N23, N28, N31, N33, N35, N41, N42, N43, N45, N86.
- **Source of truth**: `backend/config/llm_routing.yaml`.

## Context

Before session 3 the LLM layer suffered from four compounding issues:

1. **Tier sprawl**: five nominal tiers (`critical`, `complex`, `simple`, `search`, `cheap`) that in practice all mapped to one of two model classes. The extra labels added cognitive cost without buying routing flexibility.
2. **Model ids in code**: `claude-opus-4-6`, `claude-sonnet-4-5-20250929`, and `gpt-4o` were string literals in services. Upgrading a model required a code change, a PR, and a deploy.
3. **Pricing drift**: `budget_service.py` had its own `MODEL_PRICING` dict that drifted from Anthropic's console. Cost reports underestimated spend by ~4× (measured in March 2026).
4. **No on-premise path**: the router hardcoded `anthropic/*` in every branch. Customers asking for airgapped deployments had no route.

## Decision

We adopt **2 logical tiers × 3 deployment profiles**, both expressed in a single YAML file:

### Two tiers

- **orchestrator** — reasoning-heavy synthesis agents: Sophie (PM), Olivia (BA), Marcus (Architect), Emma (Research). These drive the outline of the SDS.
- **worker** — execution agents with longer but less abstract outputs: Diego (Apex), Zara (LWC), Raj (Admin), Elena (QA), Jordan (DevOps), Aisha (Data), Lucas (Trainer).

Mapping is declared once in `agent_tier_map`; legacy agent_type aliases (`pm`, `architect`, …) and display names (`sophie`, `marcus`, …) both resolve.

### Three profiles

| Profile      | Orchestrator             | Worker                       | BUILD | Fallback | Use case |
|--------------|--------------------------|------------------------------|-------|----------|----------|
| `cloud`      | `anthropic/claude-opus`  | `anthropic/claude-sonnet`    | ✅    | Opus → Sonnet → Haiku | Production VPS |
| `on-premise` | `local/mixtral`          | `local/mistral:7b-instruct`  | ✅    | Mixtral → mistral-nemo (**no cloud fallback**) | Airgapped customer |
| `freemium`   | `anthropic/claude-sonnet`| `anthropic/claude-haiku`     | ❌    | Sonnet → Haiku (no-op) | Public demo SaaS |

Selected at boot via `DH_DEPLOYMENT_PROFILE`. The **on-premise** profile has no cloud fallback on purpose — falling back to Anthropic would silently exfiltrate customer data.

### One source of truth for pricing

Every model entry in `pricing:` carries input/output USD-per-1M-token values sourced from the provider console on 2026-04-18. `budget_service.py` reads this at runtime — no separate `MODEL_PRICING` dict.

## Consequences

### Positive

- Upgrading a model (e.g. Claude Opus 4.6 → 4.7) is a YAML edit + service restart, no code change.
- Budget reports match the Anthropic console within ±1 %.
- New deployment variants (e.g. a fourth profile for EU residency) slot in with zero code changes.
- The router honours on-premise no-fallback policy without a feature flag; the YAML encodes the intent.

### Negative

- The YAML grows: ~180 lines at launch and will grow with each new provider. Mitigated by keeping the file flat (no macros, no includes) so it stays greppable.
- Callers that previously asked for a specific tier (`critical`, `cheap`) must migrate to `orchestrator` / `worker`. Agent B's `agents_registry.yaml` already maps every agent → tier; individual service calls migrate as they are touched.

### Risks

- A typo in the YAML (wrong model alias) only surfaces at first call, not at boot. Mitigated by a boot-time validator in `LLMRouterServiceV3.__init__` that resolves every profile × tier combination and refuses to start if any entry is dangling.

## Alternatives considered

1. **Keep 5 tiers, rename models in-place** — cheapest change, but leaves the core "model id in code" problem unsolved. Rejected.
2. **Delegate to LiteLLM** — attractive, but adds an external layer and a translation step for our custom pricing-aware budget logic. Kept as a follow-up if a fourth provider appears.
3. **Separate YAML per profile** — duplication of provider/pricing blocks. Rejected in favour of one file with a `profiles:` section.

## Links

- `backend/config/llm_routing.yaml` — implementation.
- `backend/app/services/llm_router_service.py` — consumer.
- `backend/app/services/budget_service.py` — pricing consumer (C-3).
- `backend/app/api/routes/config.py` — exposes active profile to frontend (C-4).
- `backend/app/middleware/build_enabled.py` — freemium BUILD gate (C-4).
- Session 3 audit report §3.4, §5.1, §5.2.
