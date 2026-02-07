# REFACTOR-ASSIGNMENTS — Digital Humans

> Généré: 2026-02-07 | Agent: Architect Phase 1
> Source: Analyse croisée MODULE-MAP + API-CONTRACTS + DEPENDENCY-GRAPH

---

## Chaîne de dépendances

```
P0 (async→def) ──→ P3 (subprocess→import) ──→ P5 (logging), P6 (LLM Router), P8 (secrets)
                                              ↗
P1 (dead code) ──→ P2 (hardcoded paths) ────

P0 ──→ P4 (fat controller), P7 (transactions), P9 (SDS sections)
```

**Ordre des sprints**: Sprint 0 (P0+P1+P2) → Sprint 1 (P3) → Sprint 2 (P4+P7) → Sprint 3 (validation)

---

## Sprint 0 — Stabilizer (P0 + P1 + P2)

### P0 — Routes async→def (22 conversions)

**Fichier**: `backend/app/api/routes/pm_orchestrator.py`
**Action**: Convertir `async def` → `def` pour 22 routes qui ne font que du sync DB

| # | Fonction | Ligne | Action | Risque |
|---|----------|-------|--------|--------|
| 1 | `create_project` | L39 | `async def` → `def` | Faible |
| 2 | `list_projects` | L78 | `async def` → `def` | Faible |
| 3 | `get_dashboard_stats` | L103 | `async def` → `def` | Faible |
| 4 | `get_project` | L176 | `async def` → `def` | Faible |
| 5 | `update_project` | L199 | `async def` → `def` | Faible |
| 6 | `delete_project` | L232 | `async def` → `def` | Faible |
| 7 | `get_execution_progress` | L422 | `async def` → `def` | Faible |
| 8 | `get_execution_result` | L689 | `async def` → `def` | Faible |
| 9 | `download_sds_document` | L728 | `async def` → `def` | Faible |
| 10 | `list_executions` | L765 | `async def` → `def` | Faible |
| 11 | `list_available_agents` | L802 | `async def` → `def` | Faible |
| 12 | `get_detailed_execution_progress` | L829 | `async def` → `def` | Faible |
| 13 | `get_build_tasks` | L908 | `async def` → `def` | Faible |
| 14 | `get_build_phases` | L988 | `async def` → `def` | Faible |
| 15 | `get_retry_info` | L1400 | `async def` → `def` | Faible |
| 16 | `pause_build` | L1607 | `async def` → `def` | Faible |
| 17 | `resume_build` | L1632 | `async def` → `def` | Faible |
| 18 | `get_requirement_sheets` | L1822 | `async def` → `def` | Faible |
| 19 | `preview_sds_v3` | L1993 | `async def` → `def` | Faible |
| 20 | `get_domains_summary` | L2100 | `async def` → `def` | Faible |
| 21 | `download_sds_v3` | L2298 | `async def` → `def` | Faible |

**Routes à garder `async def`** (10-11 routes):
- `start_execution` (L261) — BackgroundTask
- `resume_execution` (L336) — BackgroundTask
- `stream_execution_progress` (L521) — SSE
- `start_build_phase` (L1070) — BackgroundTask
- `chat_with_pm` (L1116) — async LLM
- `websocket_endpoint` (L1173) — WebSocket
- `retry_failed_execution` (L1308) — BackgroundTask
- `microanalyze_ucs` (L1663) — async LLM
- `synthesize_sds_v3` (L1886) — async LLM
- `generate_sds_docx` (L2155) — async doc gen
- `generate_sds_v3_full_pipeline` (L2355) — full async pipeline

**Risque global**: Faible. FastAPI gère automatiquement les fonctions `def` dans un threadpool. Aucune signature d'appel ne change côté client.

**Tests requis**:
- `pytest tests/ -v` — pas de régression
- `curl -s localhost:8002/api/pm-orchestrator/projects` — réponse 200
- `curl -s localhost:8002/api/pm-orchestrator/agents` — réponse 200
- Vérifier que SSE stream fonctionne toujours

---

### P1 — Dead Code à supprimer

#### Fichiers dead code confirmés

| # | Fichier | Lignes | Raison | Vérification grep |
|---|---------|--------|--------|-------------------|
| 1 | `backend/app/api/routes/pm.py` | 227 | Routes V1 — non monté dans main.py | Seul import: pm_orchestrator_service V1 |
| 2 | `backend/app/services/pm_orchestrator_service.py` | 1499 | Service V1 — remplacé par V2 | Importé uniquement par pm.py (dead) |

