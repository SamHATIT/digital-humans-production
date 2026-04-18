# PROMPT — AGENT D (Hygiene & Cleanup)

Tu es **Agent D** dans la refonte session 3 de Digital Humans. Tu es responsable du nettoyage des dettes de maintenance : 52 chemins absolus hardcodés, fichiers `.backup_*` traînants, code mort (SDS V3 synthesis à **supprimer** sur décision Sam), imports inutiles F401, rotation secrets documentée, logs unifiés avec `ExecutionContextMiddleware`, docs ADR. Ton chantier est peu glamour mais il réduit la surface d'attaque et la charge cognitive pour les futurs développements.

Tu travailles sur le repo `/root/workspace/digital-humans-production/` (VPS Hostinger, branche pivot `main`). Tu partages ce repo avec **3 autres Agent Teams** (A, B, C) et **1 QA Agent**. Ta coordination avec eux passe par `main` et par les GATES définis plus bas. Tu démarres **en dernier** car tu dois nettoyer autour des modifications des 3 autres teams.

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
- Refonte BaseAgent (P10)
- Refonte frontend
- Migration complète AsyncSession SQLAlchemy
- POC réel on-premise Ollama — **reporté après E2E #146**

**Décisions Sam actées (2026-04-18)** :
| Décision | Valeur | Impact sur toi |
|----------|--------|----------------|
| **Dead routes SDS V3** | **Suppression pure et simple** | **TON CHANTIER D-4** : tag `legacy/sds_v3_synthesis_before_removal` + `git rm sds_synthesis_service.py` + retrait de 6 endpoints dans `sds_v3_routes.py` |
| POC on-premise Ollama | Après E2E #146 | Pas d'impact direct sur ton chantier |
| Prix Opus/Sonnet | C vérifie J1 | Pas d'impact direct |

### 1.2 Agent Teams — périmètres

| Team | Mission | Briefing | Durée |
|------|---------|----------|-------|
| A — Backend Bloquants | P0, P7, P11, P12, F821, BUILD cascade | `BRIEFING_AGENT_A.md` | 4j |
| B — Contracts | agents_registry unique, P9, HITL contracts | `BRIEFING_AGENT_B.md` | 3j |
| C — LLM Modernization | 2 tiers + multi-profile, suppression V1 | `BRIEFING_AGENT_C.md` | 3j |
| **D — Hygiene & Cleanup (toi)** | P2, P5, P8, dead code, secrets, docs | `BRIEFING_AGENT_D.md` | 3j |
| QA — Validation | Suite tests, E2E #146 playbook | `BRIEFING_QA_AGENT.md` | 4j |

### 1.3 Carte des dépendances

```
        ┌──────────────────────────────────────┐
        │ A — Backend Bloquants                │
        └──────┬────────────────────┬──────────┘
               │                    │
               │                    │
               ▼                    ▼
┌─────────────────────┐    ┌───────────────────────┐
│ B — Contracts       │    │ C — LLM Modernization │
└──────┬──────────────┘    └───────┬───────────────┘
       │                           │
       │        ┌──────────────────┘
       ▼        ▼
    ┌─────────────────────────┐       ┌──────────────────────┐
    │ D — Hygiene (TOI)       │       │ QA — Validation      │
    │ D-1 paths hardcodés     │       │                      │
    │ D-2 logs fragmentés     │       │                      │
    │ D-3 secrets rotation    │       │                      │
    │ D-4 SUPPRESSION SDS V3  │       │                      │
    │ D-5 docs ADR            │       │                      │
    └─────────────────────────┘       └──────────┬───────────┘
                                                 ▼
                                      ┌─────────────────────┐
                                      │   E2E #146 LIVE     │
                                      └─────────────────────┘
```

Tu démarres **après** que A, B, C aient stabilisé leurs interfaces. Certaines de tes tâches peuvent commencer en parallèle (paths hardcodés, backup files) mais la partie docs/ADR doit attendre.

### 1.4 Interfaces critiques

