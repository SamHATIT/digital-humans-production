# PROMPT — AGENT C (LLM Modernization multi-profile)

Tu es **Agent C** dans la refonte session 3 de Digital Humans. Tu es responsable de consolider l'architecture LLM autour de **2 tiers logiques** (`orchestrator` / `worker`) et **3 deployment profiles** (`cloud`, `on-premise`, `freemium`), avec **un seul fichier YAML comme source de vérité**. Tu supprimes la classe `LLMService` V1 héritée, tu rétablis la continuation CRIT-02 dans le Router V3, et tu implémentes le middleware `BuildEnabledMiddleware` qui bloque les endpoints BUILD en mode freemium.

Ton chantier élimine mécaniquement **12 findings** (N21, N22, N23, N28, N31, N33, N35, N41, N42, N43, N45, N86) et réduit ~500 LOC de code dupliqué / dead.

Tu travailles sur le repo `/root/workspace/digital-humans-production/` (VPS Hostinger, branche pivot `main`). Tu partages ce repo avec **3 autres Agent Teams** (A, B, D) et **1 QA Agent**. Ta coordination avec eux passe par `main` et par les GATES définis plus bas.

---

## 1. Contexte global — Maître d'œuvre de la refonte

> Ce qui suit est le plan consolidé qui orchestre les 4 Agent Teams + QA. **Lis-le intégralement avant de commencer**.

### 1.1 Vue d'ensemble

**Ce qu'on résout** : 103 findings répartis sur ~85% du backend, consolidés en 13 chantiers P0-P12. Stratégie : 4 Agent Teams parallèles + 1 QA Agent. Durée cible : 10 jours ouvrés.

**Objectifs business (triplet)** :
1. Ré-activer le BUILD — actuellement cassé silencieusement
2. Fiabiliser le tracking coût — actuellement 4x sous-estimé
3. **Préserver les cas d'usage on-premise / freemium — c'est ton chantier principal**

**Ce qu'on ne fait PAS (reporté)** :
- Refonte BaseAgent (P10)
- Refonte frontend
- Migration complète AsyncSession SQLAlchemy
- POC réel on-premise Ollama — **reporté après E2E #146**

**Décisions Sam actées (2026-04-18)** :
| Décision | Valeur | Impact sur toi |
|----------|--------|----------------|
| Dead routes SDS V3 | Suppression pure et simple | Team D supprime ; tu ne touches pas |
| POC on-premise Ollama | Après E2E #146 | Tests multi-profile via **mocks** uniquement |
| **Prix Opus/Sonnet réels** | **À vérifier J1** | **TON ACTION J1** : consulte Anthropic console, mets à jour `pricing:` dans `llm_routing.yaml` avant merge C-5 |

### 1.2 Agent Teams — périmètres

| Team | Mission | Briefing | Durée |
|------|---------|----------|-------|
| A — Backend Bloquants | P0, P7, P11, P12, F821, BUILD cascade | `BRIEFING_AGENT_A.md` | 4j |
| B — Contracts | agents_registry unique, P9, HITL contracts | `BRIEFING_AGENT_B.md` | 3j |
| **C — LLM Modernization (toi)** | 2 tiers + multi-profile, suppression V1 | `BRIEFING_AGENT_C.md` | 3j |
| D — Hygiene & Cleanup | P2, P5, P8, dead code, secrets, docs | `BRIEFING_AGENT_D.md` | 3j |
| QA — Validation | Suite tests, E2E #146 playbook | `BRIEFING_QA_AGENT.md` | 4j |

### 1.3 Carte des dépendances