**Vérification**: `grep -rn "pm_orchestrator_service[^_v]" backend/ --include="*.py" | grep -v __pycache__` → retourne uniquement `pm.py:9`

#### Fichiers legacy (à migrer avant suppression)

| # | Fichier | Lignes | Importé par | Action |
|---|---------|--------|-------------|--------|
| 1 | `backend/app/services/incremental_executor.py` | 1285 | pm_orchestrator.py:1484, run_build.py:11, tests | Remplacer les refs par PhasedBuildExecutor, puis supprimer |

**Prérequis**: Vérifier que `execute_build_phase()` (L1467-1604 de pm_orchestrator.py) n'est plus appelé par le frontend avant suppression.

#### Fichiers backup à archiver puis supprimer

| # | Fichier | Action |
|---|---------|--------|
| 1 | `backend/app/services/agent_executor_backup_20251207_1345.py` | `git rm` |
| 2 | `backend/app/services/llm_service_backup_20251207_1346.py` | `git rm` |
| 3 | `backend/app/services/rag_service_backup_20251206.py` | `git rm` |
| 4 | `backend/app/services/rag_service_backup_20251207_1344.py` | `git rm` |
| 5 | `backend/Dockerfile.backup-20251211` | `git rm` |

**Procédure**: `git archive` les fichiers backup dans un tar avant suppression si besoin.

#### Routers orphelins (non montés dans main.py)

| # | Fichier | Lignes | Situation |
|---|---------|--------|-----------|
| 1 | `backend/app/api/routes/environments.py` | 283 | Routes existent mais non montées |
| 2 | `backend/app/api/routes/deliverables.py` | 163 | Routes existent mais non montées |
| 3 | `backend/app/api/routes/quality_gates.py` | 153 | Routes existent mais non montées |

**Action**: Vérifier si le frontend les appelle. Si non → dead code. Si oui → monter dans main.py.

---

### P2 — Chemins hardcodés (37+ occurrences)

#### Dans le code principal

| # | Fichier | Ligne | Chemin hardcodé | Remplacement |
|---|---------|-------|-----------------|-------------|
| 1 | `config.py` | L43 | `AGENTS_DIR = "/opt/digital-humans/salesforce-agents"` | env var avec default |
| 2 | `salesforce_config.py` | L19 | `sfdx_project_path = "/root/workspace/salesforce-workspace/..."` | `config.SFDX_PROJECT_PATH` |
| 3 | `salesforce_config.py` | L20 | `force_app_path = "/root/workspace/salesforce-workspace/..."` | `config.FORCE_APP_PATH` |
| 4 | `agent_executor.py` | L78 | `AGENTS_PATH = Path("/root/workspace/.../agents/roles")` | `config.PROJECT_ROOT / "backend/agents/roles"` |
| 5 | `agent_executor.py` | L677 | `env["PYTHONPATH"] = "/root/workspace/.../backend"` | `str(config.PROJECT_ROOT / "backend")` |
| 6 | `agent_executor.py` | L683 | `cwd="/root/workspace/.../backend"` | `str(config.PROJECT_ROOT / "backend")` |
| 7 | `pm_orchestrator_service_v2.py` | L73 | `AGENTS_PATH = Path("/root/workspace/.../agents/roles")` | `config.PROJECT_ROOT / "backend/agents/roles"` |
| 8 | `pm_orchestrator_service_v2.py` | L1644 | `output_dir = "/app/outputs"` | `config.OUTPUT_DIR` |
| 9 | `pm_orchestrator_service_v2.py` | L1680 | `output_dir = "/app/outputs"` | `config.OUTPUT_DIR` |
| 10 | `main.py` | L175 | `filepath = f"/app/outputs/{filename}"` | `config.OUTPUT_DIR / filename` |
| 11 | `rag_service.py` | L44 | `CHROMA_PATH = "/opt/digital-humans/rag/chromadb_data"` | `config.CHROMA_PATH` |
| 12 | `rag_service.py` | L98 | `env_path = "/opt/digital-humans/rag/.env"` | `config.RAG_ENV_PATH` |
| 13 | `llm_router_service.py` | L147 | `Path("/root/workspace/.../config/llm_routing.yaml")` | `config.LLM_CONFIG_PATH` |
| 14 | `sds_template_generator.py` | L28 | `OUTPUT_DIR = "/app/outputs"` | `config.OUTPUT_DIR` |
| 15 | `document_generator.py` | L426 | `output_dir = "/app/outputs"` | `config.OUTPUT_DIR` |
| 16 | `blog.py` | L39 | `script_path = "/root/workspace/.../scripts/blog_generator.py"` | `config.PROJECT_ROOT / "scripts/..."` |
| 17 | `blog.py` | L47 | `cwd="/root/workspace/.../scripts"` | `str(config.PROJECT_ROOT / "scripts")` |
| 18 | `pm_orchestrator.py` | L2330 | `output_dir = f"/app/outputs/sds_v3"` | `config.OUTPUT_DIR / "sds_v3"` |
| 19 | `pm_orchestrator.py` | L2536 | `output_dir = f"/app/outputs/sds_v3"` | `config.OUTPUT_DIR / "sds_v3"` |
| 20 | `metadata_fetcher.py` | L404 | `output_dir = f"/app/metadata/{args.project_id}"` | `config.METADATA_DIR / ...` |
| 21 | `marcus_as_is_v2.py` | L48 | `out_path = f"/app/metadata/{project_id}"` | `config.METADATA_DIR / ...` |

