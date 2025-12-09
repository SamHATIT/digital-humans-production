# DIGITAL HUMANS - CONTEXTE PROJET

# ╔════════════════════════════════════════════════════════════════════════════╗
# ║                                                                            ║
# ║   ⛔⛔⛔  RÈGLE #1 : JAMAIS DE "DONE" SANS PREUVE DE TEST RÉEL  ⛔⛔⛔    ║
# ║                                                                            ║
# ║   AVANT de marquer une feature DONE :                                      ║
# ║   ┌─────────────────────────────────────────────────────────────────────┐  ║
# ║   │ 1. EXÉCUTER un test réel (UI, curl, ou via l'app)                   │  ║
# ║   │ 2. CAPTURER la preuve (log backend, screenshot, response JSON)      │  ║
# ║   │ 3. COLLER la preuve dans PROGRESS.log                               │  ║
# ║   │ 4. SEULEMENT ALORS marquer DONE dans features.json                  │  ║
# ║   └─────────────────────────────────────────────────────────────────────┘  ║
# ║                                                                            ║
# ║   ❌ "ça compile" ≠ DONE                                                   ║
# ║   ❌ "j'ai écrit le code" ≠ DONE                                           ║
# ║   ❌ "ça devrait marcher" ≠ DONE                                           ║
# ║   ✅ "testé + preuve ci-dessous" = DONE                                    ║
# ║                                                                            ║
# ╚════════════════════════════════════════════════════════════════════════════╝

## Stack Technique
- **Backend**: FastAPI (Python 3.12) - Port 8000
- **Frontend**: React + TypeScript - Port 3000  
- **Database**: PostgreSQL (digital_humans_db) - Service système (pas Docker)
- **Vector DB**: ChromaDB
- **LLM**: Claude Sonnet 4 (Anthropic) / GPT-4 (OpenAI)
- **VPS**: 72.61.161.222

## Les 10 Agents
| Agent | Rôle | Mode SDS | Mode BUILD |
|-------|------|----------|------------|
| Sophie | PM | Extrait BRs | - |
| Olivia | BA | Génère UCs | - |
| Marcus | Architect | As-Is/Gap/Design/WBS | - |
| Diego | Apex Dev | spec | build (génère code) |
| Zara | LWC Dev | spec | build (génère code) |
| Raj | Admin | spec | build (génère config) |
| Elena | QA | spec | test (valide code) |
| Jordan | DevOps | spec | deploy |
| Aisha | Data | spec | build |
| Lucas | Trainer | sds_strategy | - |

## Flow Projet
```
DRAFT → READY → [SDS Phase] → SDS_GENERATED → SDS_IN_REVIEW → SDS_APPROVED → [BUILD Phase] → BUILD_IN_PROGRESS → BUILD_COMPLETED
```

## Fichiers de Suivi (À LIRE EN DÉBUT DE SESSION)
1. `PROGRESS.log` - Journal des sessions (lire les 50 dernières lignes)
2. `features.json` - État des 77 features
3. `CONTEXT.md` - Ce fichier (contexte stable)

## Tables Clés
- `projects` - Projets avec status
- `executions` - Exécutions SDS/BUILD
- `business_requirements` - BRs extraits par Sophie
- `agent_deliverables` - Livrables bruts des agents (JSON)
- `deliverable_items` - Items parsés (UCs)
- `task_executions` - Tâches BUILD avec status

## Chemins Importants
- VPS: `/root/workspace/digital-humans-production`
- Backend: `backend/`
- Frontend: `frontend/`
- Agents: `backend/agents/roles/`
- Services: `backend/app/services/`

## Commandes Utiles
```bash
# Logs backend
docker compose logs backend --tail=50

# Status PostgreSQL
sudo -u postgres psql -d digital_humans_db -c "SELECT ..."

# Restart backend
docker compose restart backend
```
