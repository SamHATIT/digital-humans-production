# BRIEFING AGENT A — Backend Bloquants

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md`
**Branches Claude Code** : `fix/agent-a-*`

---

## 1. Mission

Corriger les **bugs runtime critiques** qui empêchent le BUILD de fonctionner et résoudre les **chantiers architecturaux P0, P7, P11, P12** qui rendent le backend instable.

**Objectif concret** : après ce chantier, une E2E #146 doit pouvoir :
- Démarrer une exécution sans bloquer l'event loop (P0)
- Générer du code BUILD qui passe par une vraie review Elena (pas PASS par défaut)
- Déployer la phase 6 data_migration (actuellement impossible)
- Avoir un RAG qui alerte s'il est vide
- Commit atomiquement les writes budget/CR/artifact

**NON-objectif** : refonte architecturale complète (BaseAgent — briefing dédié futur). Ce briefing vise les fixes bloquants minimum viables pour rétablir le fonctionnement.

---

## 2. Périmètre — fichiers concernés

### Agents (fix F821 + dispatch)
- `backend/agents/roles/salesforce_qa_tester.py` — Elena (829 L)
- `backend/agents/roles/salesforce_data_migration.py` — Aisha (659 L)
- `backend/agents/roles/salesforce_developer_apex.py` — Diego (765 L)
- `backend/agents/roles/salesforce_developer_lwc.py` — Zara (779 L)
- `backend/agents/roles/salesforce_admin.py` — Raj (1 078 L)
- `backend/agents/roles/salesforce_devops.py` — Jordan (514 L)
- `backend/agents/roles/salesforce_trainer.py` — Lucas (610 L)

### Orchestration
- `backend/app/services/phased_build_executor.py` — retrait fail-open (L622-624)
- `backend/app/services/pm_orchestrator_service_v2.py` — F821 imports manquants (L2097, L2350, L2364)
- `backend/app/services/sfdx_service.py` — `import time` manquant

### Services (P7 — transactions)
- `backend/app/services/budget_service.py` — ajouter commit
- `backend/app/services/change_request_service.py` — UnitOfWork pattern
- `backend/app/services/artifact_service.py` — commits granulaires
- `backend/app/services/rag_service.py` — health check + non-silent

### Routes (P0)
- `backend/app/api/routes/orchestrator/execution_routes.py` — priorité absolue
- `backend/app/api/routes/change_requests.py`
- `backend/app/api/routes/projects.py`
- `backend/app/api/routes/orchestrator/sds_v3_routes.py`

---

## 3. Tâches prioritaires

### TASK A-1 — Fix Elena `generate_test` (N17a/b/c) — **BLOCKER**

**Fichier** : `backend/agents/roles/salesforce_qa_tester.py`

**Bug** : 3 F821 cumulés rendent `generate_test` impossible à appeler.

**Patch conceptuel** :

```python
def generate_test(input_data: dict, execution_id: str) -> dict:
    code_files = input_data.get("code_files", input_data.get("files", {}))
    task_info = input_data.get("task", {})
    validation_criteria = input_data.get(
        "validation_criteria",
        task_info.get("validation_criteria", "Code should be functional")
    )

    if not code_files:
        return {"agent_id": "elena", "mode": "test", "success": False,
                "verdict": "FAIL", "feedback": "No code files provided"}

    logger.info(f"Elena TEST mode - reviewing {len(code_files)} file(s)")
    start_time = time.time()

    # === FIX N17c : normaliser validation_criteria AVANT usage ===
    if isinstance(validation_criteria, list):
        criteria_text = "\n".join(f"- {c}" for c in validation_criteria)
    else:
        criteria_text = str(validation_criteria)

    # Build code content
    code_parts = [f"### FILE: {fp}\n```\n{content}\n```" for fp, content in code_files.items()]
    code_content = "\n\n".join(code_parts)

    prompt = PROMPT_SERVICE.render("elena_qa", "code_review", {
        "code_content": code_content[:80000],
        "task_info": json.dumps(task_info, indent=2),
        "validation_criteria": criteria_text,
    })

    # === FIX N17a : initialiser response AVANT de l'utiliser ===
    tokens_used = 0
    input_tokens = 0
    review_text = "{}"
    model_used = "unknown"
    response = {}

    if LLM_SERVICE_AVAILABLE:
        response = generate_llm_response(
            prompt=prompt,
            agent_type="qa_tester",
            max_tokens=4000,
            temperature=0.1,
            execution_id=execution_id,
        )
        review_text = response.get('content', '{}')
        tokens_used = response.get('tokens_used', 0)
        input_tokens = response.get('input_tokens', 0)
        model_used = response.get('model', 'unknown')

    execution_time = round(time.time() - start_time, 2)
    review_data = _parse_review_json(review_text)
    verdict = review_data.get("verdict", "FAIL").upper()  # ← FAIL par défaut si pas parsable

    # === FIX N17b : pas de self dans fonction module-level ===
    # Remplacer getattr(self, '_total_cost', 0.0) par la valeur du response
    cost_usd = response.get('cost_usd', 0.0) if isinstance(response, dict) else 0.0

    return {
        "agent_id": "elena", "agent_name": "Elena (QA Engineer)", "mode": "test",
        "success": verdict == "PASS", "verdict": verdict,
        "task_id": task_info.get("task_id", ""),
        "execution_id": str(execution_id),
        "deliverable_type": "code_validation",
        "content": {"code_review": review_data, "files_reviewed": len(code_files),
                    "total_code_chars": len(code_content)},
        "feedback": review_data.get("feedback_for_developer", "") if verdict == "FAIL" else "",
        "metadata": {
            "execution_time_seconds": execution_time,
            "tokens_used": tokens_used,
            "cost_usd": cost_usd,
            "model": model_used,
        }
    }