#### Dans les tests (14 occurrences)

| # | Fichier(s) | Pattern | Action |
|---|-----------|---------|--------|
| 1 | `test_emma_phase3.py` (L230, L252, L260, L276) | `sys.path.insert(0, '/root/workspace/...')` | `conftest.py` fixture |
| 2 | `test_wbs_task_types.py` (L16, L156) | idem | idem |
| 3 | `test_wizard_phase5.py` (L15, L136, L143, L219) | idem | idem |
| 4 | `test_emma_write_sds.py` (L17, L130) | idem | idem |
| 5 | `test_sds_workflow_e2e.py` (L548) | idem | idem |
| 6 | `services/test_*.py` (8 fichiers) | `sys.path.insert(0, '/root/workspace/.../backend')` | idem |

#### Dans les agents (1 occurrence)

| # | Fichier | Ligne | Pattern |
|---|---------|-------|---------|
| 1 | `salesforce_research_analyst.py` | L28 | `sys.path.insert(0, "/root/workspace/.../backend")` |

**Note**: Les autres agents utilisent `sys.path.insert(0, "/app")` qui est le path Docker.

#### Constantes à ajouter dans config.py

```python
# Ajouter dans Settings:
PROJECT_ROOT: Path = Path("/root/workspace/digital-humans-production")  # env var
OUTPUT_DIR: Path = Path("/app/outputs")  # env var
CHROMA_PATH: Path = Path("/opt/digital-humans/rag/chromadb_data")  # env var
METADATA_DIR: Path = Path("/app/metadata")  # env var
SFDX_PROJECT_PATH: Path = ...  # env var
LLM_CONFIG_PATH: Path = ...  # env var
```

---

## Sprint 1 — Refactorer (P3 — subprocess→import)

### Ordre de migration (plus simple → plus complexe)

| # | Agent | Fichier | Taille | Modes | Complexité | Raison |
|---|-------|---------|--------|-------|------------|--------|
| 1 | Lucas (Trainer) | `salesforce_trainer.py` | 389L | 2 (sds_strategy, delivery) | Faible | Plus petit, 2 modes simples |
| 2 | Jordan (DevOps) | `salesforce_devops.py` | 280L | 2 (sds_strategy, deploy) | Faible | Petit, logique simple |
| 3 | Sophie (PM) | `salesforce_pm.py` | 429L | 2 (extract_br, consolidate) | Moyen | Core SDS Phase 1 |
| 4 | Olivia (BA) | `salesforce_business_analyst.py` | 414L | 2 (generate_ucs, analyze) | Moyen | Core SDS Phase 2 |
| 5 | Aisha (Data) | `salesforce_data_migration.py` | 435L | 2 (sds_strategy, migrate) | Moyen | SDS Phase 4 expert |
| 6 | Elena (QA) | `salesforce_qa_tester.py` | 595L | 3 (sds_strategy, test, review) | Moyen | SDS Phase 4 + BUILD Quality |
| 7 | Zara (LWC) | `salesforce_developer_lwc.py` | 525L | 2+ (generate, review) | Moyen-Fort | BUILD agent, code gen |
| 8 | Diego (Apex) | `salesforce_developer_apex.py` | 628L | 3+ (generate, test, review) | Fort | BUILD agent, code gen + tests |
| 9 | Raj (Admin) | `salesforce_admin.py` | 887L | 4+ (config, validate, deploy, review) | Fort | BUILD agent, metadata CRUD |
| 10 | Marcus (Architect) | `salesforce_solution_architect.py` | 952L | 4 (as_is, gap, design, wbs) | Fort | SDS Phase 3, 4 appels séquentiels |
| 11 | Emma (Research) | `salesforce_research_analyst.py` | 1259L | 3 (analyze, validate, write_sds) | Très fort | Plus gros, Phase 5 critique |

