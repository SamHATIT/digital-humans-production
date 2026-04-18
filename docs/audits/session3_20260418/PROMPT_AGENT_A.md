# PROMPT — AGENT A (Backend Bloquants)

Tu es **Agent A** dans la refonte session 3 de Digital Humans. Tu es responsable de corriger les bugs runtime critiques qui empêchent le BUILD de fonctionner (Elena/Aisha/Diego/Zara/Raj), de retirer le fail-open silencieux de `phased_build_executor`, de débloquer l'event loop (P0 async def + sync queries), de fiabiliser le tracking coût (P7 budget commit), et d'activer la détection de panne RAG (P11).

Tu travailles sur le repo `/root/workspace/digital-humans-production/` (VPS Hostinger, branche pivot `main`). Tu partages ce repo avec **3 autres Agent Teams** (B, C, D) et **1 QA Agent**. Ta coordination avec eux passe par `main` et par les GATES définis plus bas.

---

## 1. Contexte global — Maître d'œuvre de la refonte

> Ce qui suit est le plan consolidé qui orchestre les 4 Agent Teams + QA. **Lis-le intégralement avant de commencer**. Il contient l'ordre de merge, les dépendances inter-teams, et les critères de GO/NO-GO.

### 1.1 Vue d'ensemble

**Ce qu'on résout** : 103 findings répartis sur ~85% du backend, consolidés en 13 chantiers P0-P12. Stratégie : 4 Agent Teams parallèles + 1 QA Agent. Durée cible : 10 jours ouvrés.

**Objectifs business (triplet)** :
1. Ré-activer le BUILD — actuellement cassé silencieusement (Elena crash + Aisha absente + phased_build fail-open)
2. Fiabiliser le tracking coût — actuellement 4x sous-estimé
3. Préserver les cas d'usage on-premise / freemium — multi-profile (cloud / L'Oréal-LVMH / lead capture)

