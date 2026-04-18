# MAÎTRE D'ŒUVRE — Plan de refonte session 3

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md` + 5 briefings (A, B, C, D, QA)
**Rôle de ce document** : orchestration des 4 Agent Teams + QA. Point d'entrée unique pour Sam et pour chaque Agent Team au début de la refonte.

---

## 1. Vue d'ensemble

### Ce qu'on résout

La refonte traite **103 findings** répartis sur ~85% du backend, consolidés en **13 chantiers P0-P12**. La stratégie : **4 Agent Teams parallèles** + **1 QA Agent** qui valide chaque merge. Durée cible : **10 jours ouvrés** (2 semaines).

### Objectifs business (triplet)

1. **Ré-activer le BUILD** — actuellement cassé silencieusement (Elena crash + Aisha absente + phased_build fail-open)
2. **Fiabiliser le tracking coût** — actuellement 4x sous-estimé
3. **Préserver les cas d'usage on-premise / freemium** — multi-profile (cloud / L'Oréal-LVMH / lead capture)

### Ce qu'on ne fait PAS (reporté)

- Refonte BaseAgent (P10) — briefing futur après stabilisation
- Refonte frontend (pas audité)
- Migration complète AsyncSession SQLAlchemy (on prend l'option `def` sync dans P0)
- POC réel on-premise Ollama — **reporté après E2E #146** (décision Sam 2026-04-18)

### Décisions Sam actées (2026-04-18)

| Décision | Valeur | Impact |
|----------|--------|--------|
| Dead routes SDS V3 | **Suppression pure et simple** | Team D supprime `sds_synthesis_service.py` + 6 endpoints orphelins dans `sds_v3_routes.py`. Tag `legacy/sds_v3_synthesis_before_removal` avant `git rm` |
| POC on-premise Ollama | **Après E2E #146** | Pas de POC réel Ollama pendant la refonte ; tests multi-profile via mocks uniquement. POC réel = étape séparée avant vente L'Oréal/LVMH |
| Prix Opus/Sonnet réels | À vérifier J1 | Team C consulte Anthropic console au jour 1 et met à jour `pricing:` dans `llm_routing.yaml` avant merge C-5 |

---

## 2. Agent Teams — périmètres et responsables

| Team | Mission | Briefing | LOC impactés | Durée |
|------|---------|----------|--------------|-------|
| **A — Backend Bloquants** | P0, P7, P11, P12, F821 fix, BUILD cascade | `BRIEFING_AGENT_A.md` | ~3 000 | 4j |
| **B — Contracts** | Agents registry unique, P9, HITL contracts | `BRIEFING_AGENT_B.md` | ~1 500 | 3j |
| **C — LLM Modernization** | 2 tiers + multi-profile, suppression V1 | `BRIEFING_AGENT_C.md` | ~1 500 | 3j |
| **D — Hygiene & Cleanup** | P2, P5, P8, dead code, secrets, docs | `BRIEFING_AGENT_D.md` | ~800 | 3j |
| **QA — Validation** | Suite tests, E2E #146 playbook | `BRIEFING_QA_AGENT.md` | ~2 000 (tests) | 4j |

**Parallélisation** : A, C, D peuvent commencer simultanément. B démarre dès que le socle A-1 à A-3 (fix bugs critiques Elena/Aisha) est mergé car B dépend de signatures stables. QA suit tous les merges en continu.

---

## 3. Carte des dépendances inter-teams

```
        ┌──────────────────────────────────────┐
        │ A — Backend Bloquants                │
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
    │ D-1 paths hardcoded     │       │ Suite A,B,C,D tests  │
    │ D-2 logs fragmentés     │       │ Cross-team tests     │
    │ D-3 secrets rotation    │       │ E2E #146 playbook    │
    │ D-4 dead routes SDS V3  │       └──────────┬───────────┘
    │ D-5 docs ADR            │                  │
    └─────────────────────────┘                  │
                                                 ▼
                                      ┌─────────────────────┐
                                      │   E2E #146 LIVE     │
                                      │   (jalon final)     │
                                      └─────────────────────┘