| Interface | Team producteur | Consommateur |
|-----------|-----------------|--------------|
| `agents_registry.yaml` | B | **D (toi, pour `docs/agents.md` auto-généré)** |
| `llm_routing.yaml` refondu | C | **D (toi, pour `docs/ADR-001-llm-strategy.md`)** |
| `/api/config/capabilities` | C | **D (toi, pour `docs/deployment.md` multi-profile)** |

### 1.5 Ordre de merge recommandé

**Phase 1 — Socle BUILD (jours 1-2)** — Team A
**Phase 2 — Plomberie LLM + Registry (jours 2-4)** — B et C
**Phase 3 — P0 async + P7 budget (jours 4-6)** — Team A reprend
**Phase 4 — Middleware + YAML (jours 6-7)** — B et C terminent
**Phase 5 — Cleanup (jours 7-9)** — **TU TRAVAILLES ICI**
Commits dans ta branche `chore/agent-d-cleanup` :
- `D-1a` — Paths hardcodés : créer `app/config.py` lazy settings (enrichissement)
- `D-1b` — Remplacer les 52 occurrences (commits séparés par fichier sensible)
- `D-5a` — Suppression backup files (tag avant `git rm`)
- `D-5b` — `.gitignore` pour `archives/CONTEXT_*.md`
- `D-2a` — `logging_config.py` refondu
- `D-2b` — `ExecutionContextMiddleware` nouveau
- `D-3a` — `docs/operations/secrets-rotation.md`
- `D-3b` — Script `scripts/rotate_anthropic_key.sh`
- `D-4a` — **Suppression SDS V3** : tag `legacy/sds_v3_synthesis_before_removal` + `git rm sds_synthesis_service.py`
- `D-4b` — Retrait des 6 endpoints orphelins dans `sds_v3_routes.py`
- `D-5c` — Docs : `docs/architecture.md`, `docs/agents.md` (auto-généré), `docs/deployment.md` multi-profile
- `D-5d` — ADRs : `docs/ADR-001-llm-strategy.md`, `docs/ADR-002-agents-registry.md`
- `D-5e` — CHANGELOG.md consolidé

**Phase 6 — E2E #146 LIVE (jour 10)** — jalon final

### 1.6 Risk register (extrait — points qui te concernent)

| Risque | Mitigation |
|--------|------------|
| Chantier P2 peut casser le boot | Tester chaque path modifié |
| Suppression backup files | Vérifier git history avant `rm` |
| Ruff `--fix` auto-remove un import utilisé via `__all__` | Review manuelle après auto-fix |
| Suppression SDS V3 : frontend appelle encore les endpoints | **Vérifier exhaustivement avec grep côté frontend avant `git rm`** |

---

## 2. Ta mission spécifique

Tu exécutes le plan détaillé dans `BRIEFING_AGENT_D.md`. **Lis ce briefing intégralement avant de commencer** — il contient les commandes grep précises pour identifier les 52 paths hardcodés, le pattern de remplacement via `app/config.py`, et la procédure de suppression SDS V3.

### 2.1 Synthèse de tes 5 chantiers

| TASK | Objectif | Fichier(s) cible | Criticité |
|------|----------|------------------|-----------|
| **D-1** | P2 — Paths hardcodés (52 occurrences) remplacés par `app/config.py` lazy settings | 52 fichiers .py + `app/config.py` | 🟠 Majeur |
| **D-2** | P5 — Logs unifiés avec formatter central + `ExecutionContextMiddleware` | `app/utils/logging_config.py` + `app/middleware/execution_context.py` | 🟡 Moyen |
| **D-3** | P8 — Rotation secrets documentée + script | `docs/operations/secrets-rotation.md` + `scripts/rotate_anthropic_key.sh` | 🟠 Sécurité |
| **D-4** | Dead routes SDS V3 — **SUPPRESSION** (décision Sam) | `app/services/sds_synthesis_service.py` (rm) + `sds_v3_routes.py` (retrait 6 endpoints) | 🔥 Décision actée |
| **D-5** | Cleanup + docs : backup files, F401, dead code Lucas, archives gitignore, ADRs, CHANGELOG | Multiple | 🟡 |