```

**Note importante** : le `verdict` par défaut doit passer de `"PASS"` à `"FAIL"` pour ne pas propager un PASS silencieux en cas de parse error.

**DoD** :
- `ruff check --select F821 agents/roles/salesforce_qa_tester.py` → 0 erreur
- Test unitaire : appeler `generate_test({"code_files": {"test.cls": "public class Foo {}"}})` retourne un dict valide avec verdict
- Test unitaire : appeler avec `validation_criteria=""` (str) ne crash pas

---

### TASK A-2 — Fix Elena `QATesterAgent.run()` dispatch (N17d)

**Fichier** : même (L693-703)

**Bug** : `run()` ne dispatche que `mode == "spec"`, retourne `None` silencieux pour `"test"`.

**Patch** :

```python
def run(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    mode = task_data.get("mode", "spec")
    input_content = task_data.get("input_content", "")
    execution_id = task_data.get("execution_id", 0)
    project_id = task_data.get("project_id", 0)

    if mode == "sds_strategy":
        mode = "spec"

    if mode not in self.VALID_MODES:
        return {"success": False, "error": f"Unknown mode: {mode}. Valid: {self.VALID_MODES}"}

    if not input_content:
        return {"success": False, "error": "No input_content provided"}

    try:
        if mode == "spec":
            return self._execute_spec(input_content, execution_id, project_id)
        elif mode == "test":  # ← NEW
            return self._execute_test(input_content, execution_id, project_id)
        else:
            return {"success": False, "error": f"Mode {mode} dispatch missing"}
    except Exception as e:
        logger.error(f"QATesterAgent error in mode '{mode}': {e}", exc_info=True)
        return {"success": False, "error": str(e)}
```

**Pattern identique à appliquer chez** :
- `DataMigrationAgent.run()` → dispatch `"build"` (N18a)
- `DevOpsAgent.run()` → dispatch `"deploy"` (N20a)

---

### TASK A-3 — Fix Aisha `generate_build` module-level (N18b) — **BLOCKER**

**Fichier** : `backend/agents/roles/salesforce_data_migration.py`

**Bug** : `phased_build_executor.py` L487 fait `from agents.roles.salesforce_data_migration import generate_build`. Or cette fonction **n'existe pas** → ImportError silencieusement avalée → Phase 6 morte.

**Solution** : ajouter une fonction module-level qui délègue à `DataMigrationAgent._execute_build` :

```python
# À ajouter à la fin du fichier AVANT le __main__
def generate_build(
    task: dict,
    architecture_context: str,
    execution_id: str,
    rag_context: str = "",
    previous_feedback: str = "",
    solution_design: dict = None,
    gap_context: str = "",
) -> dict:
    """
    Module-level entry point for phased_build_executor compatibility.
    Mirrors the signature of Diego/Zara generate_build functions.
    """
    agent = DataMigrationAgent()
    input_data = {
        "task": task,
        "architecture_context": architecture_context,
        "previous_feedback": previous_feedback,
        "solution_design": solution_design,
        "gap_context": gap_context,
    }
    return agent._execute_build(
        input_content=json.dumps(input_data),
        execution_id=int(execution_id) if str(execution_id).isdigit() else 0,
        project_id=0,
    )
```

**DoD** :
- `grep -n "^def generate_build" agents/roles/salesforce_data_migration.py` → trouve la fonction
- Import test : `python -c "from agents.roles.salesforce_data_migration import generate_build; print(generate_build.__doc__)"`
- Test smoke : phase 6 d'un E2E produit au moins 1 batch (même échec déploiement ok pour ce test)

---

### TASK A-4 — Fix `phased_build_executor` fail-open (Méta-1) — **BLOCKER**

**Fichier** : `backend/app/services/phased_build_executor.py` L622-624

**Bug** :
```python
except Exception as e:
    logger.exception(f"[PhasedBuild] Elena review failed")
    # Default to PASS on error to not block BUILD
    return {"verdict": "PASS", "error": str(e)}  # ← MASQUE les crashes
```

**Patch** :
```python
except Exception as e:
    logger.exception(f"[PhasedBuild] Elena review failed")
    # Previously defaulted to PASS; now FAIL explicitly so BUILD stops
    # on infrastructure issues rather than deploying unreviewed code
    return {
        "verdict": "FAIL",
        "validation_type": "infrastructure_error",
        "issues": [{"severity": "critical", "description": f"Elena review infrastructure failure: {type(e).__name__}"}],
        "feedback_for_developer": f"Elena review could not complete due to infrastructure error: {str(e)[:500]}. BUILD halted until Elena is operational.",
        "error": str(e),
    }
```

**Rationale** : mieux vaut un BUILD qui s'arrête sur erreur visible qu'un BUILD qui déploie silencieusement du code non-validé.

**DoD** :
- Test : injecter une exception dans `generate_test` → vérifier que `execute_phase` retourne success=False
- E2E #146 : si bug Elena persiste, le BUILD doit **échouer visiblement** au lieu de continuer

---

### TASK A-5 — Fix F821 Diego / Zara / Raj

**Fichiers** :
- `salesforce_developer_apex.py` — Diego : L225, L277, L438 (`self` dans fonctions module-level)
- `salesforce_developer_lwc.py` — Zara : L373 (`response` undefined), L450 (`self`)
- `salesforce_admin.py` — Raj : L252, L291, L349, L769 (`self`) + L797 (`model_used`)

**Pattern** : identique à Elena TASK A-1. Les fonctions `generate_build` module-level contiennent des références `self` / `response` qui étaient valides dans la méthode de classe d'origine mais pas en module-level.

**Approche** : pour chaque fonction module-level, relire le corps, identifier les variables référencées avant définition, les initialiser avec valeurs par défaut. Remplacer `getattr(self, '_total_cost', 0.0)` par valeur du `response.get('cost_usd', 0.0)`.

**DoD global** :
```bash
cd backend && . venv/bin/activate
ruff check --select F821 --exclude venv,__pycache__,tests agents/ | wc -l
# Doit être 0 après fix
```

---

### TASK A-6 — Fix F821 services

**Fichiers** :
- `app/services/sfdx_service.py` L796, 798, 860, 862 : ajouter `import time` en tête
- `app/services/pm_orchestrator_service_v2.py` :
  - L1301 : `sf_cfg` — identifier dans le contexte (probablement variable locale oubliée)
  - L2097, L2350 : `ChangeRequest` — ajouter `from app.models.change_request import ChangeRequest`
  - L2364 : `SDSVersion` — ajouter `from app.models.sds_version import SDSVersion`

**DoD** : `ruff check --select F821 app/services/` retourne 0 erreur.

---

### TASK A-7 — P0 `execution_routes.py` (priorité absolue)

**Fichier** : `backend/app/api/routes/orchestrator/execution_routes.py`

**Endpoints P0** : `/execute`, `/execute/{id}/resume`, `/execute/{id}/progress/stream`, `/execute/{id}/result`

**Approche recommandée** : **Option 1 (rapide)** — convertir `async def` en `def` sync. FastAPI les exécutera dans son ThreadPoolExecutor, débloquant l'event loop. Coût : aucun refactor de models, aucun impact fonctionnel.

**Patch type** :
```python
# AVANT
@router.post("/execute")
async def start_execution(
    request: Request,
    execution_data: ExecutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    execution = db.query(Execution).filter(...).first()
    ...

# APRÈS
@router.post("/execute")
def start_execution(  # ← retiré async
    request: Request,
    execution_data: ExecutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    execution = db.query(Execution).filter(...).first()
    ...
```

**Exception** : les endpoints qui font un `await` interne (ex: `stream_execution_progress` avec SSE) doivent rester `async def`. Pour ceux-là, wrapper les `db.query()` :

```python
from asyncio import to_thread as asyncio_to_thread

@router.get("/execute/{execution_id}/progress/stream")
async def stream_execution_progress(
    execution_id: int, token: str = Query(...), db: Session = Depends(get_db),
):
    execution = await asyncio_to_thread(
        lambda: db.query(Execution).filter(Execution.id == execution_id).first()
    )
    ...
```

**DoD** :
- Test de charge : 10 requests parallèles `/execute/{id}/progress` — latence p99 < 500ms
- Stream SSE : reste fonctionnel avec multiple subscribers

---

### TASK A-8 — P0 batch (routes restantes)

Appliquer le même pattern sur :
- `change_requests.py` (9 async def)
- `projects.py` (6 async def)
- `sds_v3_routes.py` (5 async def) — **même si code mort, convertir pour cohérence**
- `business_requirements.py` (8 async def)
- `wizard.py` (10 async def)
- `deployment.py` (10 async def)
- `environments.py` (9 async def)

Pour chaque fichier : ouvrir → lister les endpoints qui font `db.query()` sync → retirer `async` du `def` → vérifier que les `await` internes sont remplacés par appels sync équivalents.

**DoD** :
```bash
# Après le chantier : compter les résiduels
for f in app/api/routes/*.py app/api/routes/orchestrator/*.py; do
  async_count=$(grep -cE "^async def" "$f" 2>/dev/null)
  query_count=$(grep -cE "\bdb\.query\(" "$f" 2>/dev/null)
  if [ "$async_count" -gt 0 ] && [ "$query_count" -gt 0 ]; then
    echo "RESIDUAL: $f async=$async_count query=$query_count"
  fi
done
# Doit retourner 0 lignes (ou uniquement les endpoints SSE avec to_thread wrapping)
```

---

### TASK A-9 — P7 `budget_service.record_cost` commit (N36)

**Fichier** : `backend/app/services/budget_service.py` L112-122

**Bug** : `record_cost` écrit `execution.total_cost` mais **ne commit jamais**, avec docstring "Does NOT commit — caller manages transaction". Or les callers oublient de commit, notamment `llm_service.py` L273-281.

**Patch** :
```python
def record_cost(self, execution_id: int, model: str,
                input_tokens: int, output_tokens: int,
                commit: bool = True) -> float:
    """
    Record cost after an LLM call. Returns the cost in USD.

    Args:
        commit: If True (default), commits immediately. Set False only if
                caller explicitly manages a larger transaction boundary.
    """
    cost = self.estimate_cost(model, input_tokens, output_tokens)
    execution = self.db.query(Execution).get(execution_id)
    if execution:
        execution.total_cost = (execution.total_cost or 0.0) + cost
        execution.total_tokens_used = (
            (execution.total_tokens_used or 0) + input_tokens + output_tokens
        )
        if commit:
            self.db.commit()
    return cost
```

**Même pattern pour** :
- `CircuitBreaker.increment_retry` → ajouter `commit=True` default

**DoD** :
- Test : après un appel LLM, `SELECT total_cost FROM executions WHERE id = ?` retourne > 0
- Log inspection : plus de "cost perdu" sur sessions fermées

---

### TASK A-10 — RAG health check + non-silent (P11, N65, N70)

**Fichier** : `backend/app/services/rag_service.py`

**Fix 1 — Health check au boot** : ajouter au `app/main.py` startup :
```python
from app.services.rag_service import get_stats

@app.on_event("startup")
async def check_rag_health():
    stats = get_stats()
    total = stats.get("total_chunks", 0)
    if total == 0:
        logger.error(
            f"[RAG HEALTH] WARNING: All RAG collections are empty. "
            f"Agents will run without RAG context. "
            f"Run ingestion scripts to populate."
        )
    else:
        logger.info(f"[RAG HEALTH] OK — {total} chunks across {len(stats['collections'])} collections")
```

**Fix 2 — Non-silent sur erreur** : dans `query_collection` L185-187 et `query_rag` L220-222 :
```python
except Exception as e:
    logger.error(f"[RAG ERROR] Collection {coll_key} query failed: {e}", exc_info=True)
    return [], []
```
→ élever le level de WARNING à ERROR + `exc_info=True` pour avoir le stacktrace.

**Fix 3 — Flag dans la réponse agent** : ajouter `"rag_available": bool` dans les return dicts des agents, calculé depuis `len(rag_context) > 0`. Permet au frontend d'afficher un warning si le RAG est down.

---

### TASK A-11 — Hygiene `pm_orchestrator_service_v2.py` imports

**Fichier** : `backend/app/services/pm_orchestrator_service_v2.py`

Ajouter en tête du fichier (section imports) :
```python
from app.models.change_request import ChangeRequest
from app.models.sds_version import SDSVersion
```

Pour `sf_cfg` (L1301) : nécessite lecture contextuelle (~5 lignes autour). Probablement `self.sf_cfg` ou `execution.sf_cfg` — à confirmer par grep dans le fichier.

---

## 4. Plan d'exécution séquentiel

### Sprint 1 (jour 1) — Fix BLOCKERS BUILD
- A-1, A-2, A-3, A-4 → rétablit le BUILD fonctionnel
- **Critère de sortie** : `ruff F821` sur Elena+Aisha = 0, E2E smoke test de phase 6 passe jusqu'au deploy SFDX

### Sprint 2 (jour 1-2) — Fix F821 résiduels
- A-5, A-6 → zéro F821 dans le backend
- **Critère de sortie** : `ruff F821 backend/ --exclude venv,tests` retourne 0

### Sprint 3 (jour 2-3) — P0 async def
- A-7 (execution_routes en priorité)
- A-8 (routes batch)
- **Critère de sortie** : aucun endpoint `async def` + `db.query()` sync restant (sauf SSE wrappés)

### Sprint 4 (jour 3-4) — P7 + P11
- A-9, A-10, A-11
- **Critère de sortie** : cost tracking cohérent (test 10 appels LLM → `total_cost` DB = somme estimée), RAG log ERROR visible si vide

---

## 5. Validation globale — Tests post-merge

```bash
cd /root/workspace/digital-humans-production/backend
. venv/bin/activate

# 1. Aucun F821 résiduel
ruff check --select F821 --exclude venv,__pycache__,tests,migrations . 2>&1 | tee ruff_post.log
[ $(wc -l < ruff_post.log) -eq 0 ] && echo "✅ F821 clean" || echo "❌ F821 resi"

# 2. Dispatch run() tous modes
python -c "
from agents.roles.salesforce_qa_tester import QATesterAgent
r = QATesterAgent().run({'mode':'test', 'input_content':'{\"code_files\":{\"t.cls\":\"public class T{}\"}}'})
assert r is not None, 'run test returned None'
assert 'verdict' in r, 'no verdict'
print('✅ Elena dispatch OK')
"

# 3. generate_build module-level Aisha
python -c "
from agents.roles.salesforce_data_migration import generate_build
print('✅ Aisha generate_build importable')
"

# 4. E2E #146 smoke (à lancer après déploiement)
# curl -X POST http://localhost:8002/api/pm-orchestrator/execute ...
```

---

## 6. Risques & points d'attention

1. **Ordre de merge** : A-1 à A-6 AVANT A-7/A-8. Sinon le fix P0 révèle les F821 masqués par async swallowing.
2. **Régression Elena** : si Elena PASS par défaut devient FAIL par défaut (A-4), les E2E qui étaient "verts" peuvent devenir "rouges" — **c'est attendu et souhaité**. Annoncer dans CHANGELOG.
3. **P0 et SSE** : les endpoints SSE (`/stream`) sont particuliers. Ne PAS les convertir en `def` sync, utiliser `asyncio.to_thread`. Tester stream avec 3+ subscribers parallèles.
4. **budget_service commit** : ajouter `commit=True` par défaut peut provoquer des commits indésirables si un caller l'utilisait dans une transaction plus large. Vérifier les 3 callers actuels (`llm_service`, `llm_router_service`, `change_request_service`).

---

## 7. Livrables attendus

- Code commits atomiques par TASK (un commit par fix)
- CHANGELOG.md mis à jour avec résolution des findings
- Tests unitaires ajoutés pour Elena.generate_test, Aisha.generate_build, phased_build_executor fail-on-exception
- PR description incluant `Resolves N17a, N17b, N17c, N17d, N18a, N18b, ...`
- Capture journalctl montrant "[RAG HEALTH]" au boot

*Fin briefing Agent A*
