# AGENT RUN REPORT — Vague 1 (correctifs)

**Agent** : Claude Code (exécution autonome)
**Date** : 2026-06-08
**Périmètre** : Vague 1 — lanes A, B, C, E, et D (sauf bug light-mode, gardé pour Sam).
**Environnement** : conteneur cloud (clone frais). Pas de backend/venv/.env local ;
preuve via `py_compile`, tests unitaires mockés, builds frontend réels, et lectures
read-only de la DB/prod via MCP VPS. Aucune mutation prod, aucun run SDS payant, aucun
merge effectué par l'agent.

**Convention** : une branche + une PR par tâche, vers `main`. Aucune n'est mergée
(gate orchestrateur + Sam). STREAM-001 non retouché (déjà mergé).

---

## ✅ PRs ouvertes (8) — toutes avec preuve testée

| # PR | Branche | Tâche | Lane | Statut | Preuve |
|------|---------|-------|------|--------|--------|
| 1 | `fix/ELENA-TIMEOUT-001` | ELENA-TIMEOUT-001 | A | fait (code) | py_compile + analyse |
| 2 | `fix/JORDAN-PROMPT-001` | JORDAN-PROMPT-001 | A | fait | 7 cas normalisation + parse Jinja + rendu |
| 3 | `fix/AGENT-FK-001` | AGENT-FK-001 | A | fait | 13 clés → agents.id (croisé DB live) + py_compile |
| 4 | `fix/BR-FOOTGUN-FIX` | BR-FOOTGUN-FIX | A | fait (garde-fou) | 5 cas + WARNING + py_compile |
| 5 | `feat/MOD40-CAPABILITY` | MOD40 | A | fait (opt-in, off par défaut) | 17 checks unitaires mockés + YAML + py_compile |
| 6 | `fix/COST-001` | COST-001 | A | fait | scan 7/7 blocs metadata + py_compile |
| 7 | `chore/DEADCODE-BACKUPS` | DEADCODE-BACKUPS | E | fait | git rm 3 fichiers, 0 réf code |
| 8 | `chore/GIT-CLEANUP-001` | GIT-CLEANUP-001 | E | préparé (script, non exécuté) | bash -n + dry-run = 4 branches sûres |

### Détails par PR