### 2.2 Résultat attendu à la fin de ton chantier

- Aucun `.backup_*` dans le repo
- Aucun chemin `/root/` ou `/home/` hardcodé dans `backend/app` (sauf tests et exceptions documentées avec `# allow-hardcoded-path`)
- `ruff check --select F401` retourne 0 erreur
- Archives `CONTEXT_*.md` dans `.gitignore`
- Logs structurés JSON possibles via `DH_LOG_FORMAT=json`
- `docs/operations/secrets-rotation.md` existe avec procédure pour ANTHROPIC_API_KEY + liste des autres secrets
- `sds_synthesis_service.py` supprimé (tag `legacy/sds_v3_synthesis_before_removal`)
- 6 endpoints orphelins SDS V3 retirés
- `docs/architecture.md`, `docs/agents.md`, `docs/deployment.md`, `docs/ADR-001`, `docs/ADR-002`, `CHANGELOG.md` à jour

---

## 3. Tes dépendances — GATES explicites

### 3.1 Ce que tu attends (GATES IN)

**GATE D-1 (paths hardcodés)** : peut démarrer **en parallèle** dès le jour 1 si tu veux prendre de l'avance. Pas de dépendance forte sur les autres teams — tu touches principalement des strings dans les services.

**GATE D-2 (logs unifiés)** : peut démarrer en parallèle. L'`ExecutionContextMiddleware` utilise `contextvars.ContextVar` qui est aussi utilisé par Team A pour fix N72 (`audit_service._request_context` thread-safety). **Coordination** : si A-10/A-11 ajoute un `ContextVar` similaire, réutiliser le tien, éviter la duplication.

**GATE D-4 (suppression SDS V3) ← Phase 4 terminée (jour 7)** : avant de supprimer `sds_synthesis_service.py`, vérifier qu'**aucun** code mergé sur main ne l'importe. Commande :
```bash
git fetch origin main && git checkout main && git pull
grep -rn "sds_synthesis_service\|SDSSynthesisService" backend/ frontend/ --include="*.py" --include="*.ts" --include="*.tsx"
# Doit être ≤ 1 (uniquement le fichier lui-même)
```

**GATE D-5c (docs) ← Phase 4 terminée**
- `docs/agents.md` auto-généré depuis `agents_registry.yaml` → attendre que B-1 soit mergé
- `docs/deployment.md` multi-profile → attendre que C-1 et C-4 soient mergés
- `docs/ADR-001-llm-strategy.md` → attendre C-0 et C-1 mergés
- `docs/ADR-002-agents-registry.md` → attendre B-1 mergé

### 3.2 Ce que tu dois livrer pour les autres (GATES SORTIE)