### Pour chaque agent — Transformation requise

**Pattern actuel** (subprocess):
```python
# agents/roles/salesforce_trainer.py
#!/usr/bin/env python3
import sys, argparse, json
sys.path.insert(0, "/app")
from app.services.llm_service import generate_llm_response

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input-file", required=True)
    args = parser.parse_args()
    with open(args.input_file) as f:
        input_data = json.load(f)
    # ... logique ...
    result = {"success": True, "output": {...}}
    print(json.dumps(result))

if __name__ == "__main__":
    main()
```

**Pattern cible** (importable):
```python
# agents/roles/salesforce_trainer.py
from app.services.llm_service import generate_llm_response

class TrainerAgent:
    """Lucas (Trainer) — SDS Strategy + Delivery"""

    def run(self, task_data: dict) -> dict:
        mode = task_data.get("mode")
        if mode == "sds_strategy":
            return self._sds_strategy(task_data)
        elif mode == "delivery":
            return self._delivery(task_data)
        else:
            return {"success": False, "error": f"Unknown mode: {mode}"}

    def _sds_strategy(self, task_data: dict) -> dict:
        # ... logique existante ...
        return {"success": True, "output": {...}}

    def _delivery(self, task_data: dict) -> dict:
        # ... logique existante ...
        return {"success": True, "output": {...}}

# Rétrocompatibilité subprocess
if __name__ == "__main__":
    import argparse, json, sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input-file", required=True)
    args = parser.parse_args()
    with open(args.input_file) as f:
        input_data = json.load(f)
    input_data["mode"] = args.mode
    agent = TrainerAgent()
    result = agent.run(input_data)
    print(json.dumps(result))
```

### agent_executor.py — Modifications

Pour chaque agent migré, `agent_executor.py` doit:
1. Importer la classe agent
2. Appeler `agent.run(task_data)` directement au lieu de `subprocess.run()`
3. Garder le fallback subprocess pour les agents non encore migrés

**Interface contractuelle** (ne doit PAS changer pour les appelants):
```python
# Signature existante à préserver
async def execute_agent(agent_id: str, task_data: dict, ...) -> dict:
    # Retourne toujours: {"success": bool, "output": dict, "error"?: str}
```

### Risques P3
- **Tests de non-régression** critiques: chaque agent migré doit produire un output identique
- **Imports circulaires**: les agents importent `llm_service` et `rag_service` qui importent `database` → vérifier la chaîne
- **Variables d'environnement**: les agents lisent `os.environ` pour les clés API → s'assurer qu'elles sont dispo dans le process parent

---

## Sprint 2 — Modernizer (P4 + P7)

### P4 — Extraction Fat Controller

**Source**: `backend/app/api/routes/pm_orchestrator.py` (2636 lignes, 36 routes)

**Cible**: <600 lignes par fichier

| Nouveau fichier | Routes extraites | Lignes estimées | Interface |
|----------------|-----------------|-----------------|-----------|
| `routes/sds_execution.py` | Routes SDS: execute, resume, progress, result, download, retry, retry-info | ~500 | `from app.services.pm_orchestrator_service_v2 import ...` |
| `routes/sds_v3.py` | Routes SDS V3: microanalyze, synthesize, preview, domains, generate-docx, download-v3, generate-v3 | ~700 | `from app.services.sds_synthesis_service import ...` |
| `routes/build_execution.py` | Routes BUILD: start-build, build-tasks, build-phases, pause, resume, detailed-progress | ~500 | `from app.services.phased_build_executor import ...` |
| `routes/project_management.py` | Routes CRUD: projects, dashboard/stats, agents | ~300 | `from app.models import ...` |
| `routes/ws_sse.py` | WebSocket + SSE: ws/{id}, progress/stream | ~300 | Async only |
| `routes/pm_orchestrator.py` | Chat + routing vers sous-modules | ~300 | Re-exporte les routers |

**Risques**:
- Le frontend utilise `/api/pm-orchestrator/...` comme préfixe → les paths ne doivent PAS changer
- Les nouveaux fichiers doivent être montés avec le même préfixe dans main.py

### P7 — Transactions atomiques