```
        ┌──────────────────────────────────────┐
        │ A — Backend Bloquants                │
        └──────┬────────────────────┬──────────┘
               │                    │
               │ alias stable       │ agent_type stable
               ▼                    ▼
┌─────────────────────┐    ┌───────────────────────┐
│ B — Contracts       │    │ C — LLM Modernization │
│                     │    │ (TOI)                 │
│ B-1 agents_registry │    │ C-0 drop LLMService V1│
│ B-2 migrate 4 dicts │    │ C-1 profile router    │
│ B-3 YAML stubs x3   │    │ C-2 fallback chain    │
│ B-4 HITL N91/N92    │    │ C-3 continuation V3   │
└──────┬──────────────┘    │ C-4 build middleware  │
       │                   │ C-5 pricing YAML      │
       │                   └───────┬───────────────┘
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

| Interface | Team producteur | Team consommateur | Stabilisation |
|-----------|-----------------|-------------------|---------------|
| `generate_build()` signatures | A | phased_build, QA | Jour 1 |
| `agents_registry.yaml` schema | B | **C (toi — cross-check tier)**, QA | Jour 2 |
| **`config/llm_routing.yaml` profiles** | **C (toi)** | A (agents appelants), QA | Jour 2 |
| **`generate_llm_response()` signature** | **C (toi)** | A, B | Jour 1 |
| **`/api/config/capabilities`** | **C (toi)** | Frontend, QA | Jour 3 |

### 1.5 Ordre de merge recommandé — les 6 phases

**Phase 1 — Socle BUILD (jours 1-2)** — Team A. **TU PEUX DÉMARRER EN PARALLÈLE** (pas de dépendance).
**Phase 2 — Plomberie LLM + Registry (jours 2-4)** — **TU TRAVAILLES ICI** avec B en parallèle
Commits dans ta branche `feat/agent-c-llm-unified` :
- `C-1` — Nouveau `config/llm_routing.yaml` (format multi-profile)
- `C-1b` — Router `_select_provider` profile-aware + `is_build_enabled` / `get_active_profile`
- `C-0` — Suppression `LLMService` V1 + wrapper mince ⚠️ **GATE** (voir §3)
- `C-3` — Continuation CRIT-02 dans Router V3 `_call_anthropic`
- `C-5` — Pricing depuis YAML (avec prix réels vérifiés sur Anthropic console le J1)

**Phase 3 — P0 async + P7 budget (jours 4-6)** — Team A reprend
**Phase 4 — Middleware + YAML (jours 6-7)** — **TU CONTINUES**
- `C-4a` — `BuildEnabledMiddleware` dans `backend/app/middleware/build_enabled.py`
- `C-4b` — Endpoint `/api/config/capabilities` dans `backend/app/api/routes/config.py`

**Phase 5 — Cleanup (jours 7-9)** — Team D (supprimera `sds_synthesis_service.py`)
**Phase 6 — E2E #146 LIVE (jour 10)** — jalon final

### 1.6 Risk register (extrait — points qui te concernent)

| Risque | Mitigation |
|--------|------------|
| C-0 suppression `LLMService` casse un caller oublié | `grep -rn "LLMService()"` exhaustif avant suppression. Tag `legacy/pre-c0-llmservice` avant `git rm` de la classe. |
| Pricing YAML sous-estime les coûts Opus réels | Vérifier avec Anthropic console au jour 1 |
| Tests multi-profile nécessitent ollama réel | Mocks uniquement dans CI (cf. `fixtures/mock_ollama.py` écrit par QA) |
| Régression fonctionnelle sur Router V3 après continuation port | Test de régression QA `test_router_continuation.py` |

---

## 2. Ta mission spécifique

Tu exécutes le plan détaillé dans `BRIEFING_AGENT_C.md`. **Lis ce briefing intégralement avant de commencer** — il contient le format YAML cible complet, les patches de code pour Router V3, le nouveau module `llm_service.py` en wrapper mince, et la matrice de migration avant/après.

### 2.1 Synthèse de tes 6 chantiers

| TASK | Objectif | Fichier(s) cible | Phase |
|------|----------|------------------|-------|
| **C-1** | Refondre `llm_routing.yaml` en format multi-profile (3 profiles × 2 tiers) | `backend/config/llm_routing.yaml` | 2 |
| **C-1b** | Profile-aware routing dans Router V3 + accesseurs `is_build_enabled` / `get_active_profile` | `backend/app/services/llm_router_service.py` | 2 |
| **C-2** | Fallback chain profile-aware (pas de fallback cloud depuis on-premise/freemium) | même fichier | 2 |
| **C-0** | Suppression classe `LLMService` V1 — remplacée par wrapper mince (~150 LOC au lieu de 752) | `backend/app/services/llm_service.py` réécrit | 2 |
| **C-3** | Port de la continuation CRIT-02 dans Router V3 `_call_anthropic` | même router | 2 |
| **C-4** | `BuildEnabledMiddleware` + endpoint `/api/config/capabilities` | `backend/app/middleware/build_enabled.py` (new) + `backend/app/api/routes/config.py` (new) | 4 |
| **C-5** | Pricing lu depuis YAML (avec prix réels vérifiés) | `backend/app/services/budget_service.py` | 2 |

### 2.2 Résultat attendu à la fin de ton chantier

- Changer Opus → Opus 4.8 → Opus 5 = modifier **1 ligne YAML**
- Classe `LLMService` n'existe plus. Plus de `LLMService()` direct dans le code (B-2 et hitl_routes sont déjà migrés par Team B)
- `DH_DEPLOYMENT_PROFILE=cloud|on-premise|freemium` switche tout le routing
- En mode `freemium`, `POST /execute/1/build` retourne **403 `build_disabled`** avec message upgrade
- En mode `on-premise`, si Ollama local down, **pas de fallback cloud** (erreur visible)
- Continuation auto-activée : Marcus peut générer > 16K tokens sans truncation
- `/api/config/capabilities` retourne le profile actif + `build_enabled` pour que le frontend adapte son UI

---

## 3. Tes dépendances — GATES explicites

### 3.1 Ce que tu attends (ne pas commencer avant)

**Aucun prérequis pour C-1 / C-1b / C-2** : tu peux démarrer au jour 1, 9h, en parallèle de Team A.

**GATE C-0 (suppression LLMService V1) ← Team B B-2b et B-2d mergés**

La classe `LLMService` est instanciée directement dans `change_request_service.py` L54 et `hitl_routes.py` L266. Team B va supprimer ces bypass (N45, N86) dans B-2b et B-2d. **TU NE DOIS PAS SUPPRIMER `LLMService`** avant que B-2b et B-2d soient mergés sur main, sinon le code de B casse.

**Check avant C-0** :
```bash
grep -rn "LLMService()" backend/app --include="*.py" | grep -v "# deprecated" | grep -v "llm_service.py"
# Doit être vide (ou uniquement du code que tu contrôles)
```

Si B-2b et B-2d ne sont pas encore mergés au moment où tu veux faire C-0, fais tes autres TASKs (C-3, C-5) d'abord et garde C-0 pour la fin.

**GATE C-5 (pricing from YAML) ← A-9 (budget_service.record_cost commit)**

Les deux touchent `budget_service.py`. Si A-9 merge d'abord (commit par défaut), tu rebases et adaptes la signature de `record_cost` pour accepter `provider_str` au lieu de `model`. Si C-5 merge d'abord, A-9 adapte.

### 3.2 Ce que tu dois livrer pour les autres (GATES SORTIE)

- **À fin de C-1 (jour 2 matin)** : signaler que `llm_routing.yaml` schema est stable → QA peut écrire `test_llm_router_profiles.py`.
- **À fin de C-1b (jour 2 après-midi)** : signaler que le Router V3 expose `is_build_enabled()` → QA peut préparer `test_middleware_build_disabled_freemium.py`.
- **À fin de C-4 (jour 3)** : signaler que `/api/config/capabilities` est disponible → frontend team peut commencer l'adaptation UI, QA écrit le test.

### 3.3 Fichiers à risque de collision

| Fichier | Tes lignes | Autre team | Lignes autre team | Stratégie |
|---------|-----------|------------|-------------------|-----------|
| `budget_service.py` | MODEL_PRICING L17-31 + pricing function | A (record_cost L112-122) | **Lignes proches** | Coordination : qui merge premier → l'autre rebase |
| `change_request_service.py` | (après C-0, plus de LLMService import) | B (CATEGORY_AGENT_MAP L36-44) | Différentes | Auto-merge probable |
| `hitl_routes.py` | (après C-0, L266 bypass removed via B) | B (AGENT_CHAT_PROFILES + N91/N92) | B gère déjà ces lignes | **Pas de conflit direct pour toi** |
| `llm_service.py` | Réécrit intégralement (C-0) | Personne d'autre | — | Chantier solo |
| `llm_router_service.py` | C-1b / C-2 / C-3 | Personne d'autre | — | Chantier solo |

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
git push origin feat/agent-c-llm-unified
gh pr create --base main --title "C-1: multi-profile YAML llm_routing" \
  --body "Resolves N21, N22, N28, N31, N42, N43. See BRIEFING_AGENT_C.md TASK C-1."
```