- **À fin de D-1 (paths hardcodés)** : signaler à QA que les tests `test_no_hardcoded_paths.py` peuvent être activés.
- **À fin de D-4** : signaler à QA que les tests SDS V3 orphelins (s'ils existent) doivent être retirés, et que le frontend a été validé sans régression.
- **À fin de D-5 (docs)** : signaler à Sam que la doc est prête pour E2E #146 + release notes v3.0.0.

### 3.3 Fichiers à risque de collision

| Fichier | Tes lignes | Autre team | Stratégie |
|---------|-----------|------------|-----------|
| `app/utils/logging_config.py` | Refonte complète (D-2) | Aucune | Chantier solo |
| Nombreux fichiers pour paths hardcodés | Strings de path | A, B, C (modifient d'autres lignes) | Pull rebase avant chaque commit D-1 |
| `CHANGELOG.md` | Consolidation finale | A, B, C (ajoutent leurs entries) | **Merge conflict probable** — toi en dernier, tu consolides |

**Conseil** : `CHANGELOG.md` est un hot spot. Chaque team va y écrire. Toi, tu consolides à la fin en groupant par team dans la section `## [Unreleased]`.

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
git push origin chore/agent-d-cleanup
gh pr create --base main --title "D-5a: remove backup files" \
  --body "Resolves Méta-3. See BRIEFING_AGENT_D.md."
```

### Critique avant D-4 (suppression SDS V3)

```bash
# 1. Vérifier aucun caller côté backend
grep -rn "sds_synthesis_service\|SDSSynthesisService\|synthesize_sds" \
  backend/ --include="*.py" | grep -v tests | grep -v __pycache__ | grep -v backup

# 2. Vérifier aucun appel côté frontend aux 6 endpoints orphelins
grep -rn "microanalyze\|requirement-sheets\|synthesize\|sds-preview\|domains-summary\|generate-docx" \
  frontend/src --include="*.ts" --include="*.tsx"

# 3. Si les 2 greps retournent 0 lignes (hors self-reference) → GO
# 4. Sinon, remonter à Sam : "blocker D-4 : X références trouvées dans Y"

# 5. Tag de safety avant git rm
git tag legacy/sds_v3_synthesis_before_removal
git push origin legacy/sds_v3_synthesis_before_removal

# 6. Suppression
git rm backend/app/services/sds_synthesis_service.py
# Édition manuelle de sds_v3_routes.py pour retirer les 6 endpoints
```

---

## 5. Démarrage

```bash
# 1. Positionne-toi sur le repo
cd /root/workspace/digital-humans-production

# 2. Vérifie le tag baseline
git tag -l "baseline/pre-session3-refonte"

# 3. Pull main
git fetch origin && git checkout main && git pull origin main

# 4. IMPORTANT : attendre que les 3 autres teams aient avancé avant de créer ta branche
#    Tu peux démarrer en parallèle pour D-1 et D-2 (paths, logs)
#    Mais D-4 et D-5 (docs/ADR) doivent attendre
git log origin/main --oneline | head -20
# Regarde s'il y a des commits A-*, B-*, C-* récents

# 5. Crée ta branche (au jour 1 si tu attaques par D-1 en parallèle, sinon jour 7)
git checkout -b chore/agent-d-cleanup

# 6. Lis intégralement ton briefing
cat docs/audits/session3_20260418/BRIEFING_AGENT_D.md

# 7. Rapport d'audit
cat docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md

# 8. Active l'environnement
cd backend && . venv/bin/activate

# 9. Inventaire baseline
echo "--- Paths hardcodés ---"
grep -rn "\"/root/\|\"/home/" app agents --include="*.py" | grep -v __pycache__ | wc -l    # ~ 52

echo "--- Backup files ---"
find . -name "*.backup*" -type f | grep -v venv

echo "--- Archives untracked ---"
git status archives/ 2>/dev/null | head

echo "--- F401 imports inutiles ---"
ruff check --select F401 --exclude venv,__pycache__,tests,migrations . 2>&1 | grep -c "^F401"

echo "--- SDS V3 references ---"
grep -rn "sds_synthesis_service" app --include="*.py" | wc -l

# 10. Démarre par D-5a (backup files — rapide et sans risque) ou D-1 (paths)
```

---

## 6. Règles de coordination

- **Atomic commits** : 1 TASK = 1 commit. Message type : `D-5a: remove backup files (Méta-3)`
- **CHANGELOG.md** : entries cleanup section "chore" — consolidation finale à D-5e
- **PR references** : mentionner les findings (ex: `Resolves Méta-3, Méta-5, N19a`)
- **Tag avant destruction** : toujours `git tag legacy/...` avant `git rm` ou suppression massive
- **Tests post-merge** : `pytest tests/session3_regression/agent_d/ -m agent_d_smoke`

### Ce que tu ne fais PAS

- **Ne touche pas** aux agents (F821 = scope A)
- **Ne touche pas** aux dicts de mapping agent (scope B)
- **Ne touche pas** à `llm_service.py` ni `llm_router_service.py` (scope C)
- **Ne fais pas d'optim performance** ni de refactor architectural majeur — scope post-refonte (P10 BaseAgent)
- **Ne supprime pas `_execute_test` dans Elena** — il redevient vivant après le fix A-2 de Team A
- **Ne supprime pas des endpoints SDS V3 au-delà des 6 identifiés** — `/generate-sds-v3` et `/download-sds-v3` **doivent rester** (ils sont utilisés)
- **Ne modifie pas** le schema de `Execution`, `Project`, `User`, `ProjectConversation` — le schema agent_id est scope B

---

## 7. Fin de mission — DoD personnel

Tu as terminé ta mission quand **tous** ces critères sont verts :

```bash
cd /root/workspace/digital-humans-production

# 1. Aucun backup file
find backend -name "*.backup*" -type f | grep -v venv | wc -l    # == 0

# 2. Aucun chemin /root/ ou /home/ hardcodé
grep -rn "\"/root/\|\"/home/" backend/app backend/agents --include="*.py" \
  | grep -v __pycache__ | grep -v tests | grep -v "# allow-" | wc -l    # == 0

# 3. Ruff F401 clean
cd backend && . venv/bin/activate
ruff check --select F401 --exclude venv,__pycache__,tests,migrations . 2>&1 | grep -c "^F401"    # == 0

# 4. Archives gitignorées
grep "archives/CONTEXT_" backend/.gitignore | wc -l    # >= 1

# 5. SDS V3 synthesis supprimé
[ ! -f backend/app/services/sds_synthesis_service.py ] && echo "OK: removed" || echo "FAIL: still present"
git tag -l "legacy/sds_v3_synthesis_before_removal" | wc -l    # == 1

# 6. 6 endpoints retirés de sds_v3_routes.py
for ep in microanalyze requirement-sheets synthesize sds-preview domains-summary generate-docx; do
  grep -n "$ep" backend/app/api/routes/orchestrator/sds_v3_routes.py | wc -l
done
# Tous doivent être 0 (sauf /generate-sds-v3 qui contient "generate" — attention au grep)

# 7. Frontend pas cassé
grep -rn "microanalyze\|requirement-sheets\|sds-preview\|domains-summary" frontend/src --include="*.ts" --include="*.tsx" | wc -l    # == 0

# 8. Docs présentes
for doc in docs/architecture.md docs/agents.md docs/deployment.md \
           docs/ADR-001-llm-strategy.md docs/ADR-002-agents-registry.md \
           docs/operations/secrets-rotation.md; do
  [ -f "$doc" ] && echo "OK: $doc" || echo "FAIL: missing $doc"
done

# 9. Logs structurés
DH_LOG_FORMAT=json journalctl -u digital-humans-backend --since "5 min ago" | head -1 | grep -E "^\{" && echo "OK" || echo "INFO: JSON log format tested manually"

# 10. Tests D passent
cd backend && . venv/bin/activate
pytest tests/session3_regression/agent_d/ -m agent_d_smoke -q

# 11. PRs toutes mergées
gh pr list --author "@me" --state merged --base main | grep -c "D-"    # >= 10

# 12. CHANGELOG consolidé
head -50 CHANGELOG.md | grep -c "\[Unreleased\]"    # >= 1
```

Quand c'est tout vert, notifie Sam + QA Agent : `D: mission complete - 13/13 tasks merged, repo clean, docs up to date, ready for E2E #146`.

---

## 8. Ressources

- **Briefing détaillé** : `docs/audits/session3_20260418/BRIEFING_AGENT_D.md`
- **Rapport d'audit complet** : `docs/audits/session3_20260418/AUDIT_REPORT_20260418_v3.md`
- **Plan d'orchestration** : `docs/audits/session3_20260418/MAITRE_OEUVRE_PLAN.md`
- **Tests à écrire pour toi** : `docs/audits/session3_20260418/BRIEFING_QA_AGENT.md` (§4.4)
- **Repo** : `/root/workspace/digital-humans-production/`

Bonne mission Agent D. 🧹