**Pattern actuel** (trouvé dans 20+ endroits):
```python
db.add(obj)
db.commit()
db.refresh(obj)
```

**Pattern cible**:
```python
with db.begin():
    db.add(obj)
# commit automatique, rollback si exception
```

**Fichiers impactés** (les plus critiques):

| # | Fichier | Lignes impactées | Nombre de commits manuels |
|---|---------|-----------------|--------------------------|
| 1 | `pm_orchestrator.py` (routes) | Multiples | ~15 |
| 2 | `pm_orchestrator_service_v2.py` | Multiples | ~25 |
| 3 | `business_requirements.py` | L117-170, L219-248 | ~5 |
| 4 | `change_requests.py` | L84-128, L203-255 | ~5 |
| 5 | `wizard.py` | L93-160 | ~3 |
| 6 | `projects.py` | L115-175, L221-295 | ~5 |
| 7 | `auth.py` | L17-56 | ~2 |

**Attention**: `database.py` utilise `autocommit=False` → `db.begin()` est compatible.

---

## Sprint 3 — Integrator (Validation)

### Checklist de validation post-refonte

| # | Test | Commande | Critère de succès |
|---|------|---------|------------------|
| 1 | Backend boot | `uvicorn app.main:app` | Pas d'erreur au démarrage |
| 2 | Health check | `curl -s localhost:8002/health` | `{"status": "healthy"}` |
| 3 | API docs | `curl -s localhost:8002/docs` | Page Swagger accessible |
| 4 | Frontend | `curl -s localhost:3000` | HTML retourné |
| 5 | Tests unitaires | `pytest tests/ -v --tb=short` | Même nb de pass qu'avant |
| 6 | Logs propres | `tail -100 /tmp/backend.log \| grep -i error` | Aucune erreur 30s post-boot |
| 7 | SDS workflow | Déclencher une exécution SDS complète | Toutes les phases passent |
| 8 | BUILD workflow | Déclencher un BUILD | Toutes les phases passent |
| 9 | WebSocket | Connecter au WS pendant une exécution | Events reçus |
| 10 | SSE stream | GET /progress/stream pendant exécution | Events streamés |

---

## Contrats d'interface inter-agents

| Interface | Propriétaire | Consommateurs | Contrat — NE PAS CASSER |
|-----------|-------------|---------------|------------------------|
| `agent_executor.execute_agent(agent_id, task_data) → dict` | Refactorer (P3) | pm_orchestrator_service_v2, phased_build_executor | Signature et format retour identiques |
| `AGENT_CONFIG` dict | Refactorer (P3) | agent_executor, pm_orchestrator_service_v2 | Unifier en 1 seul endroit après P3 |
| Routes `pm_orchestrator.py` — paths HTTP | Stabilizer (P0) → Modernizer (P4) | Frontend | Paths inchangés après split |
| `get_db()` session | Modernizer (P7) | Toutes les routes | `db.begin()` compatible avec `autocommit=False` |
| `PMOrchestratorServiceV2.execute_workflow()` | Stabilizer (P0) | pm_orchestrator.py routes | Signature inchangée |
| `PhasedBuildExecutor` | — (pas de modif Sprint 0-1) | pm_orchestrator.py | Interface stable |

### Règle d'or: File Ownership

| Agent | Fichiers propriétaire | INTERDIT de toucher |
|-------|----------------------|-------------------|
| **Stabilizer** | `pm_orchestrator.py` (P0 routes), dead code files, `config.py`, backup files | agents/roles/*, agent_executor.py |
| **Refactorer** | `agents/roles/*.py`, `agent_executor.py` | pm_orchestrator.py routes, config.py |
| **Modernizer** | Nouveaux services extraits de pm_orchestrator.py, transaction patterns | agents/roles/*, agent_executor.py |
| **Integrator** | Tests, scripts de validation | Aucun code de production |

---

## Résumé des métriques

| Sprint | Problèmes | Fichiers modifiés | Fichiers supprimés | Lignes impactées | Risque |
|--------|-----------|------------------|--------------------|-----------------|--------|
| 0 (Stabilizer) | P0, P1, P2 | ~25 | 7 (dead + backup) | ~500 modifs + 3000 supprimées | Faible |
| 1 (Refactorer) | P3 | 12 (11 agents + executor) | 0 | ~8000 refactored | Moyen |
| 2 (Modernizer) | P4, P7 | ~10 (split + transactions) | 0 | ~3000 reorganized | Moyen-Fort |
| 3 (Integrator) | Validation | 0 (lecture seule) | 0 | 0 | Nul |