### Action J1 matin — Prix Opus/Sonnet

**AVANT** d'écrire le YAML `pricing:` section, **vérifie les prix réels sur Anthropic console** :
1. Connecte-toi à `console.anthropic.com/settings/billing`
2. Note les prix `input` et `output` par 1M tokens pour :
   - Claude Opus (dernière version disponible — actuellement 4.6 ou plus récent)
   - Claude Sonnet (dernière version)
3. Mets ces prix dans `llm_routing.yaml > pricing:` **avant** de merger C-1

Valeurs de référence (à confirmer) : Opus input ~15$/1M, output ~75$/1M. Sonnet input ~3$/1M, output ~15$/1M.

### Synchronisation avec Team B

Au jour 2 matin : pull main et vérifier que B-1 (registry) est mergé. Si oui, tu peux intégrer un cross-check dans Router V3 : pour chaque agent dans `agents_registry.yaml`, son `tier` (orchestrator/worker) doit exister dans chaque profile.

---

## 5. Démarrage

```bash
# 1. Positionne-toi sur le repo
cd /root/workspace/digital-humans-production

# 2. Vérifie le tag baseline
git tag -l "baseline/pre-session3-refonte"

# 3. Pull main
git fetch origin && git checkout main && git pull origin main

# 4. Crée ta branche
git checkout -b feat/agent-c-llm-unified

# 5. Lis intégralement ton briefing
cat docs/audits/session3_20260418/BRIEFING_AGENT_C.md

# 6. Consulte aussi le rapport d'audit
cat docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md

# 7. Active l'environnement
cd backend && . venv/bin/activate

# 8. Inventaire actuel
echo "--- Fichier llm_routing.yaml actuel ---"
wc -l config/llm_routing.yaml
echo "--- Fichier llm_service.py actuel ---"
wc -l app/services/llm_service.py
echo "--- Callers LLMService() ---"
grep -rn "LLMService()" app --include="*.py" | grep -v llm_service

# 9. **Action J1 matin** : prix Anthropic
echo "→ Consulte console.anthropic.com/settings/billing"
echo "→ Note input/output prices pour Opus et Sonnet"
echo "→ Les utiliser dans llm_routing.yaml pricing: section"

# 10. Démarre par TASK C-1 (YAML + Router V3 profile-aware)
```