```

### Interfaces critiques à stabiliser en premier

| Interface | Team producteur | Team consommateur | Stabilisation avant jour |
|-----------|-----------------|-------------------|--------------------------|
| `agents_registry.yaml` — schema | B | C (tier cross-check), QA (tests) | Jour 2 |
| `config/llm_routing.yaml` — profiles | C | A (agents appelants), QA | Jour 2 |
| `generate_llm_response()` signature | C | A (agents), B (hitl chat) | Jour 1 |
| `generate_build()` module-level signatures | A | phased_build_executor, QA | Jour 1 |
| `/api/config/capabilities` endpoint | C | Frontend, D (docs), QA | Jour 3 |
| `ProjectConversation.agent_id` schema | B | A (fix chat), QA | Jour 3 |

---

## 4. Ordre de merge recommandé

### Phase 1 — Socle BUILD (jours 1-2)
**Objectif** : faire marcher le BUILD de base, sans autre ambition.

Commits dans cet ordre :
1. `A-1` — Elena `generate_test` fix F821 + `criteria_text` defensive
2. `A-2` — `QATesterAgent.run()` dispatch `"test"` mode
3. `A-3` — Aisha `generate_build` module-level créée
4. `A-4` — `phased_build_executor` retire le fail-open
5. `A-5` — F821 Diego/Zara/Raj (3 commits séparés par agent)
6. `A-6` — F821 services (`sfdx_service`, `pm_orchestrator_v2`)

**Critère de sortie de phase** :
```bash
ruff check --select F821 --exclude venv,tests backend/ | wc -l  # == 0
pytest tests/session3_regression/agent_a/ -m agent_a_smoke
```

### Phase 2 — Plomberie LLM + Registry (jours 2-4)
**Objectif** : mettre en place le nouveau routage LLM et le registry agents.

Commits :
7. `C-1` — Nouveau `config/llm_routing.yaml` (format multi-profile)
8. `C-1b` — Router `_select_provider` profile-aware
9. `C-0` — Suppression `LLMService` V1 + wrapper mince
10. `B-1` — `agents_registry.yaml` + `agents_registry.py`
11. `B-2` — Migration `rag_service`, `change_request_service`, `artifact_service` (un commit par service)
12. `B-2b` — Migration `hitl_routes` AGENT_CHAT_PROFILES
13. `C-3` — Continuation CRIT-02 dans Router V3
14. `C-5` — Pricing depuis YAML

**Critère de sortie** :
```bash
pytest tests/session3_regression/agent_b/ tests/session3_regression/agent_c/
# + cross-team
pytest tests/session3_regression/cross/test_agent_b_c_integration.py
```

### Phase 3 — P0 async + P7 budget (jours 4-6)
**Objectif** : débloquer l'event loop et fiabiliser le tracking coût.

Commits :
15. `A-9` — `budget_service.record_cost` commit par défaut
16. `A-10` — RAG health check au boot + logs ERROR
17. `A-7` — P0 `execution_routes.py` (BLOCKER critique)
18. `A-8` — P0 batch routes (un commit par fichier : change_requests, projects, wizard, deployment, business_requirements, environments, sds_v3)

**Critère de sortie** :
```bash
pytest tests/session3_regression/agent_a/test_routes_no_sync_in_async.py
pytest tests/session3_regression/agent_a/test_budget_commits.py
pytest tests/session3_regression/agent_a/test_rag_health_check.py
```

### Phase 4 — Middleware build_enabled + YAML prompts (jours 6-7)
**Objectif** : feature flag freemium + remplir les prompts stubs.

Commits :
19. `C-4` — `BuildEnabledMiddleware` + `/api/config/capabilities`
20. `B-3` — YAML prompts Diego/Zara/Raj remplis
21. `B-3b` — Agents Diego/Zara/Raj utilisent `PROMPT_SERVICE.render()` au lieu du prompt inline
22. `B-4` — Fix N91 (`deliverable_id` → `artifact_id`) + N92 (chat history agent_id)

**Critère de sortie** :
```bash
pytest tests/session3_regression/agent_c/test_middleware_build_disabled_freemium.py
# Via les 3 profiles successifs
for p in cloud on-premise freemium; do
  DH_DEPLOYMENT_PROFILE=$p pytest tests/session3_regression/agent_c/test_llm_router_profiles.py
