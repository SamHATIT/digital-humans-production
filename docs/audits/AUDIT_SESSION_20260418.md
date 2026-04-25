# Audit Digital Humans — Document de Référence

**Date session** : 18 avril 2026
**Modèle** : Claude Opus 4.7 (fenêtre 1M tokens)
**Statut** : Audit en cours — Étape 1 ✅ | Étape 2 🟡 partielle | Étape 3 ⬜ | Étape 4 ⬜
**Objectif** : Audit exhaustif du code + confrontation avec rapports antérieurs avant refonte Agent Teams.

> Ce document sert de **passage de témoin** entre sessions. Il contient tout ce qu'il faut pour reprendre l'audit là où on s'est arrêté, sans perte d'information. À uploader dans Claude Projects.

---

## 1. Méthodologie en 4 étapes

1. **Reconnaissance du repo** (VPS, git status, structure) — ✅ Terminé
2. **Audit statique automatisé** (ruff, grep patterns, tsc) — 🟡 En cours (ruff fait, reste greps + frontend)
3. **Audit sémantique 1M tokens** (contrats inter-agents, keys dict, state machine) — ⬜ À faire
4. **Confrontation rapports antérieurs P0-P10 / H1-H10 vs code réel** — ⬜ À faire

**Livrable final** : rapport Markdown dans `/mnt/user-data/outputs/AUDIT_REPORT_20260418.md` avec 3 sections (écarts doc/code, anomalies nouvelles, priorisation pré-refonte).

---

## 2. État du repo découvert