---

## 6. Règles de coordination

- **Atomic commits** : 1 TASK = 1 commit. Message type : `C-1: multi-profile YAML llm_routing (N21, N22, N42)`
- **CHANGELOG.md** : entry par TASK avec la liste des findings résolus
- **PR references** : `Resolves N21, N22, N23, N28, N31, N33, N35, N41, N42, N43, N45, N86` (progressif selon les TASKs)
- **Tests post-merge** : `pytest tests/session3_regression/agent_c/ -m agent_c_smoke` après chaque merge
- **Tag avant C-0** : `git tag legacy/pre-c0-llmservice` avant suppression définitive de la classe
- **Pas de rupture backward compat agent** : `generate_llm_response(agent_type="...")` reste la même signature publique pour les agents

### Ce que tu ne fais PAS

- **Ne touche pas** aux agents eux-mêmes (salesforce_*.py) — scope A (F821) + B (PROMPT_SERVICE)
- **Ne touche pas** aux 6 dicts de mapping agent — scope B (registry)
- **Ne supprime pas** les backup files ni les routes SDS V3 orphelines — scope D
- **Ne modifie pas** `phased_build_executor.py` — scope A-4
- **Ne crée pas** de nouveau provider (ex: Mistral API hosted, Groq) — hors scope. Les providers actuels (Anthropic, Ollama local, OpenAI désactivé) suffisent.
- **N'installe pas** Ollama réellement sur le VPS — POC reporté post-E2E #146. Tests multi-profile via mocks.

