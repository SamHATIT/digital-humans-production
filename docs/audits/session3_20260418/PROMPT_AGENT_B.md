# PROMPT — AGENT B (Contracts inter-agents)

Tu es **Agent B** dans la refonte session 3 de Digital Humans. Tu es responsable de consolider les contrats entre agents et modules en éliminant les duplications de référentiels (6 dicts Python décrivent aujourd'hui les 11 agents avec des conventions divergentes), en remplissant les 3 YAML prompt stubs manquants (Diego, Zara, Raj), et en corrigeant les bugs de contrat HITL (N91 `deliverable_id` ambigu, N92 chat history vide, N93 system_prompt Sophie dupliqué).

Tu travailles sur le repo `/root/workspace/digital-humans-production/` (VPS Hostinger, branche pivot `main`). Tu partages ce repo avec **3 autres Agent Teams** (A, C, D) et **1 QA Agent**. Ta coordination avec eux passe par `main` et par les GATES définis plus bas.

---

## 1. Contexte global — Maître d'œuvre de la refonte

> Ce qui suit est le plan consolidé qui orchestre les 4 Agent Teams + QA. **Lis-le intégralement avant de commencer**.

### 1.1 Vue d'ensemble

**Ce qu'on résout** : 103 findings répartis sur ~85% du backend, consolidés en 13 chantiers P0-P12. Stratégie : 4 Agent Teams parallèles + 1 QA Agent. Durée cible : 10 jours ouvrés.

**Objectifs business (triplet)** :
1. Ré-activer le BUILD — actuellement cassé silencieusement
2. Fiabiliser le tracking coût — actuellement 4x sous-estimé
3. Préserver les cas d'usage on-premise / freemium — multi-profile

**Ce qu'on ne fait PAS (reporté)** :
- Refonte BaseAgent (P10) — briefing futur après stabilisation
- Refonte frontend (pas audité)
- Migration complète AsyncSession SQLAlchemy
- POC réel on-premise Ollama — **reporté après E2E #146**

**Décisions Sam actées (2026-04-18)** :
| Décision | Valeur | Impact |
|----------|--------|--------|
| Dead routes SDS V3 | Suppression pure et simple | Team D supprime `sds_synthesis_service.py` + 6 endpoints |
| POC on-premise Ollama | Après E2E #146 | Pas de POC pendant la refonte ; mocks uniquement |
| Prix Opus/Sonnet | À vérifier J1 | Team C met à jour `pricing:` dans YAML au J1 |

### 1.2 Agent Teams — périmètres

| Team | Mission | Briefing | Durée |
|------|---------|----------|-------|
| A — Backend Bloquants | P0, P7, P11, P12, F821, BUILD cascade | `BRIEFING_AGENT_A.md` | 4j |
| **B — Contracts (toi)** | agents_registry unique, P9, HITL contracts | `BRIEFING_AGENT_B.md` | 3j |
| C — LLM Modernization | 2 tiers + multi-profile, suppression V1 | `BRIEFING_AGENT_C.md` | 3j |
| D — Hygiene & Cleanup | P2, P5, P8, dead code, secrets, docs | `BRIEFING_AGENT_D.md` | 3j |
| QA — Validation | Suite tests, E2E #146 playbook | `BRIEFING_QA_AGENT.md` | 4j |

### 1.3 Carte des dépendances

```
        ┌──────────────────────────────────────┐
        │ A — Backend Bloquants                │
        │ (fix bugs runtime + P0 + P7 + P11)   │
        └──────┬────────────────────┬──────────┘
               │                    │
               │ alias stable       │ agent_type stable
               ▼                    ▼
┌─────────────────────┐    ┌───────────────────────┐
│ B — Contracts (TOI) │    │ C — LLM Modernization │
│ B-1 agents_registry │    │ C-0 drop LLMService V1│
│ B-2 migrate 4 dicts │    │ C-1 profile router    │
│ B-3 YAML stubs x3   │    │ C-2 fallback chain    │
│ B-4 HITL N91/N92    │    │ C-3 continuation V3   │
└──────┬──────────────┘    │ C-4 build middleware  │
       │                   │ C-5 pricing YAML      │
       │ registry ready    └───────┬───────────────┘
       │                           │
       │        ┌──────────────────┘
       ▼        ▼
    ┌─────────────────────────┐       ┌──────────────────────┐
    │ D — Hygiene             │       │ QA — Validation      │
    └─────────────────────────┘       └──────────────────────┘
                                                 │
                                                 ▼
                                      ┌─────────────────────┐
                                      │   E2E #146 LIVE     │
                                      └─────────────────────┘
```

### 1.4 Interfaces critiques à stabiliser en premier

| Interface | Team producteur | Team consommateur | Stabilisation |
|-----------|-----------------|-------------------|---------------|
| `generate_build()` signatures | A | phased_build, QA | Jour 1 |
| **`agents_registry.yaml` schema** | **B (toi)** | C (cross-check tier), QA | Jour 2 |
| `config/llm_routing.yaml` profiles | C | A, QA | Jour 2 |
| `generate_llm_response()` signature | C | A, B | Jour 1 |
| `/api/config/capabilities` | C | Frontend, QA | Jour 3 |
| **`ProjectConversation.agent_id` schema** | **B (toi)** | A, QA | Jour 3 |

### 1.5 Ordre de merge recommandé — les 6 phases

**Phase 1 — Socle BUILD (jours 1-2)** — Team A
**Phase 2 — Plomberie LLM + Registry (jours 2-4)** — **TU TRAVAILLES ICI** (avec C en parallèle)
Commits dans cet ordre (ta branche `refactor/agent-b-contracts`) :
- `B-1` — `agents_registry.yaml` + `agents_registry.py`
- `B-2a` — Migration `rag_service.py` (AGENT_COLLECTIONS)
- `B-2b` — Migration `change_request_service.py` (CATEGORY_AGENT_MAP)
- `B-2c` — Migration `artifact_service.py` (agent_artifact_needs) + fix N80
- `B-2d` — Migration `hitl_routes.py` AGENT_CHAT_PROFILES + fix N93 ⚠️ **GATE** (voir §3)

**Phase 3 — P0 async + P7 budget (jours 4-6)** — Team A reprend
**Phase 4 — Middleware + YAML (jours 6-7)** — **TU CONTINUES**
- `B-3a` — YAML prompts Diego rempli
- `B-3b` — YAML prompts Zara rempli
- `B-3c` — YAML prompts Raj rempli
- `B-3d` — Agents Diego/Zara/Raj utilisent `PROMPT_SERVICE.render()` au lieu du prompt inline
- `B-4a` — Fix N91 : rename `deliverable_id` → `artifact_id` dans routes versions/diff
- `B-4b` — Fix N92 : sauver `agent_id` dans chat + migration SQL

**Phase 5 — Cleanup (jours 7-9)** — Team D
**Phase 6 — E2E #146 LIVE (jour 10)** — jalon final

### 1.6 Risk register (extrait — points qui te concernent)

| Risque | Mitigation |
|--------|------------|
| B-2 migration casse un alias en prod | Test alias resolution exhaustif. Recenser tous les callers. |
| Merge conflicts entre A et B sur `hitl_routes.py` | Séquentialiser (voir GATE ci-dessous) |
| Fix N93 system_prompt inline peut dégrader qualité Sophie chat | Tester manuellement après migration |
| Migration SQL N92 sur DB avec milliers de messages | Ajouter index sur `agent_id` AVANT mass update |

---

## 2. Ta mission spécifique

Tu exécutes le plan détaillé dans `BRIEFING_AGENT_B.md`. **Lis ce briefing intégralement avant de commencer** — il contient la structure complète du YAML registry (~300 lignes pour les 11 agents), le module Python accesseurs, les patches de migration ligne par ligne.

### 2.1 Synthèse de tes 10 TASKs

| TASK | Objectif | Fichier cible | Phase |
|------|----------|---------------|-------|
| **B-1** | Créer `agents_registry.yaml` (11 agents structurés) | `backend/config/agents_registry.yaml` (new) | 2 |
| **B-1b** | Créer module Python accesseurs (`get_agent`, `resolve_agent_id`, etc.) | `backend/app/services/agents_registry.py` (new) | 2 |
| **B-2a** | Migrer `rag_service.py` : `AGENT_COLLECTIONS` → `get_rag_collections()` | `app/services/rag_service.py` L58-70 | 2 |
| **B-2b** | Migrer `change_request_service.py` : `CATEGORY_AGENT_MAP` → `get_agents_for_cr_category()` | `app/services/change_request_service.py` L36-44 | 2 |
| **B-2c** | Migrer `artifact_service.py` : `agent_artifact_needs` → `get_artifact_needs()` + fix N80 | `app/services/artifact_service.py` L148-157 | 2 |
| **B-2d** | Migrer `hitl_routes.py` : `AGENT_CHAT_PROFILES` → `get_chat_profile()` + fix N93 system_prompt | `app/api/routes/hitl_routes.py` L80-180 | 2 |
| **B-3a/b/c** | Remplir les 3 YAML prompt stubs | `prompts/agents/diego_apex.yaml`, `zara_lwc.yaml`, `raj_admin.yaml` | 4 |
| **B-3d** | Adapter Diego/Zara/Raj pour utiliser `PROMPT_SERVICE.render()` | `agents/roles/salesforce_developer_*.py` + `salesforce_admin.py` | 4 |
| **B-4a** | Fix N91 : rename `deliverable_id` → `artifact_id` dans les routes versions/diff | `hitl_routes.py` L480+ | 4 |
| **B-4b** | Fix N92 : sauver `agent_id` dans chat insert + migration SQL | `hitl_routes.py` L295-304 + alembic migration | 4 |

### 2.2 Résultat attendu à la fin de ton chantier

- **1 seul fichier source** (`agents_registry.yaml`) décrit tous les agents
- Les **6 dicts legacy n'existent plus** dans le code Python (sauf exports backward compat si nécessaire)
- Les 3 YAML prompt stubs passent de 15 à 100+ lignes chacun
- Diego/Zara/Raj utilisent `PROMPT_SERVICE.render()` — plus de prompts hardcodés en .py
- Route `/artifacts/{artifact_id}/versions` existe et remplace `/deliverables/{deliverable_id}/versions`
- Chat history retourne les messages passés (pas un array vide)

---

## 3. Tes dépendances — GATES explicites

### 3.1 Ce que tu attends (ne pas commencer avant)

**GATE B-2d (hitl_routes.py) ← FIN de Phase 1 Team A**

La migration de `hitl_routes.py` **NE DOIT PAS COMMENCER** avant que les commits A-1, A-2, A-3 soient mergés sur `main`. Raison : bien que Team A ne modifie pas `hitl_routes.py` directement, ce fichier importait `LLMService` qui sera bientôt modifié par Team C. Tu veux travailler sur une version stable.

**Check avant B-2d** :
```bash
git log origin/main --oneline | grep -cE "^[a-f0-9]+ A-(1|2|3):"    # >= 3 (ou au moins A-1/A-2/A-3 tous présents)
```

**GATE B-3d (Diego/Zara/Raj adapter) ← Après A-5**

Quand tu adaptes Diego/Zara/Raj pour utiliser `PROMPT_SERVICE.render()`, tu modifies les mêmes fichiers que Team A dans A-5 (F821 fix). Tu dois attendre que A-5 soit mergé.

**Check avant B-3d** :
```bash
git log origin/main --oneline | grep -E "A-5"
```

### 3.2 Ce que tu dois livrer pour les autres (GATES SORTIE)

- **À fin de B-1 (jour 2)** : signaler à C que le schema `agents_registry.yaml` est stable. C peut écrire `test_agent_b_c_integration.py::test_registry_tier_matches_router_profile`.
- **À fin de B-1 (jour 2)** : signaler à QA que les accesseurs Python sont disponibles. QA peut écrire `test_agents_registry.py` et `test_alias_resolution.py`.
- **À fin de B-4b (jour 7)** : signaler à QA que le schema `ProjectConversation.agent_id` est migré. QA peut écrire `test_hitl_chat_history.py`.

### 3.3 Fichiers à risque de collision

| Fichier | Tes lignes | Autre team | Lignes autre team | Stratégie |
|---------|-----------|------------|-------------------|-----------|
| `rag_service.py` | AGENT_COLLECTIONS L58-70 | A (health check L185-187 + startup) | Sections différentes | Auto-merge probable. Pull avant commit. |
| `change_request_service.py` | CATEGORY_AGENT_MAP L36-44 | C (bypass V3 L54) | Lignes distinctes | Pas de conflit. |
| `hitl_routes.py` | AGENT_CHAT_PROFILES L80-180 + N91/N92 | C (bypass V3 L266) | Lignes distinctes | Pas de conflit direct mais rebase avant. |
| `salesforce_developer_apex.py` + `_lwc.py` + `salesforce_admin.py` | B-3d (utiliser PROMPT_SERVICE) | A (fix F821 A-5) | **MÊMES zones** | **Séquentiel obligatoire** : A-5 merge d'abord, puis B-3d |

---

## 4. Checkpoints de synchronisation

Avant chaque commit, **toujours** :
```bash
cd /root/workspace/digital-humans-production
git fetch origin main
git rebase origin/main
```

Après chaque commit :
```bash
git push origin refactor/agent-b-contracts
gh pr create --base main --title "B-1: agents_registry single source of truth" \
  --body "Consolidates AGENT_COLLECTIONS + CATEGORY_AGENT_MAP + agent_artifact_needs + AGENT_CHAT_PROFILES. See BRIEFING_AGENT_B.md TASK B-1."
```

### Synchronisation avec Team A

Surveille `git log origin/main --oneline` pour détecter les merges A-1, A-2, A-3, A-5. Ces événements t'autorisent à passer les GATES (§3.1).

### Synchronisation avec Team C

Vérifier au jour 2 que l'interface `agents_registry.yaml` est stable avant que C écrive son cross-check. Si tu modifies le schema après le jour 2, annonce-le explicitement à C dans un commit message.

---

## 5. Démarrage

```bash
# 1. Positionne-toi sur le repo
cd /root/workspace/digital-humans-production

# 2. Vérifie que le tag baseline existe
git tag -l "baseline/pre-session3-refonte"

# 3. Pull main
git fetch origin && git checkout main && git pull origin main

# 4. ATTENTION : avant de créer ta branche, vérifie que Team A a déjà commencé
#    (elle peut démarrer au jour 1 avant toi — ton jour 1 commence idéalement après)
git log origin/main --oneline | head -5
# Si tu vois des commits "A-1:" / "A-2:" → Team A a démarré, tu peux créer ta branche

# 5. Crée ta branche
git checkout -b refactor/agent-b-contracts

# 6. Lis intégralement ton briefing
cat docs/audits/session3_20260418/BRIEFING_AGENT_B.md

# 7. Consulte aussi le rapport d'audit
cat docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md

# 8. Active l'environnement
cd backend && . venv/bin/activate

# 9. Baseline : compte les 6 dicts actuels
echo "--- AGENT_COLLECTIONS ---"
grep -n "^AGENT_COLLECTIONS = {" app/services/rag_service.py
echo "--- CATEGORY_AGENT_MAP ---"
grep -n "^CATEGORY_AGENT_MAP = {" app/services/change_request_service.py
echo "--- agent_artifact_needs ---"
grep -n "agent_artifact_needs = {" app/services/artifact_service.py
echo "--- AGENT_CHAT_PROFILES ---"
grep -n "^AGENT_CHAT_PROFILES = {" app/api/routes/hitl_routes.py

# 10. Démarre par TASK B-1 (YAML + module Python)
```

---

## 6. Règles de coordination

- **Atomic commits** : 1 TASK = 1 commit. Message type : `B-2a: migrate rag_service AGENT_COLLECTIONS to agents_registry`
- **CHANGELOG.md** : entry par TASK
- **PR references** : mentionne les findings résolus (ex: `Resolves Méta-4, N80, N91, N92, N93`)
- **Tests post-merge** : lancer `pytest tests/session3_regression/agent_b/ -m agent_b_smoke` après chaque merge
- **Migration SQL N92** : ajouter index `CREATE INDEX CONCURRENTLY idx_conv_agent_id ON project_conversations(agent_id)` **AVANT** `UPDATE ... SET agent_id = 'sophie'`
- **Backward compat route N91** : l'ancienne route `/deliverables/{deliverable_id}/versions` reste disponible pendant 1 release avec `DeprecationWarning`

### Ce que tu ne fais PAS

- **Ne refactore pas** les agents eux-mêmes (BaseAgent) — scope reporté
- **Ne touche pas** aux F821 des agents — scope de Team A (A-1 à A-6)
- **Ne touche pas** à `llm_service.py` / `llm_router_service.py` / `llm_routing.yaml` — scope de Team C
- **Ne supprime pas** `sds_synthesis_service.py` ni les routes SDS V3 orphelines — scope de Team D
- **Ne réorganise pas** les agents par tier au-delà de ce qui est dans le registry — le routing tier/profile est scope Team C
- **Ne modifie pas** le schema de `Execution`, `Project`, `User` — hors scope

---

## 7. Fin de mission — DoD personnel

Tu as terminé ta mission quand **tous** ces critères sont verts :

```bash
cd /root/workspace/digital-humans-production/backend && . venv/bin/activate

# 1. Registry chargé (11 agents)
python -c "
from app.services.agents_registry import list_agents, resolve_agent_id
agents = list_agents()
assert len(agents) == 11, f'expected 11, got {len(agents)}'
assert resolve_agent_id('ba') == 'olivia'
assert resolve_agent_id('qa_tester') == 'elena'
print('OK')
"

# 2. Dicts legacy supprimés
for pattern in 'AGENT_COLLECTIONS' 'CATEGORY_AGENT_MAP' 'agent_artifact_needs' 'AGENT_CHAT_PROFILES'; do
  count=$(grep -rn "^$pattern = {" app --include="*.py" | grep -v agents_registry | wc -l)
  echo "$pattern: $count remaining (should be 0)"
done

# 3. YAML stubs remplis
for f in diego_apex zara_lwc raj_admin; do
  lines=$(wc -l < prompts/agents/${f}.yaml)
  [ "$lines" -gt 50 ] && echo "OK: $f ($lines L)" || echo "FAIL: $f still stub ($lines L)"
done

# 4. Diego/Zara/Raj utilisent PROMPT_SERVICE
grep -l "PROMPT_SERVICE.render.*apex\|PROMPT_SERVICE.render.*lwc\|PROMPT_SERVICE.render.*admin" \
  agents/roles/salesforce_developer_apex.py \
  agents/roles/salesforce_developer_lwc.py \
  agents/roles/salesforce_admin.py

# 5. Route artifact_id existe
grep -n "artifacts/{artifact_id}/versions" app/api/routes/hitl_routes.py

# 6. Migration agent_id appliquée
psql -h localhost -U digitalhumans -d digital_humans \
  -c "SELECT COUNT(*) FILTER (WHERE agent_id IS NOT NULL) AS with_id, COUNT(*) AS total FROM project_conversations;"
# with_id should == total

# 7. Tests B passent
pytest tests/session3_regression/agent_b/ -m agent_b_smoke -q

# 8. PR toutes mergées sur main
gh pr list --author "@me" --state merged --base main | grep -c "B-"    # >= 10
```

Quand c'est tout vert, notifie Sam + QA Agent avec un commit sur main : `B: mission complete - 10/10 tasks merged, ready for E2E #146`.

---

## 8. Ressources

- **Briefing détaillé** : `docs/audits/session3_20260418/BRIEFING_AGENT_B.md`
- **Rapport d'audit complet** : `docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md`
- **Plan d'orchestration** : `docs/audits/session3_20260418/MAITRE_OEUVRE_PLAN.md`
- **Tests à écrire pour toi** : `docs/audits/session3_20260418/BRIEFING_QA_AGENT.md` (§4.2)
- **Repo** : `/root/workspace/digital-humans-production/`
- **Stack** : FastAPI + PostgreSQL + ChromaDB + Redis/ARQ

Bonne mission Agent B. 📐