### Chemins critiques
- **Repo actif** : `/root/workspace/digital-humans-production/`
- **Repo obsolète à ignorer** : `/opt/digital-humans/` (c'est `digital-humans-salesforce`, ancien)
- **Remote** : `git@github.com:SamHATIT/digital-humans-production.git`
- **Branche** : `main` (à jour avec `origin/main`)
- **Python** : 3.12, venv dans `backend/venv/`

### Métriques du repo
| Élément | Compte |
|---------|--------|
| Fichiers Python backend (hors venv/pycache/tests) | 189 |
| Agents (dans `backend/agents/`) | 13 |
| Services (dans `app/services/`) | 44 |
| Routes (dans `app/api/routes/`) | 32 |
| Modèles SQLAlchemy (dans `app/models/`) | 30 |
| YAML prompts (dans `backend/prompts/`) | 11 |
| Fichiers frontend .ts/.tsx | 40 |
| **LOC total backend (hors venv)** | **50 758** |

### Derniers commits importants (post-CHANGELOG du 14 février)
```
064cc04 docs: update CLAUDE.md with current state april 2026 + autonomous session rules
66a9efc fix: Lucas missing agent_type in generate_llm_response (was falling to Haiku)
6bcf88f fix: default agent timeout 5min→10min (Aisha timeout on large context)
3cf7dd1 fix: Emma analyze+validate max_tokens 16K→32K (was truncating UC digest)
2e48a19 feat: route Olivia (BA) to Opus 4.6 for higher quality UCs
a0f4249 docs: CHANGELOG for pre-E2E #145 fixes
883e317 Merge fix/remaining-bugs-pre-e2e145: P3+COST+H4+P1b
7aa5db9 fix(P3+COST+H4+P1b): subprocess→import, cost tracking all agents, standard object names
d3fa493 fix: 27 states (not 24), CR lifecycle +rejected, Ollama=OFF, YAML comments
```

### Incohérences déjà constatées entre docs et code
1. **State machine** : CLAUDE.md dit "24 états", commit `d3fa493` corrige vers "27 états". À valider dans `state_machine_service.py`.
2. **CHANGELOG.md** s'arrête au 14 février, ne documente pas les commits mars/avril.
3. **P3 (subprocess→import)** marqué "🔴 ÉCHEC" dans l'audit Gemini de février — **confirmé corrigé** par `7aa5db9`.
4. **P1b (scripts orphelins)** supprimés dans `7aa5db9` (direct_wbs.py, fix_wbs.py, gen_wbs.py, gen_wbs_direct.py).
5. **H4 (noms objets standards)** corrigé dans `7aa5db9` (`document_generator.py` teste maintenant `label → api_name → object → name`).

### État des services (18 avril 2026, 14h30 CET)
```
digital-humans-backend  : active ✅ (port 8002, /health répond OK)
digital-humans-frontend : active ✅ (port 3000)
digital-humans-worker   : INACTIVE ⚠️ (worker ARQ off — cohérent session audit offline)
postgresql              : active ✅
redis-server            : active ✅
ollama                  : active ✅ (port 11434)
```

---

## 3. Découvertes Étape 2 — Audit statique ruff

### Outil et scope
- `ruff 0.15.11` (installé dans le venv backend via `pip install ruff pyflakes`)
- Codes analysés : F (pyflakes : imports, names, vars) + E9 (syntax errors)
- Exclusions : `venv, __pycache__, .pytest_cache, migrations, alembic, tests, debug_exec_87`

### Synthèse quantitative
| Code | Count | Sévérité | Commentaire |
|------|-------|----------|-------------|
| **F821 Undefined name** | **22** | 🔴 CRITIQUE | Bugs runtime (NameError garanti sur le chemin concerné) |
| F401 imported but unused | ~70 | 🟡 Cosmétique | Code legacy / imports défensifs |
| F541 f-string without placeholders | 57 | 🟢 Cosmétique | Utilisation inutile de f-string |
| F841 local var assigned never used | 4 | 🟢 Cosmétique | Variables orphelines |
| E9 (syntax errors) | 0 | — | Le code compile |

### 🔴 Les 22 F821 — bugs runtime détaillés

#### A. `backend/app/services/sfdx_service.py` — `time` non importé (6 occurrences)
**Lignes** : 796, 798, 860, 862, 906, 908
**Cause** : Le fichier utilise `time.time()` pour mesurer les durées mais `import time` est absent. Imports actuels :
```python
import asyncio, json, logging, os, subprocess, tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
```
**Impact** : `NameError` à chaque appel de `retrieve_metadata`, `run_apex_tests`, `deploy`. **Hypothèse** : ce code n'est jamais réellement exécuté en prod (cohérent avec CLAUDE.md "BUILD : Jamais déployé bout-en-bout").
**Fix** : ajouter `import time` après la ligne 18.

#### B. `backend/app/services/pm_orchestrator_service_v2.py` — 4 F821
- **Ligne 1301** : `sf_cfg` hors scope dans `"api_version": org_info.get("apiVersion", sf_cfg.api_version)`. Bug conditionnel selon le chemin (per-project vs global singleton).
- **Lignes 2097, 2350** : `ChangeRequest` utilisé comme annotation string (`change_request: 'ChangeRequest'`). **À valider** : si forward ref string, pas un vrai bug runtime ; sinon il faut `from app.models.change_request import ChangeRequest` ou bloc `TYPE_CHECKING`.
- **Ligne 2364** : `SDSVersion` utilisé **avant** son import local ligne 2389 (`from app.models.sds_version import SDSVersion`). **NameError garanti** si ce chemin est exécuté.

#### C. 4 agents avec `self` hors méthode (9 occurrences)
Pattern commun : code utilisant `self._total_cost += response.get('cost_usd', 0.0)` apparemment indenté à plat, hors d'une méthode de classe. **Hypothèse forte** : artefact de la correction COST-001 (commit `7aa5db9` du 14 fév) mal fusionnée dans ces 4 agents.

| Fichier | Lignes concernées |
|---------|-------------------|
| `agents/roles/salesforce_admin.py` | 252, 291, 349, 769 (+ `model_used` ligne 797) |
| `agents/roles/salesforce_developer_apex.py` | 225, 277, 438 |
| `agents/roles/salesforce_developer_lwc.py` | 373 (`response` undefined), 450 (`self`) |
| `agents/roles/salesforce_qa_tester.py` | 413 (`response` undefined), 492 (`self`) |

**À faire dans la prochaine session** : lire chaque bloc en contexte (±30 lignes autour) pour distinguer :
- Simple réindentation manquante (code dans une méthode mais dé-indenté par erreur)
- Code écrit dans une fonction libre qui devrait être une méthode
- Bloc `else:` qui référence des variables du `if:` supprimé

### Imports unused notables (F401)
Pas critique mais révélateur de code legacy :
- `LLMProvider` importé dans 6+ agents sans usage (héritage fallback OpenAI ?)
- `subprocess` importé dans 4 fichiers (héritage pattern avant P3)
- `asyncio` importé inutilement dans 4 fichiers
- `docx.oxml.ns.qn` importé 3× sans usage

---

## 4. Ce qui reste à faire

### Étape 2 (suite)
- [ ] Lire les 22 F821 en contexte (±30 lignes) pour catégoriser chaque fix
- [ ] Grep patterns de vérification :
  - `grep -rn "subprocess.run\|subprocess.Popen\|create_subprocess_exec" backend/app backend/agents --include="*.py"` → confirmer disparition post-P3
  - `grep -rn "async def.*:" backend/app/api/routes/ | xargs -I{} grep -l "db.query\|db.execute" ...` → vérifier P0
  - `grep -rnE "/(home|opt|root|usr)/" backend/app backend/agents --include="*.py" | grep -v "test\|comment"` → vérifier P2
  - `grep -rn "try:.*ImportError\|except ImportError" backend/agents --include="*.py"` → fallbacks restants
  - `grep -rn "db.commit()" backend/app --include="*.py" | wc -l` → mesure P7
- [ ] Frontend : `cd frontend && npx tsc --noEmit` + `npx eslint src/ --quiet`

### Étape 3 — Audit sémantique (1M tokens)
Charger dans la fenêtre (ordre d'importance) :
1. `backend/app/services/pm_orchestrator_service_v2.py` (~2600 lignes, cœur du système)
2. `backend/app/services/agent_executor.py` (registre MIGRATED_AGENTS)
3. `backend/agents/roles/salesforce_*.py` (les 11 agents)
4. `backend/prompts/agents/*.yaml` (les 11 prompts)
5. `backend/app/services/llm_router_service.py` + `backend/config/llm_routing.yaml`
6. `backend/app/services/prompt_service.py`
7. `backend/app/services/state_machine_service.py` (24 ou 27 états, à valider)
8. `backend/app/services/budget_service.py`
9. `backend/app/api/routes/orchestrator/*.py`
10. `backend/app/api/routes/hitl_routes.py`
11. `frontend/src/components/ArchitectureReviewPanel.tsx`
12. `frontend/src/components/StructuredRenderer.tsx`
13. `frontend/src/components/DeliverableViewer.tsx`
14. `frontend/src/components/ChatSidebar.tsx`

Chercher :
- Clés de dicts incohérentes (ex. `qa_specs`/`qa_plan`, `salesforce_components`/`sf_objects`)
- Contrats cassés : ce que produit l'agent X ≠ ce qu'attend l'agent Y
- Méthodes appelées avec signature obsolète
- États state machine orphelins / transitions non définies
- Code effectivement mort non référencé

### Étape 4 — Confrontation rapports vs code réel
| ID | Doc dit | À vérifier dans le code |
|----|---------|-------------------------|
| P0 | ✅ Corrigé | Routes orchestrator en `def` sync, pas `async def` + `db.query` |
| P1 | 🟠 Partiel | `pm.py` supprimé ✅, scripts orphelins supprimés ✅ |
| P2 | ✅ Corrigé | Zéro hardcoded path `/opt/` `/home/` `/root/` dans backend |
| P3 | ✅ Corrigé | `_run_agent` utilise MIGRATED_AGENTS, pas `create_subprocess_exec` |
| P4 | ✅ Corrigé | `pm_orchestrator.py` (la route) < 50 lignes |
| P5 | ✅ Corrigé | `logging_config.py` actif, JSON format |
| P6 | ✅ Corrigé | Tous agents passent par LLM Router via `agent_type` |
| P7 | 🟡 Partiel | Mesurer ratio `db.commit()` manuel vs `with db.begin()` |
| P8 | ✅ Corrigé | Pas d'injection secrets via env subprocess |
| P9 | ✅ Corrigé | SDS sectioned actif, sections QA/DevOps/Data/Trainer présentes |
| P10 | 📋 Backlog | Pas de classe BaseAgent commune aux 11 agents |

### Étape 5 — Rédaction rapport final
`/mnt/user-data/outputs/AUDIT_REPORT_20260418.md` avec :
1. Exec summary (verdict + top 3 priorités)
2. Tableau récap des issues (sévérité, fichier, ligne, fix proposé)
3. Écarts documentation vs code
4. Recommandations avant refonte Agent Teams

---

## 5. Commandes utiles pour reprendre la session

```bash
# 1. Vérifier repo
cd /root/workspace/digital-humans-production
git log --oneline -5
git status -s

# 2. Vérifier services
systemctl is-active digital-humans-backend digital-humans-frontend \
  digital-humans-worker postgresql redis-server

# 3. Relancer ruff (doit refaire apparaître les 22 F821 si pas fixés)
cd backend
source venv/bin/activate  # ou: bash -c "source venv/bin/activate && ..."
ruff check --select F821 \
  --exclude venv,__pycache__,.pytest_cache,migrations,alembic,tests,debug_exec_87 \
  --output-format=grouped .

# 4. Audit statique complet
ruff check --select F,E9 \
  --exclude venv,__pycache__,.pytest_cache,migrations,alembic,tests,debug_exec_87 \
  --output-format=concise . > /tmp/ruff_audit.txt
wc -l /tmp/ruff_audit.txt
```

---

## 6. Hypothèses à valider lors de la prochaine session

1. **H1** : Les corrections `7aa5db9` (COST-001) ont introduit des F821 dans 4 agents par mauvaise fusion de la propagation `self._total_cost`.
2. **H2** : `sfdx_service.py` n'est jamais exécuté en prod — sinon le `NameError: time` serait remonté. Cohérent avec "BUILD jamais testé bout-en-bout" (CLAUDE.md).
3. **H3** : `pm_orchestrator_service_v2.py:1301` bug déclenché uniquement sur chemin "per-project SF config" vs "global singleton".
4. **H4** : `SDSVersion` ligne 2364 ne se déclenche que sur un chemin spécifique du CR lifecycle.
5. **H5** : `ChangeRequest` lignes 2097, 2350 est en forward ref string → pas un bug runtime mais une annotation fragile.

---

## 7. Priorisation tactique avant refonte Agent Teams

Pour ne pas lancer la refonte sur du code cassé :
1. **🔴 Bloquant** : Fixer les 22 F821 (30 min–1h, fixes triviaux : imports manquants + réindentation)
2. **🟠 Important** : Confirmer ou infirmer les hypothèses H1-H5 ci-dessus par lecture contextuelle
3. **🟡 Moyen** : Nettoyer les 70+ F401 (imports inutiles) pour réduire le bruit pendant la refonte
4. **🟢 Mineur** : F541/F841 (purement cosmétique, à déléguer à la refonte)

---

## 8. Options possibles pour la session suivante

**Option A — Voie propre (choisie par Sam le 18/04)**
Terminer Étapes 2 → 3 → 4 → rapport final, sans toucher au code. Livraison : rapport Markdown exhaustif. Temps estimé : 1h-1h30.

**Option B — Voie exécutive**
Fixer d'abord les 22 F821 (30 min), relancer ruff pour validation, puis reprendre l'audit sémantique sur base saine.

**Option C — Voie hybride**
Terminer l'audit (voie propre), produire le rapport, puis lancer une session séparée "fixes" avant la refonte Agent Teams.

---

## 9. Notes pour la continuation

- Pour l'Étape 3, **absolument charger** les 14 fichiers listés en section 4 dans la fenêtre 1M tokens avant de répondre, sinon l'analyse sera superficielle.
- Le repo contient **60+ archives de contexte quotidien** (`archives/CONTEXT_2026021X.md` à `CONTEXT_20260418.md`) qui ne sont pas trackées par git. Elles contiennent potentiellement des infos de sessions autonomes passées (à scanner si besoin de contexte manquant).
- Présence de dossiers suspects à investiguer : `backend/agents/backups/`, `backend/debug_exec_87/`, `backend/backups/`, `backend/backups_20251219_114242/`, `backups/`, `chroma_db/` (différent du RAG réel qui est à `/opt/digital-humans/rag/chromadb_data/`).
- Les `tasks/` (non tracké) pourraient contenir des plans de sessions récentes utiles.

---

*Document généré le 18 avril 2026 pendant la session d'audit. Archivé dans `docs/audits/AUDIT_SESSION_20260418.md` sur le VPS. À uploader dans Claude Projects pour continuation en session suivante.*