done
```

### Phase 5 — Cleanup (jours 7-9)
**Objectif** : hygiene + docs + observabilité.

Commits :
23. `D-1` — Paths hardcodés → `app/config.py` lazy settings (multiple commits)
24. `D-5` — Backup files supprimés, `.gitignore` archives
25. `D-2` — Logs unifiés + `ExecutionContextMiddleware`
26. `D-3` — Secrets rotation docs + script
27. `D-4` — Dead routes SDS V3 **suppression** (tag `legacy/sds_v3_synthesis_before_removal` + `git rm sds_synthesis_service.py` + retrait 6 endpoints)
28. `D-5b` — ADR-001-llm-strategy, ADR-002-agents-registry, docs/agents.md, docs/deployment.md multi-profile

**Critère de sortie** :
```bash
pytest tests/session3_regression/agent_d/
find backend -name "*.backup*" | wc -l       # == 0
grep -rn "/root/\|/home/" backend/app --include="*.py" | grep -v "# allow-" | wc -l  # == 0
```

### Phase 6 — E2E #146 LIVE (jour 10)
**Objectif** : validation finale sur un cas métier réel.

- Suivre `docs/e2e-tests/E2E_146_PLAYBOOK.md` (produit par QA)
- Compte-rendu dans `docs/e2e-tests/E2E_146_RESULTS.md`

---

## 5. Planning consolidé (Gantt simplifié)

```
Jour    1    2    3    4    5    6    7    8    9   10
        |    |    |    |    |    |    |    |    |    |
Team A  ▓▓▓▓▓▓▓▓▓▓─────▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓─────────────
         ↑ BLOCKERS      ↑ P0                  ↑ fini
Team B  ──────▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓───────────────────
         registry  migrations  YAML+HITL
Team C  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓─────────────────────────
         YAML+router  drop V1  middleware
Team D  ─────────────────────────▓▓▓▓▓▓▓▓▓▓▓▓─────
                                  paths logs docs
Team QA ─▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓
         fixtures  tests_per_team  cross  playbook
                                                 ▲ E2E #146

Jalons :
  J2 fin : BUILD fonctionnel en local (blockers A-1/A-2/A-3/A-4 mergés)
  J4 fin : Multi-profile routing actif + registry consolidé
  J6 fin : P0 résolu + feature flag freemium opérationnel
  J9 fin : Code propre, docs à jour, tests verts
  J10   : E2E #146 LIVE — go/no-go pour release
```

**Parallélisation maximale** : 4 Agent Teams + QA simultanément sur jours 2-6. Attention aux interfaces (section 3) pour éviter les conflits de merge.

---

## 6. Commandes de validation — consolidées

### Quick check santé repo (à lancer après CHAQUE merge)

```bash
cd /root/workspace/digital-humans-production/backend
. venv/bin/activate

# 1. No F821 / F401 regression
ruff check --select F821,F401 --exclude venv,__pycache__,tests,migrations . 2>&1 | grep -E "^F(821|401)" | wc -l
# Must be 0

# 2. All 11 agents importable
python -c "
from agents.roles.salesforce_qa_tester import generate_test
from agents.roles.salesforce_data_migration import generate_build as aisha
from agents.roles.salesforce_developer_apex import generate_build as diego
from agents.roles.salesforce_developer_lwc import generate_build as zara
from agents.roles.salesforce_admin import generate_build as raj
print('✅ All 5 BUILD agents importable')
"

# 3. Registry loaded (after B-1 mergé)
python -c "
from app.services.agents_registry import list_agents
assert len(list_agents()) == 11
print('✅ Registry 11 agents')
" 2>/dev/null || echo "⏳ B-1 not merged yet"

# 4. LLM routing (after C-1 mergé)
python -c "
from app.services.llm_router_service import get_llm_router
r = get_llm_router()
assert 'cloud' in r.config.get('profiles', {})
print('✅ LLM profiles configured')
" 2>/dev/null || echo "⏳ C-1 not merged yet"

# 5. RAG health
python -c "
from app.services.rag_service import get_stats
s = get_stats()
print(f'RAG chunks: {s.get(\"total_chunks\", 0)}')
"

# 6. Test suite smoke
pytest tests/session3_regression/ -m "agent_a_smoke or agent_b_smoke or agent_c_smoke or agent_d_smoke" -q --tb=no
```

### DoD final (avant E2E #146)

```bash
# Full regression passes
pytest tests/session3_regression/ -q

# Cross-team integration
pytest tests/session3_regression/cross/ -q

# Lint clean
ruff check --select F821,F401 --exclude venv,tests . | wc -l    # == 0