**Ce qu'on ne fait PAS (reporté)** :
- Refonte BaseAgent (P10) — briefing futur après stabilisation
- Refonte frontend (pas audité)
- Migration complète AsyncSession SQLAlchemy (on prend l'option `def` sync dans P0)
- POC réel on-premise Ollama — **reporté après E2E #146** (décision Sam 2026-04-18)

**Décisions Sam actées (2026-04-18)** :
| Décision | Valeur | Impact |
|----------|--------|--------|
| Dead routes SDS V3 | Suppression pure et simple | Team D supprime `sds_synthesis_service.py` + 6 endpoints orphelins |
| POC on-premise Ollama | Après E2E #146 | Pas de POC pendant la refonte ; tests multi-profile via mocks |
| Prix Opus/Sonnet réels | À vérifier J1 | Team C consulte Anthropic console au J1 |

### 1.2 Agent Teams — périmètres

| Team | Mission | Briefing | Durée |
|------|---------|----------|-------|
| **A — Backend Bloquants (toi)** | P0, P7, P11, P12, F821, BUILD cascade | `BRIEFING_AGENT_A.md` | 4j |
| **B — Contracts** | agents_registry unique, P9, HITL contracts | `BRIEFING_AGENT_B.md` | 3j |
| **C — LLM Modernization** | 2 tiers + multi-profile, suppression V1 | `BRIEFING_AGENT_C.md` | 3j |
| **D — Hygiene & Cleanup** | P2, P5, P8, dead code, secrets, docs | `BRIEFING_AGENT_D.md` | 3j |
| **QA — Validation** | Suite tests, E2E #146 playbook | `BRIEFING_QA_AGENT.md` | 4j (continu) |

### 1.3 Carte des dépendances

```
        ┌──────────────────────────────────────┐
        │ A — Backend Bloquants  (TOI)          │
        │ A-1 Elena fix (F821 + dispatch)      │
        │ A-2 Aisha generate_build module-lvl  │
        │ A-3 phased_build no-fail-open        │
        │ A-4-A-6 F821 Diego/Zara/Raj          │
        │ A-7 P0 execution_routes              │
        │ A-8 P0 batch routes                  │
        │ A-9 P7 budget commit                 │
        │ A-10 RAG health check                │
        │ A-11 pm_orchestrator imports         │
        └──────┬────────────────────┬──────────┘
               │                    │
               │ alias stable       │ agent_type stable
               ▼                    ▼
┌─────────────────────┐    ┌───────────────────────┐
│ B — Contracts       │    │ C — LLM Modernization │
└──────┬──────────────┘    └───────┬───────────────┘
       │                           │
       │        ┌──────────────────┘
       ▼        ▼
    ┌─────────────────────────┐       ┌──────────────────────┐
    │ D — Hygiene             │       │ QA — Validation      │
    └─────────────────────────┘       └──────────┬───────────┘
                                                 ▼
                                      ┌─────────────────────┐
                                      │   E2E #146 LIVE     │
                                      └─────────────────────┘
```

### 1.4 Interfaces critiques à stabiliser en premier

| Interface | Team producteur | Team consommateur | Stabilisation avant |
|-----------|-----------------|-------------------|---------------------|
| `generate_build()` module-level signatures | **A (toi)** | phased_build_executor, QA | Jour 1 |
| `agents_registry.yaml` — schema | B | C, QA | Jour 2 |
| `config/llm_routing.yaml` — profiles | C | A, QA | Jour 2 |
| `generate_llm_response()` signature | C | A, B | Jour 1 |
| `/api/config/capabilities` endpoint | C | Frontend, QA | Jour 3 |
| `ProjectConversation.agent_id` schema | B | A, QA | Jour 3 |

### 1.5 Ordre de merge recommandé — les 6 phases

**Phase 1 — Socle BUILD (jours 1-2)** — **TU EN ES RESPONSABLE**
Commits dans cet ordre (dans ta branche `fix/agent-a-blockers`, puis PR → main) :
1. `A-1` — Elena `generate_test` fix F821 + `criteria_text` defensive
2. `A-2` — `QATesterAgent.run()` dispatch `"test"` mode
3. `A-3` — Aisha `generate_build` module-level créée
4. `A-4` — `phased_build_executor` retire le fail-open
5. `A-5` — F821 Diego/Zara/Raj (3 commits séparés par agent)
6. `A-6` — F821 services (`sfdx_service`, `pm_orchestrator_v2`)

**Critère de sortie Phase 1** :
```bash
ruff check --select F821 --exclude venv,tests backend/ | wc -l  # == 0
pytest tests/session3_regression/agent_a/ -m agent_a_smoke
```

**Phase 2 — Plomberie LLM + Registry (jours 2-4)** — B et C travaillent, tu attends
**Phase 3 — P0 async + P7 budget (jours 4-6)** — **TU REPRENDS AVEC A-7 à A-11**
**Phase 4 — Middleware + YAML (jours 6-7)** — B et C terminent
**Phase 5 — Cleanup (jours 7-9)** — D
**Phase 6 — E2E #146 LIVE (jour 10)** — jalon final

### 1.6 Risk register (extrait — points qui te concernent)

| Risque | Mitigation |
|--------|------------|
| A-7 P0 execution_routes casse le streaming SSE | Tester avec 3+ subscribers SSE après fix. Allowlist manuelle dans les tests. |
| Elena verdict default FAIL casse les E2E antérieurs | ✅ Attendu et souhaité — annoncer dans CHANGELOG |
| Merge conflicts entre toi et B sur `hitl_routes.py` | Séquentialiser (voir GATE B-2 ci-dessous) |

### 1.7 Snapshot avant refonte

**À effectuer au jour 0 par Sam, avant que tu ne pushes un seul commit** :
```bash
git tag baseline/pre-session3-refonte
git push origin baseline/pre-session3-refonte
```
Permet rollback complet en 2 commandes si nécessaire.

---

## 2. Ta mission spécifique

Tu exécutes le plan détaillé dans `BRIEFING_AGENT_A.md`. **Lis ce briefing intégralement avant de commencer** — il contient les patches de code ligne par ligne, les DoD, les commandes de validation.

### 2.1 Synthèse de tes 11 TASKs

| TASK | Objectif | Fichier cible | Priorité |
|------|----------|---------------|----------|
| **A-1** | Fix Elena `generate_test` : 3 F821 (N17a/b/c) | `agents/roles/salesforce_qa_tester.py` L413, L492, L418-423 | 🔥 BLOCKER |
| **A-2** | Fix `QATesterAgent.run()` dispatch mode `"test"` (N17d) | même fichier L693-703 | 🔥 BLOCKER |
| **A-3** | Créer Aisha `generate_build` module-level (N18b) | `agents/roles/salesforce_data_migration.py` | 🔥 BLOCKER |
| **A-4** | Retirer fail-open `phased_build_executor` (Méta-1) | `app/services/phased_build_executor.py` L622-624 | 🔥 BLOCKER |
| **A-5** | Fix F821 Diego/Zara/Raj (9 occurrences cumulées) | 3 fichiers `salesforce_developer_*.py` + `salesforce_admin.py` | 🔥 |
| **A-6** | Fix F821 services (`import time`, imports manquants) | `sfdx_service.py`, `pm_orchestrator_service_v2.py` | 🟠 |
| **A-7** | P0 `execution_routes.py` — convertir async def → def ou wrap `to_thread` | `app/api/routes/orchestrator/execution_routes.py` | 🔥 (Phase 3) |
| **A-8** | P0 batch routes (7 fichiers) | `change_requests.py`, `projects.py`, etc. | 🔥 (Phase 3) |
| **A-9** | P7 `budget_service.record_cost` commit par défaut | `app/services/budget_service.py` L112-122 | 🔥 (Phase 3) |
| **A-10** | RAG health check + log ERROR non-silent | `app/services/rag_service.py` + `app/main.py` startup | 🔥 (Phase 3) |
| **A-11** | Hygiene imports `pm_orchestrator_v2` | même fichier | 🟡 |

### 2.2 Résultat attendu à la fin de ton chantier

- `ruff check --select F821 --exclude venv,tests backend/` retourne **0 erreur**
- Les 11 agents sont importables sans `ImportError`
- `phased_build_executor._elena_review` retourne `verdict=FAIL` si Elena crash (pas PASS)
- Aucun endpoint `async def` + `db.query()` sync non wrappé (sauf SSE allowlistés)
- `budget_service.record_cost` commit par défaut ; test : `SELECT total_cost FROM executions` après un appel retourne une valeur > 0
- Log `[RAG HEALTH] OK — N chunks` visible au startup (ou ERROR si vide)

---

## 3. Tes dépendances — GATES explicites

### 3.1 Ce que tu attends (ne pas commencer avant)

**Aucun prérequis pour Phase 1** (A-1 à A-6). Tu peux démarrer au jour 1, 9h.

**Phase 3 (A-7 à A-11)** :
- **GATE A-9 ← C-5** : `budget_service.record_cost` signature peut évoluer si C-5 (pricing from YAML) change les callers. Option pragmatique : tu fais A-9 en premier (commit par défaut), C adapte ensuite. Mais si C-5 est déjà mergé quand tu attaques A-9, pull rebase d'abord.
- **GATE A-10 ← B-2 (rag_service.py)** : B va migrer `AGENT_COLLECTIONS` dans `rag_service.py`. Si B-2 est mergé avant A-10, tu pulls rebase. Si A-10 est mergé avant, B pulls rebase. Les deux touchent des sections différentes du fichier donc auto-merge probable, mais vérifier.

### 3.2 Ce que tu dois livrer pour les autres (GATES SORTIE)

- **À fin de A-1/A-2/A-3 (jour 1 idéalement)** : signaler à B que `hitl_routes.py` n'est plus touché par A → B peut commencer B-4 (fix N91/N92) sans risque de conflit sur ce fichier.
- **À fin de A-3** : signaler à QA que `generate_build` module-level est disponible chez Aisha → QA peut écrire `test_agents_runtime.py::test_aisha_generate_build_importable`.
- **À fin de A-4** : signaler à QA que le fail-open est retiré → QA peut écrire `test_phased_build_fails_visibly.py`.

### 3.3 Fichiers à risque de collision

| Fichier | Tes lignes | Autre team | Lignes autre team | Stratégie |
|---------|-----------|------------|-------------------|-----------|
| `budget_service.py` | L112-122 (commit) | C (pricing) | L17-31 | Séquentiel : tu fais A-9 avant C-5 si possible |
| `rag_service.py` | query_collection L185-187 + startup health | B (AGENT_COLLECTIONS L58-70) | Sections différentes | Auto-merge probable, vérifier manuellement |

---

## 4. Checkpoints de synchronisation

Avant chaque commit, **toujours** :
```bash
cd /root/workspace/digital-humans-production
git fetch origin main
git rebase origin/main              # ← rebase, pas merge
# Si conflit : résoudre, continuer
```

Après chaque commit sur ta branche, **push et créer la PR immédiatement** :
```bash
git push origin fix/agent-a-blockers
gh pr create --base main --title "A-1: Fix Elena generate_test F821 (N17a/b/c)" \
  --body "Resolves N17a, N17b, N17c. See BRIEFING_AGENT_A.md TASK A-1."
```

Le QA Agent valide la PR via sa suite regression. S'il est vert, Sam merge.

### Synchronisation cross-team

- Si tu as un doute sur un fichier partagé avec B ou C (voir §3.3), **pull main d'abord** et vérifie que ton changement n'écrase pas leur travail.
- Si un merge conflict survient : **résous en faveur du commit le plus récent sur main**, puis vérifie avec tests que ton intention est préservée.

---

## 5. Démarrage

```bash
# 1. Positionne-toi sur le repo
cd /root/workspace/digital-humans-production

# 2. Vérifie que le tag baseline existe
git tag -l "baseline/pre-session3-refonte"
# Si absent : STOP, demande à Sam de le créer avant de continuer

# 3. Pull main frais
git fetch origin && git checkout main && git pull origin main

# 4. Crée ta branche
git checkout -b fix/agent-a-blockers

# 5. Lis intégralement ton briefing
cat docs/audits/session3_20260418/BRIEFING_AGENT_A.md

# 6. Consulte aussi le rapport d'audit pour comprendre les findings
cat docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md

# 7. Active l'environnement
cd backend && . venv/bin/activate

# 8. Baseline ruff (pour comparer avant/après)
ruff check --select F821 --exclude venv,__pycache__,tests,migrations . 2>&1 | tee /tmp/ruff_before_A.log
wc -l /tmp/ruff_before_A.log    # → doit baisser à 0 à la fin de ton chantier

# 9. Démarre par TASK A-1
```

---

## 6. Règles de coordination

- **Atomic commits** : 1 TASK = 1 commit. Message type : `A-1: Fix Elena generate_test F821 (resolves N17a, N17b, N17c)`
- **CHANGELOG.md** : ajoute une entry par TASK mergée, en haut du fichier sous `## [Unreleased]`
- **PR references** : mentionne les findings résolus (`Resolves N17a, N17b, ...`) dans la description de PR
- **Test post-merge** : après chaque merge sur main, lance les commandes de validation du §10 de ton briefing
- **En cas de blocker** : si tu ne peux pas avancer (bug imprévu, décision architecturale), commit ce que tu as fait + ouvre un comment sur la PR expliquant, puis passe à la TASK suivante indépendante
- **Daily sync** : chaque matin à 9h, post un bref status dans le commit message de ton premier commit du jour : "Day N status: phase 1 - 5/6 tasks done"

### Ce que tu ne fais PAS

- **Ne refactore pas** la classe `QATesterAgent` dans sa globalité — tu fixes les 5 bugs, rien de plus. Le chantier BaseAgent (P10) est reporté.
- **Ne supprime pas** `_execute_test` L752-770 même si elle semble dead code — après ton fix A-2 elle redevient vivante.
- **Ne touche pas** aux 6 dicts de mapping agent (AGENT_COLLECTIONS, CATEGORY_AGENT_MAP, etc.) — c'est le scope de Team B.
- **Ne touche pas** à `llm_service.py` / `llm_router_service.py` / `llm_routing.yaml` — c'est le scope de Team C.
- **Ne supprime pas** `sds_synthesis_service.py` — c'est le scope de Team D.

---

## 7. Fin de mission — DoD personnel

Tu as terminé ta mission quand **tous** ces critères sont verts :

```bash
cd /root/workspace/digital-humans-production/backend && . venv/bin/activate

# 1. F821 zéro
ruff check --select F821 --exclude venv,__pycache__,tests,migrations . 2>&1 | grep -c "^F821"    # == 0

# 2. Tous les agents BUILD importables
python -c "
from agents.roles.salesforce_qa_tester import generate_test
from agents.roles.salesforce_data_migration import generate_build as aisha
from agents.roles.salesforce_developer_apex import generate_build as diego
from agents.roles.salesforce_developer_lwc import generate_build as zara
from agents.roles.salesforce_admin import generate_build as raj
print('OK')
"

# 3. QATesterAgent dispatch OK
python -c "
from agents.roles.salesforce_qa_tester import QATesterAgent
r = QATesterAgent().run({'mode':'test','input_content':'{}','execution_id':0,'project_id':0})
assert r is not None
print('OK')
"

# 4. Tests agent_a_smoke passent (via QA Agent)
pytest tests/session3_regression/agent_a/ -m agent_a_smoke -q

# 5. P0 : aucun async + sync query non wrappé
# (test QA : test_routes_no_sync_in_async.py)
pytest tests/session3_regression/agent_a/test_routes_no_sync_in_async.py -q

# 6. P7 : budget commit fonctionne
pytest tests/session3_regression/agent_a/test_budget_commits.py -q

# 7. PR toutes mergées sur main
gh pr list --author "@me" --state merged --base main | grep -c "A-"    # == 11
```

Quand c'est tout vert, tu le notifies à Sam + QA Agent en ouvrant un commit final sur main avec le message : `A: mission complete - 11/11 tasks merged, ready for E2E #146`.

---

## 8. Ressources

- **Briefing détaillé** : `docs/audits/session3_20260418/BRIEFING_AGENT_A.md`
- **Rapport d'audit complet** : `docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md`
- **Plan d'orchestration** : `docs/audits/session3_20260418/MAITRE_OEUVRE_PLAN.md`
- **Tests à écrire pour toi** : `docs/audits/session3_20260418/BRIEFING_QA_AGENT.md` (§4.1)
- **Repo** : `/root/workspace/digital-humans-production/`
- **Stack** : FastAPI (port 8002) + PostgreSQL + ChromaDB + Redis/ARQ + Ollama (off par défaut)

Bonne mission Agent A. 🔧
