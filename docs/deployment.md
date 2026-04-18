# Deployment Guide

*Last reviewed: 2026-04-18 (session 3 refonte).*

Digital Humans ships in three deployment profiles that differ in LLM routing and feature surface. Profile selection is driven by a single env var at boot time.

## Profile matrix

| Capability | `cloud` (prod) | `on-premise` | `freemium` |
|---|---|---|---|
| Active env var | `DH_DEPLOYMENT_PROFILE=cloud` (default) | `DH_DEPLOYMENT_PROFILE=on-premise` | `DH_DEPLOYMENT_PROFILE=freemium` |
| Orchestrator tier (Sophie, Olivia, Marcus, Emma) | Anthropic Claude Opus | Ollama Mixtral (local) | Anthropic Claude Sonnet |
| Worker tier (Diego, Zara, Raj, Elena, Jordan, Aisha, Lucas) | Anthropic Claude Sonnet | Ollama Mistral:7b-instruct | Anthropic Claude Haiku |
| Fallback chain | Opus → Sonnet → Haiku | Mixtral → mistral-nemo **no cloud fallback** | Sonnet → Haiku (no-op) |
| BUILD enabled | ✅ | ✅ | ❌ — gated by `BuildEnabledMiddleware` (HTTP 403) |
| Data exfiltration risk | Cloud provider sees data | Zero cloud egress | Cloud provider sees data |
| Est. cost per SDS | ~$5 | $0 | ~$0.50 |

**Important**: the `on-premise` profile has **no cloud fallback chain**. If `local/mixtral` is down, the error bubbles up to the caller — never switches to Anthropic, because that would silently exfiltrate data from an airgapped customer.

The source of truth for this matrix is `backend/config/llm_routing.yaml`. Any change there automatically flows through `LLMRouterServiceV3` without code edits.

## Selecting a profile at boot

```bash
# cloud (default)
export DH_DEPLOYMENT_PROFILE=cloud     # or leave unset

# on-premise
export DH_DEPLOYMENT_PROFILE=on-premise
# Preconditions: Ollama running locally with mixtral + mistral:7b-instruct + mistral-nemo pulled.

# freemium
export DH_DEPLOYMENT_PROFILE=freemium
# BUILD routes will return 403; frontend hides BUILD buttons via /api/config/capabilities.
```

Verify the active profile from the frontend via:

```bash
curl -s http://localhost:8002/api/config/capabilities | jq
# {
#   "profile": "cloud",
#   "build_enabled": true,
#   "llm": {"orchestrator": "anthropic/claude-opus", "worker": "anthropic/claude-sonnet"}
# }
```

## Environment-variable driven paths (D-1)

Every filesystem path is now env-var driven with sensible defaults derived from `__file__`. No more hardcoded `/root/workspace/...` strings. Override any of these as needed:

| Var | Default | Purpose |
|-----|---------|---------|
| `DH_PROJECT_ROOT`       | parent of `backend/`                     | repo root |
| `DH_BACKEND_ROOT`       | `backend/`                               | Python source root |
| `DH_OUTPUT_DIR`         | `backend/outputs`                         | generated SDS/BUILD artefacts |
| `DH_METADATA_DIR`       | `backend/metadata`                        | cached SFDX metadata |
| `DH_CHROMA_PATH`        | `/opt/digital-humans/rag/chromadb_data`   | ChromaDB 70K chunks |
| `DH_RAG_ENV_PATH`       | `/opt/digital-humans/rag/.env`            | RAG service env (OpenAI key) |
| `DH_LLM_CONFIG_PATH`    | `backend/config/llm_routing.yaml`         | LLM routing YAML |
| `DH_SFDX_PROJECT_PATH`  | `/opt/digital-humans/salesforce-workspace/digital-humans-sf` | generated SFDX project |
| `DH_FORCE_APP_PATH`     | `…/force-app/main/default`                | Salesforce metadata target |
| `DH_AGENTS_DIR`         | `/opt/digital-humans/salesforce-agents`   | legacy agent scripts (subprocess) |
| `DH_LOG_FORMAT`         | `json`                                    | `json` or `plain` (D-2 logging) |
| `DH_LOG_LEVEL`          | `INFO`                                    | standard Python log levels |

## Services inventory

| Service       | Port  | Managed by         | Notes |
|---------------|-------|--------------------|-------|
| PostgreSQL 16 | 5432  | systemd            | primary store |
| Nginx         | 80/443 | systemd           | TLS termination + static |
| Ghost CMS     | 2368  | Docker compose     | marketing blog only |
| Backend API   | 8002  | systemd `digital-humans-backend` | FastAPI + uvicorn |
| Frontend      | 3000  | systemd or dev `npm run dev` | React/Vite |
| Ollama        | 11434 | systemd (optional) | required only for `on-premise` |
| ChromaDB      | —     | embedded (`CHROMA_PATH`) | 2.4 GB, 70K chunks |

## First-boot checklist

1. **Secrets** — copy `.env.example` to `/opt/digital-humans/backend/.env` and set at minimum: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY` (for `cloud`/`freemium`), `OPENAI_API_KEY` (for RAG embeddings).
2. **Profile** — set `DH_DEPLOYMENT_PROFILE` in the same env file.
3. **Paths** — leave defaults unless the filesystem layout differs.
4. **DB migrate** — on first boot `Base.metadata.create_all()` runs implicitly; for existing DBs run `alembic upgrade head`.
5. **RAG warmup** — `ChromaDB` loads lazily on the first `/api/pm-orchestrator/*` call; watch `[RAG HEALTH]` log line at boot (added by A-10) to confirm collections are reachable.
6. **Smoke test** — `curl http://localhost:8002/api/health && curl http://localhost:8002/api/config/capabilities`.

## Rollback procedure

- Every sprint is tagged `post-sprint-X`. To roll back a deploy:
  ```bash
  git checkout post-sprint-<N-1>
  sudo systemctl restart digital-humans-backend
  ```
- DB migrations are additive. If a migration must be rolled back, use `alembic downgrade -1` **before** swapping the code.
- For the LLM router, flipping `DH_DEPLOYMENT_PROFILE` requires only a restart; no code change.

## Related docs

- `docs/agents.md` — the 11 agents and their contracts.
- `docs/ADR-001-llm-strategy.md` — why two tiers and three profiles.
- `docs/ADR-002-agents-registry.md` — why a single YAML registry.
- `docs/operations/secrets-rotation.md` — 90-day rotation playbook.