# No backup files, no hardcoded paths, no dead code
pytest tests/session3_regression/agent_d/ -q

# All 3 profiles routable
for p in cloud on-premise freemium; do
  DH_DEPLOYMENT_PROFILE=$p pytest tests/session3_regression/agent_c/test_llm_router_profiles.py -q
done

# Changes log
cat CHANGELOG.md | head -50
```

---

## 7. Risk register

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| **A-7 P0 execution_routes casse le streaming SSE** | Moyenne | Haut | Tester avec 3+ subscribers SSE après fix. Allowlist manuelle dans `test_no_sync_in_async.py`. |
| **B-2 migration casse un alias en prod** | Moyenne | Haut | Test alias resolution exhaustif (voir `test_alias_resolution.py`). Recenser tous les callers avant refactor. |
| **C-0 suppression `LLMService` casse un caller oublié** | Moyenne | Moyen | `grep -rn "LLMService()"` exhaustif avant suppression. Période de deprecation (warning) avant suppression finale. |
| **Elena verdict default FAIL casse les E2E antérieurs** | Haute | **Faible** | ✅ Attendu et souhaité — ces E2E étaient faux-verts. Annoncer dans CHANGELOG. |
| **Multi-profile tests nécessitent ollama réel** | Haute | Faible | Mocks uniquement dans CI. POC réel en étape séparée avant vente client. |
| **Merge conflicts entre A et B sur `hitl_routes.py`** | Haute | Moyen | Team B démarre B-2 (hitl migration) **après** les fix A ne touchent plus hitl_routes. Séquentialiser. |
| **Pricing YAML sous-estime les coûts Opus réels** | Haute | Moyen | Vérifier avec Anthropic console au jour 1 et mettre à jour dans le YAML. |
| **Coverage Emma reste à 61% après refonte** | Haute | **Faible** | Hors scope — c'est un problème de qualité prompt Marcus. Note pour chantier suivant. |
| **Tests live E2E #146 consomment budget Anthropic important** | Moyenne | Moyen | Fixer un budget max via `MAX_TOTAL_LLM_CALLS` + monitor en temps réel. |

---

## 8. Procédures de rollback

### Par phase

**Phase 1 (BUILD blockers)** :
- Si le fix Elena casse le comportement antérieur de manière imprévue : `git revert` du commit fix → retour au PASS silencieux (dégradation mais pas blocage)
- Procédure : `git revert <hash A-4>` (retire le no-fail-open, garde les fixes F821)

**Phase 2 (LLM + Registry)** :
- Rollback complet : `git revert` des commits C-0 à C-5 dans l'ordre inverse
- Alternative partielle : env var `DH_DEPLOYMENT_PROFILE=cloud` force le comportement historique cloud-only
- Danger : si `LLMService` V1 est déjà supprimée, rollback ne restaure pas. Garder un tag `legacy/pre-c0-llmservice` avant la suppression

**Phase 3 (P0)** :
- Rollback un par un des async/sync. Chaque commit est isolé par fichier.
- Check avant rollback : `systemctl status digital-humans-backend` — si service up mais event loop freeze → rollback P0 pour ce fichier uniquement

**Phase 4-5** :
- Low risk, rollback standard git

### Snapshot avant refonte

**À effectuer au jour 0, avant d'autoriser un seul merge** :

```bash
cd /root/workspace/digital-humans-production
git tag baseline/pre-session3-refonte
git push origin baseline/pre-session3-refonte

# PG dump
pg_dump digital_humans > /root/backups/pre-refonte-$(date +%Y%m%d).sql

# Code snapshot
tar czf /root/backups/pre-refonte-code-$(date +%Y%m%d).tar.gz \
  --exclude=venv --exclude=node_modules --exclude=.git \
  backend/ frontend/