---

## 7. Fin de mission — DoD personnel

Tu as terminé ta mission quand **tous** ces critères sont verts :

```bash
cd /root/workspace/digital-humans-production/backend && . venv/bin/activate

# 1. Classe LLMService supprimée
grep -n "^class LLMService" app/services/llm_service.py && echo "FAIL: still present" || echo "OK: removed"

# 2. Pas de bypass direct
grep -rn "LLMService()" app --include="*.py" | grep -v llm_service.py | grep -v "# deprecated" | wc -l    # == 0

# 3. YAML charge 3 profiles
python -c "
from app.services.llm_router_service import get_llm_router
r = get_llm_router()
for p in ('cloud', 'on-premise', 'freemium'):
    assert p in r.config['profiles'], f'{p} missing'
    assert 'orchestrator' in r.config['profiles'][p]
    assert 'worker' in r.config['profiles'][p]
print('OK')
"

# 4. Routing cloud → anthropic
DH_DEPLOYMENT_PROFILE=cloud python -c "
from app.services.llm_router_service import get_llm_router, LLMRequest
r = get_llm_router()
p = r._select_provider(LLMRequest(prompt='', agent_type='marcus'))
assert p.startswith('anthropic/'), f'got {p}'
print('OK')
"

# 5. Routing on-premise → local
DH_DEPLOYMENT_PROFILE=on-premise python -c "
from app.services.llm_router_service import get_llm_router, LLMRequest
r = get_llm_router()
p = r._select_provider(LLMRequest(prompt='', agent_type='marcus'))
assert p.startswith('local/'), f'got {p}'
print('OK')
"

# 6. Freemium bloque BUILD
DH_DEPLOYMENT_PROFILE=freemium python -c "
from app.services.llm_router_service import get_llm_router
assert get_llm_router().is_build_enabled() is False
print('OK')
"

# 7. Endpoint capabilities
curl -s http://localhost:8002/api/config/capabilities | python -m json.tool

# 8. Pricing YAML avec prix réels
python -c "
from app.services.budget_service import MODEL_PRICING
assert 'anthropic/opus-latest' in MODEL_PRICING
assert MODEL_PRICING['anthropic/opus-latest']['output'] >= 50.0, 'pricing looks too low for Opus'
print('OK')
"

# 9. Continuation CRIT-02 présente
grep -n "stop_reason.*max_tokens" app/services/llm_router_service.py | head    # doit trouver la logique

# 10. Tests C passent
pytest tests/session3_regression/agent_c/ -m agent_c_smoke -q

# 11. PR toutes mergées
gh pr list --author "@me" --state merged --base main | grep -c "C-"    # >= 6
```

Quand c'est tout vert, notifie Sam + QA Agent avec un commit sur main : `C: mission complete - 6/6 tasks merged, multi-profile active, ready for E2E #146`.

---

## 8. Ressources

- **Briefing détaillé** : `docs/audits/session3_20260418/BRIEFING_AGENT_C.md`
- **Rapport d'audit complet** : `docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md`
- **Plan d'orchestration** : `docs/audits/session3_20260418/MAITRE_OEUVRE_PLAN.md`
- **Tests à écrire pour toi** : `docs/audits/session3_20260418/BRIEFING_QA_AGENT.md` (§4.3)
- **Repo** : `/root/workspace/digital-humans-production/`
- **Stack** : FastAPI + PostgreSQL + ChromaDB + Redis/ARQ + Ollama (off par défaut)

Bonne mission Agent C. 🔀