**PR #1 — ELENA-TIMEOUT-001 (Lane A)**
Vérification : le streaming (STREAM-001) supprime le timeout HTTP *interne* d'Anthropic
(cause d'origine), mais le wrapper *externe* `asyncio.wait_for(600s)` dans
`_execute_agent_via_import` restait indépendant et coupait Elena à 600s. Experts SDS
(`qa/data/trainer/devops`) passés à **1200s** (cohérent architect=900 / Emma=3600).
Reste : déploiement + validation batch (Sam).

**PR #2 — JORDAN-PROMPT-001 (Lane A)**
Modèle Pydantic `MonitoringSpec` (`tools/lib/collect_sds.py`) normalise
`monitoring.alerting` (+ checks) en `list[str]` quelle que soit la forme émise (dict /
list[dict] / list[str] / scalaire / None / non-dict). Template `cicd_deployment.html.j2`
simplifié (suppression de la double branche défensive `is mapping`).

**PR #3 — AGENT-FK-001 (Lane A)**
Nouveau `agent_pk_resolver.resolve_agent_pk(db, key)` : clé/alias → `agents_registry` →
nom → `agents.id`, fallback None (jamais d'exception). Branché sur les 2 write sites
(`pm_orchestrator_service_v2._save_deliverable`, `agent_integration._save_agent_deliverable`).
Band-aid OUTER JOIN conservé pour les **589** lignes historiques NULL (backfill =
mutation DB, gate Sam).

**PR #4 — BR-FOOTGUN-FIX (Lane A)**
`resolve_brief_text()` : `business_requirements` → `requirements_text` → repli
`description` (≥120 car.) avec WARNING explicite, évite le 0 BR silencieux. NB : la
correction des **données** des 3 projets SDS reste une mutation DB côté Sam.

**PR #5 — MOD40 (Lane A)**
`capability_resolver.py` (résolution `/v1/models` + `/v1/models/{id}` capabilities,
cache+TTL, fallback YAML, ne lève jamais) + warmup câblé dans le router, **gate
`DH_MOD40_CAPABILITY_RESOLVER` = off (défaut) | warn | apply**. Off = no-op total.
Jamais de bascule auto du model_id (WARNING seulement). À activer par Sam.

**PR #6 — COST-001 (Lane A)**
`cost_usd` (= `_total_cost`, déjà accumulé via BaseAgent) ajouté aux blocs metadata qui
l'omettaient : Elena/spec, Aisha/build, Jordan/deploy. Lucas + modes spec d'Aisha/Jordan
l'avaient déjà (vérifié). Tous les blocs de sortie des 4 experts portent désormais `cost_usd`.

**PR #7 — DEADCODE-BACKUPS (Lane E)**
`git rm -r backups_20251219_114242/` (3 fichiers, 196K). Aucune référence code.

**PR #8 — GIT-CLEANUP-001 (Lane E)**
`docs/GIT_CLEANUP_001.md` + `scripts/git_cleanup_001.sh` (dry-run par défaut, `--apply`
avec confirmation, ne supprime que les branches recalculées mergées). 58 branches → 4
sûres. **Suppression non exécutée** (irréversible, non relisible) — script pour Sam.

---

## 🟡 Lane B — Finalisation SDS templating (investigué)

- **merge `feat/sds-templating` + tag `v2.0-sds-db-driven`** → **gate Sam** (non fait,
  conforme au brief). La branche n'est PAS mergée dans `origin/main` (vérifié).
- **DOCX-OBSOLETE-001** : ⚠️ **PAS un dead code mort**. `_generate_sds_document` est
  encore appelé en Phase 6 (`pm_orchestrator_service_v2.py:2923`) et alimente
  `execution.sds_document_path`, **consommé par le bouton de téléchargement frontend**
  (`/api/pm-orchestrator/execute/{id}/download`, `execution_routes.py:405` ;
  `ExecutionMonitoringPage.tsx:199 canDownload`). Le supprimer casserait le download.
  → Recommandation : décision produit (basculer le download vers le SDS HTML `build_sds`)
  avant suppression. **Non fait** (risque + intention produit requise).
- **Supprimer `.bak.*`** : aucun fichier `.bak*` suivi par git (`git ls-files | grep .bak`
  = vide). **Rien à faire.**
- **rename `raw_markdown` → `raw_html`** : cross-cutting et **risqué** — la clé est
  écrite par les agents ET lue par tous les collectors (`collect_sds.py`), ET les
  deliverables **déjà stockés en base** utilisent `raw_markdown`. Un rename dur casserait
  la lecture de l'historique. → Recommandation : si fait, prévoir une lecture tolérante
  (accepter les deux clés) + migration. **Non fait** (gate Sam, touche données stockées).
- **guard Annexe A (`<!DOCTYPE`)** : seul `<!DOCTYPE` trouvé = ligne 1 du shell
  (`sds_shell.html.j2`). Pas de section « Annexe A » identifiable embarquant du HTML brut.
  → Spécification ambiguë : à préciser avec Sam.
- **valider `build_sds` via API/navigateur** : nécessite backend + DB (indisponibles dans
  ce conteneur). Le rendu des filtres/template a toutefois été prouvé (cf. PR #2).

---

## 🟡 Lane C — Plateforme UI (sites localisés, non modifiés)

Le conteneur n'a pas de navigateur ; la « preuve testée » se limiterait à un build (pas
de vérification visuelle). Comme ces correctifs touchent au rendu/à l'intention produit,
ils ne sont **pas** modifiés à l'aveugle. Sites exacts identifiés pour exécution rapide :

- **UX-004 (find()→filter() agents parallèles)** : `ExecutionMonitoringPage.tsx:121`
  `activeAgentFrom()` fait `agent_progress.find(isAgentActive)` → ne retient qu'**un**
  agent alors que la Phase 4 lance 4 experts en parallèle. Le « Théâtre » est conçu
  autour d'**un** protagoniste : passer à `filter()` implique un choix UI (afficher
  plusieurs actifs / un ensemble) → décision produit.
- **UI-002 (ELAPSED « — »)** : composants `ExecutionMetricsStudio.tsx`,
  `ExecutionMonitoringPage.tsx`. À tracer : calcul elapsed quand `started_at` est présent
  mais l'agent en cours non terminé.
- **UI-004 (sidebar chevauche au scroll)** : `ChatSidebar.tsx` / `ChatSidebarStudio.tsx`
  (positionnement sticky/fixed au scroll).
- **UI-003 (« first take » figé)**, **UX-003 (coverage gaps détaillés)**,
  **STUDIO-RIM-AGENTS** : nécessitent maquette/intention visuelle.

> Recommandation : traiter en session frontend dédiée avec dev server + revue visuelle
> (le toolchain build est OK : `npm install` puis `npm run build` passent au vert dans ce
> conteneur — utile pour la CI/preuve de non-régression de type).

---

## 🟡 Lane D — Marketing / site

- **BUNDLE-001** : la tâche vise le **bundle marketing 16 MB**. Le seul projet front du
  repo est `frontend/` (app-studio), dont le build produit ~4 MB (plus gros chunk
  `ExecutionMonitoringPage` 927 kB). Le site marketing 16 MB ne semble **pas** dans ce
  repo (probablement servi séparément sur le VPS). → À confirmer l'emplacement avec Sam
  avant d'optimiser. Optimisation de l'app-studio = tâche distincte (non demandée).
- **Transcréation FR (skill `dh-fr-copywriting`)** : nécessite le **copy source** à
  transcréer (page/section précise). À pointer par Sam.
- **Brouillon LinkedIn** : ✅ livré — `docs/marketing/LINKEDIN_LAUNCH_DRAFT.md`
  (3 variantes + notes). À valider (ton, claims, visuel, galerie M1).
- **Bug light-mode** : **sauté** (attend la spec de Sam, conforme au brief).

---

## Garde-fous respectés
- Aucun merge, aucun push sur `main`, aucune suppression de branche distante.
- Aucune rotation de secret, aucun Stripe prod, aucun run SDS payant, aucune mutation DB.
- Cœur LLM/orchestrateur : seules des modifications **opt-in / additives / défensives**
  (ELENA timeout, MOD40 gate-off, garde-fou BR, resolver FK) — préparées pour relecture Sam.
- DB live : **lectures seules** uniquement (table `agents`, comptes de NULL) via MCP VPS.

## Prochaines étapes suggérées (Sam / orchestrateur)
1. Relire + merger les PRs Lane A (#1–#6) puis déployer ; lancer le batch Vague 2 comme preuve.
2. Lane B : merger `feat/sds-templating` + tag `v2.0-sds-db-driven` ; trancher DOCX-OBSOLETE
   (download → HTML) et le rename `raw_markdown`.
3. Session frontend dédiée pour Lane C (sites déjà localisés ci-dessus).
4. Confirmer l'emplacement du bundle marketing (BUNDLE-001) + fournir le copy source FR.