```

Permet un rollback complet en 2 commandes si nécessaire.

---

## 9. Communication & coordination

### Canaux

- **Repository** : `github.com/SamHATIT/digital-humans-production`
- **Branche pivot** : `main`
- **Branches Agent Teams** : `fix/agent-a-*`, `refactor/agent-b-*`, `feat/agent-c-*`, `chore/agent-d-*`, `test/qa-*`
- **PR template** : chaque PR référence les findings résolus (ex: `Resolves N17a, N17b, N17c`)
- **CHANGELOG.md** : mis à jour à chaque merge

### Daily check (synchrone Sam ↔ Agent Teams)

Chaque matin :
1. Status des phases en cours
2. Blockers inter-teams (chaîne de dépendance section 3)
3. Nouveaux findings découverts (si les Agent Teams trouvent des bugs non listés)
4. Décisions à prendre par Sam (ex: "dead routes SDS V3 : delete or feature flag ?")

### Go/No-Go E2E #146

Réunion fin jour 9 avec tous les Agent Teams :
- QA rapporte le résultat de la suite regression
- Sam valide `GO` si : tous les tests agent_*_smoke passent + tests cross passent + lint clean + docs à jour
- Sinon, jour 10 = correction des blockers, E2E #146 reporté à J11

---

## 10. Livrables consolidés (checklist)

### Code
- [ ] `AUDIT_REPORT_20260418_v3.md` (référence)
- [ ] Team A : ~15 commits sur agents/, services/ (F821, dispatch, P0, P7, P11)
- [ ] Team B : `agents_registry.yaml`, `agents_registry.py`, 4 services migrés, 3 YAML prompts remplis, HITL corrigé
- [ ] Team C : `llm_routing.yaml` refondu, `llm_service.py` réécrit, `llm_router_service.py` profile-aware, `build_enabled.py` middleware, `config.py` route
- [ ] Team D : `app/config.py` enrichi, `logging_config.py`, `execution_context.py` middleware, scripts secrets, backup files supprimés
- [ ] Team QA : suite `tests/session3_regression/` avec 15+ fichiers, CI workflow, pre-commit hooks

### Documentation
- [ ] `CHANGELOG.md` mis à jour
- [ ] `docs/architecture.md` refondu
- [ ] `docs/agents.md` auto-généré depuis registry
- [ ] `docs/deployment.md` multi-profile
- [ ] `docs/ADR-001-llm-strategy.md`
- [ ] `docs/ADR-002-agents-registry.md`
- [ ] `docs/operations/secrets-rotation.md`
- [ ] `docs/testing-strategy.md`
- [ ] `docs/e2e-tests/E2E_146_PLAYBOOK.md`
- [ ] `docs/e2e-tests/E2E_146_RESULTS.md` (après E2E)

### Opérationnel
- [ ] Tag `baseline/pre-session3-refonte` créé
- [ ] PG dump snapshot effectué
- [ ] Secrets rotation script testé
- [ ] Systemd units mis à jour pour `DH_DEPLOYMENT_PROFILE`
- [ ] Health endpoint `/api/config/capabilities` accessible
- [ ] Health endpoint `/api/health/rag` accessible

---

## 11. Post-E2E #146 — prochaines étapes

Si E2E #146 `GO` :
- Release `v3.0.0` tag
- Annonce interne (Notion, Slack)
- Déploiement prod
- Retour à la roadmap produit (HITL, change requests conversationnels, web admin hub — cf. user memory)

Si `NO-GO` :
- Post-mortem 1h avec tous les Agent Teams
- Identification des 2-3 blockers
- Jour 11-12 : correctifs ciblés
- E2E #147 re-run

### Chantiers reportés (backlog post-refonte)

1. **POC réel on-premise** (jalon prioritaire post-E2E #146) — Ollama + Llama 3.3 70B sur VPS test, installation SOP, mesure latences, comparaison qualitative cloud vs on-premise. Prérequis à la vente L'Oréal/LVMH.
2. **P10 BaseAgent class** — unifier les 11 agents avec héritage + mixins
3. **Frontend audit complet** — 11 000 LOC jamais audités exhaustivement
4. **Models audit** — 30 fichiers SQLAlchemy
5. **Centralized web admin hub** (user memory) — monitoring tous services
6. **~~Refonte SDS V3 Mistral PASS 1~~** — abandonné, code supprimé dans Team D (tag `legacy/sds_v3_synthesis_before_removal` si restauration future)

---

*Maître d'œuvre consolidé — plan de refonte session 3 complet.*

*Livrables connexes :*
- `AUDIT_REPORT_20260418_v3.md`
- `BRIEFING_AGENT_A.md` (Backend Bloquants)
- `BRIEFING_AGENT_B.md` (Contracts inter-agents)
- `BRIEFING_AGENT_C.md` (LLM Modernization multi-profile)
- `BRIEFING_AGENT_D.md` (Hygiene & Cleanup)
- `BRIEFING_QA_AGENT.md` (Validation & Regression)
