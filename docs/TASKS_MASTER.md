# TASKS MASTER — vue unique des tâches Digital Humans

> **▶ PROCHAINE ACTION (8 juin)** : Sam crée les 3 projets R&D (Pipeline Tuner / Grid Foresight / Omnichannel Loop) — brief dans `business_requirements` (le wizard studio Acte II le fait déjà correctement). Puis Claude enchaîne le **batch Vague 2** (TEST-4-PARALLEL + EX3 Télécom + EX4 Retail + re-run 148 + publish 155) = preuve finale STREAM-001 / Elena-timeout.

**Généré** : 2026-06-06 — consolidation factuelle (audit croisé docs ↔ git ↔ DB ↔ working tree).
**Vocation** : remplacer le suivi éclaté (BACKLOG.md, 2× STATUS.md, NEXT_SESSION_TODO, SESSION_NEXT_TODO, 4× TODO_*, PROGRESS.log) par une source unique.
**Méthode statut** : ✅ vérifié fait · 🟡 partiel / à valider · ❌ à faire · ⚠️ incohérence détectée.

---

## ✅ FAIT — session 8 juin 2026

**Vague 1 — toutes mergées `main` + déployées** (push `20dc447`, /health 200) : ELENA-TIMEOUT-001, JORDAN-PROMPT-001, AGENT-FK-001, BR-FOOTGUN-FIX (garde-fou), MOD40-CAPABILITY, COST-001, DEADCODE-BACKUPS. GIT-CLEANUP-001 préparé (script ; Sam lance `--apply`).
**Data** : backfill `agent_id` (554 lignes legacy, 35 system NULL) ✅ · MOD40 activé en `warn` ✅.
**Routage modèle / free tier** (push `67facb4`) : free → **Sonnet** (Sophie+Olivia), **Opus réservé au payant** (Marcus dès Pro, Team plein) — `tier_overrides.free` cloud, vérifié via `_select_provider`. Profil `freemium` : **Haiku éliminé** (worker→Sonnet, repli no-op). Chat in-app `sophie_chat_service` passe le `subscription_tier` du user (free→Sonnet live). Concierge public : déjà Sonnet.
**Site marketing** : bundle mod41 — bullet free « Haiku 4.5 model » → « Sonnet 4.6 model » (EN+FR), live (`GOOD-mod41-free-sonnet`).
**Repo** : STREAM-001 mergé+déployé (`04ea3c5`) · mods 37-39 commités · display_name YAML 4.7→4.8 corrigé · DOCBUILD-VERIFYPAGE corrigé (`b2a7478`).

---

## 0. ÉCARTS DE STATUT DÉTECTÉS (à arbitrer en priorité)

### A. Marqué « à faire » alors que c'est FAIT
- ⚠️ **P10 BaseAgent** — BACKLOG le classe en "P2 dette, sprint post-launch". Réalité : **fait**, commit `258c5c3`, tag `v2026.05-p10-baseagent`. → corriger BACKLOG.
- ✅ **Galerie Télécom — correction (8 juin)** : l'exec 144 que j'avais citée date de **février, AVANT la refonte des agents** → artefact legacy, non représentatif du système actuel, inutilisable pour la galerie. Le BACKLOG avait raison : Télécom nécessite une vraie exécution post-refonte (cf. EX3 ci-dessous). Premier SDS post-refonte = LogiFleet (146).
- ⚠️ **SDS Claim Resolver (exec 155)** — absent de tous les docs (postérieur). Réalité : **COMPLETED le 31/05** (canary $9.75/40min). SDS entier non tracké, marqué "bientôt" sur le site live alors qu'il est prêt.

### B. Travail récent NON COMMITÉ / NON POUSSÉ — risque de perte (priorité absolue)
- ⚠️ **`main` jamais poussé** : `origin/main` a 5 semaines de retard. 4 commits locaux non poussés (P10 BaseAgent + tag, tuning ARQ, studio 3-col, helper P3).
- ⚠️ **Mods 37-39 dans l'arbre de travail, non commités** : `budget_service.py`, `llm_router_service.py`, `llm_service.py`, `llm_routing.yaml` (datés 31/05, commentaires mod38/mod39). La mémoire les dit "completed" mais ils ne sont **pas** commités.
- ⚠️ **Mod 31 marketing** (`dh-mod31-hero-shorten.py`) non suivi par git.

### C. Marqué « fait » mais en réalité PARTIEL / à valider
- 🟡 **REVISION-001 patch mode** — code fait, validation E2E en attente (cf. REVISION-001-WORKER : restart worker+backend requis).
- 🟡 **SDS templating Phase 1** — marquée CLOSE, mais `docs/sds/STATUS.md` garde une checklist de tests fonctionnels non cochés (bascule Emma write_sds, preview frontend, robustesse multi-exec). De facto sans doute couverts par exec 148/155 mais jamais validés formellement.
- 🟡 **feat/sds-templating** — STATUS SDS attend "merge + tag v2.0-sds-db-driven" ; branche encore présente. Confirmer si mergée (probable) puis tag + cleanup.

### D. Incohérences de contenu
- ⚠️ **`llm_routing.yaml` ligne ~166** : `model_id: claude-opus-4-8` mais `display_name: "Claude Opus 4.7"`. Le display_name doit suivre le model_id (principe SSoT).
- ⚠️ **`refonte/STATUS.md`** : en-tête dit "consolidation main" mais le pied "Environnement" dit encore `Branche: feature/docs-refonte`.

---

## 0bis. ⚠️ INCIDENT RÉSOLU + À DURCIR (8 juin)

- 🔴 **WORKER-DOWN (cause racine du "0 BR depuis 155")** : le worker ARQ (`digital-humans-worker.service`) était **mort depuis le 31 mai 18:12 UTC** (sortie propre, juste après le canary 155 — son dernier job). Aucun job traité pendant 1 semaine → aucune extraction de BR possible sur AUCUN projet. **Relancé le 8 juin** (✅ actif). L'unit a pourtant `Restart=always` → mort restée = probable `systemctl stop` manuel/déploiement. **À durcir** : élucider la cause du stop ; **réactiver le monitoring** (workflow N8N désactivé — un worker mort 1 semaine sans alerte = vrai trou). Ne PAS toucher le worker tant qu'un SDS tourne.
- ✅ **WIZARD-EXEC-TRIGGER** : le wizard studio créait le projet puis allait sur br-validation **sans démarrer d'exécution** → 0 BR. Corrigé (`ProjectWizard.tsx`) : `executions.start()` après création + navigation avec `?executionId=`. Build + déployé sur `/var/www/app-studio` (backup `app-studio.bak-pre-wizard`). Vérifié : exéc 158 (projet 103) → 25 BR extraites.

---

## 1. NOUVELLES TÂCHES (post-2 mai, absentes des docs)

| ID | Prio | Description | Statut |
|----|------|-------------|--------|
| STREAM-001 | 🔴 P0 | `_call_anthropic` en **streaming** (remplace create()+continuation, fin des raccords corrompus). | 🟡 **mergé main + déployé** (04ea3c5), preuve unit OK (Opus 4.8 32k, stop=end_turn, 0 continuation). Validation finale = batch Vague 2. Suivi mineur : constante MAX_CONTINUATIONS morte. |
| SDS-PIPELINE-TUNER | P1 | Générer SDS Pipeline Tuner. Aucune exec. Brief → `business_requirements` (PAS `description`). | ❌ |
| SDS-GRID-FORESIGHT | P1 | Générer SDS Grid Foresight. Idem. | ❌ |
| SDS-OMNICHANNEL-LOOP | P1 | Générer SDS Omnichannel Loop. Idem. | ❌ |
| BR-FOOTGUN-FIX | P1 | Corriger l'emplacement du brief (`business_requirements`) sur les 3 projets ci-dessus. Footgun : brief dans `description` → 0 BR extraite. | ✅ **garde-fou code posé** (`fix/BR-FOOTGUN-FIX`) : `resolve_brief_text()` dans l'orchestrateur — privilégie `business_requirements` → `requirements_text` → repli `description` (>120 car.) avec WARNING explicite, évite le 0 BR silencieux. Preuve : 5 cas testés OK + WARNING déclenché. NB : la **correction des données** des 3 projets SDS (déplacer le brief en base) reste une mutation DB côté Sam. |
| TEST-4-PARALLEL | P1 | Test d'exécution 4-parallèle. | ❌ |
| MOD40-CAPABILITY | P2 | Resolver de capacités au startup (auto-config params modèle via `GET /v1/models/{id}`, niveaux effort). À faire APRÈS STREAM-001. | ✅ **posé (opt-in)** (`feat/MOD40-CAPABILITY`) : module `capability_resolver.py` (list/latest par famille, `/v1/models/{id}` capabilities → flags, cache disque+TTL, fallback YAML, jamais d'exception) + warmup câblé dans le router, **gate `DH_MOD40_CAPABILITY_RESOLVER`=off/warn/apply** (off par défaut = no-op total). Pas de bascule auto du model_id (seulement WARNING pin obsolète). Preuve : 17 checks unitaires mockés verts (`backend/tests/services/test_capability_resolver.py`) + YAML/py_compile OK. À activer par Sam. — **Activé en `warn`** (backend/.env, 8 juin) : resolver OK, aucun pin obsolète (YAML à jour). Passer en `apply` quand prêt. |
| SDS-148-QA-EMPTY | P2 | SDS Pharma exec 148 : section QA vide (même bug raccord). Différé, non bloquant. | 🟡 |
| SITE-155-PUBLISH | P2 | Publier Claim Resolver (exec 155) sur le site — il est COMPLETED mais affiché "bientôt". | ❌ |

---

## 2. P0 — BLOQUANTS OUVERTURE (inchangés, action humaine Sam)

| ID | Description | Statut |
|----|-------------|--------|
| LEGAL-001 | Validation juriste CGV (300-500€). Boilerplate FR+EN livré. | ❌ Sam |
| LEGAL-002 | Compléter SIRET + adresse siège (placeholders Mentions Légales). | ✅ FAIT (Sam, 8 juin) |
| BIZ-001 | Décision tier Free ouvert/fermé au launch. | ✅ TRANCHÉ : Free **ouvert** au launch |
| STRIPE-PROD-001 | Bascule prod Stripe (`docs/STRIPE_PROD_CHECKLIST.md`) : rotation sk_test→sk_live, recréation produits. | ❌ après BIZ-001 |
| SECURITY-001..005 | Audit secrets + manager (Doppler/Infisical) + migration + bascule services + `docs/SECURITY.md`. Phase 0 NON démarrée. **Note : secret Stripe partagé en chat phase sandbox → rotation obligatoire.** | ❌ |

---

## 3. PLATEFORME / ONBOARDING / GALERIE

| ID | Description | Statut |
|----|-------------|--------|
| ONBOARDING-001/002/003 | Tier-aware, verify-then-create, CTA→wizard pré-rempli. | ✅ (25f226b, 17ee65d, 8aa5e02) |
| STUDIO-S4.1 | Cinématique Théâtre (TheatreStage.tsx). | ✅ (68c3b19) |
| STUDIO-RIM-AGENTS | Sidebar agents rim-only, accent par acte. | ❌ |
| MARKETING-EX2-001 | SDS Pharma (148) sur site marketing. | 🟡 (SDS prêt, page à faire) |
| MARKETING-EX3-001 | SDS Télécom — **à générer** (exec 144 est pre-refonte, inutilisable). Nouvelle exécution post-refonte requise, comme Retail. | ❌ (dépend de STREAM-001 + BR-FOOTGUN) |
| MARKETING-EX4-001 | SDS Retail — pas lancé. | ❌ |

---

## 4. DETTE TECHNIQUE

| ID | Description | Statut |
|----|-------------|--------|
| AGENT-FK-001 | `agent_deliverables.agent_id` NULL depuis exec 142+. Band-aid OUTER JOIN posé (9262a96) ; vrai fix au write site. | ✅ **fix posé** (`fix/AGENT-FK-001`) : nouveau resolver `agent_pk_resolver.resolve_agent_pk(db, key)` (clé/alias → `agents_registry` → name → `agents.id`), branché sur les **2 write sites** (`pm_orchestrator_service_v2._save_deliverable` + `agent_integration._save_agent_deliverable`), fallback None sans régression. Preuve : 13 clés orchestrateur résolues vers un `agents.id` valide (croisé DB live) + py_compile. Band-aid OUTER JOIN conservé pour les 589 lignes historiques (backfill = mutation DB, gate Sam). — **Backfill data fait (8 juin)** : 554 lignes legacy résolues (deliverable_type→agents.id), 35 `system_metadata` laissées NULL (correct). |
| DOCX-OBSOLETE-001 | Supprimer Phase 6 `_generate_sds_document`. | ⚠️ **ANNULÉ** (vérif agent 8 juin) : PAS du dead code — encore câblé au bouton download frontend. Ne pas supprimer. |
| ELENA-TIMEOUT-001 | Timeout 10min Phase 4 marque Elena failed alors que le LLM réussit après. Recouvert par STREAM-001. | 🟡 **fix posé** (`fix/ELENA-TIMEOUT-001`) : STREAM-001 supprime le timeout HTTP interne Anthropic, mais le wrapper externe `asyncio.wait_for(600s)` restait indépendant → experts SDS (qa/data/trainer/devops) passés à 1200s. py_compile OK. Reste : déploiement + validation batch Vague 2 (Sam). |
| JORDAN-PROMPT-001 | Sortie `monitoring.alerting` non contrainte (dict/list selon exec). Template défensif posé ; vrai fix = Pydantic. | ✅ **fix posé** (`fix/JORDAN-PROMPT-001`) : modèle Pydantic `MonitoringSpec` dans `collect_sds.py` normalise `alerting`/checks → `list[str]` (gère dict, list[dict], list[str], scalaire, None, non-dict) ; template `cicd_deployment.html.j2` simplifié (suppression double branche dict/list, `dot_join` symétrique). Preuve : 7 cas de normalisation + parse Jinja + rendu, tous verts. |
| GHOST-001 | SMTP réel (Postmark) pour Ghost + réactiver staffDeviceVerification. | ❌ |
| COST-001 | cost_usd 6-tuple : Marcus/Emma/Olivia ✅ ; reste Aisha/Lucas/Elena/Jordan. | ✅ **fait** (`fix/COST-001`) : `cost_usd` (= `_total_cost`, déjà accumulé via BaseAgent) ajouté aux blocs metadata qui l'omettaient — Elena/spec (673), Aisha/build (500), Jordan/deploy (352). Lucas + modes spec d'Aisha/Jordan l'avaient déjà (vérifié). Tous les blocs de sortie des 4 experts portent désormais `cost_usd` (preuve : scan 7/7 blocs OK + py_compile). |
| BUNDLE-001 | Bundle marketing 16MB, split lazy-load. Perf Lighthouse 25/100. | ❌ |
| P4-FAT-CONTROLLER | `PMOrchestratorServiceV2` = god node n°1 (66 arêtes, Graphify). Non traité. | ❌ |
| UI-002/003/004 | ELAPSED "—", "first take" figé, sidebar chevauche au scroll. | ❌ |
| UX-003/004 | Coverage gaps détaillés ; find()→filter() agents parallèles. | ❌ |

---

## 5. HYGIÈNE REPO & DOC (issu Graphify + git)

| ID | Description | Statut |
|----|-------------|--------|
| DEADCODE-BACKUPS | Supprimer `backups_20251219_114242/` (196K, vieux pm_orchestrator_service_v2.py + BuildPhaseService). Scanné par Graphify, pollue le graphe, résidu P1 split-brain. | ✅ **fait** (`chore/DEADCODE-BACKUPS`) : `git rm -r backups_20251219_114242/` (3 fichiers, 196K). Aucune référence code (seulement des mentions descriptives en doc). |
| GIT-CLEANUP-001 | 40+ branches stale (locales `feat/*` mergées + `claude/*` refonte). | 🟡 **préparé** (`chore/GIT-CLEANUP-001`) : inventaire `docs/GIT_CLEANUP_001.md` + script `scripts/git_cleanup_001.sh`. Analyse : 58 branches, **4 mergées dans main = suppression sûre** (feat/platform-studio, feat/stream-001, feature/freemium-realignment, feature/journal-publication) ; 53 non mergées = arbitrage Sam (risque de perte). L'agent n'exécute PAS la suppression (irréversible, non relisible) — script à lancer par Sam (`--apply`, recalcule la liste mergée dynamiquement). |
| DOC-ARCHIVE | Archiver les docs périmés (6 mois) : `NEXT_SESSION_TODO.md`, `SESSION_NEXT_TODO.md`, `docs/TODO_AUDIT_TRACABILITE.md`, `TODO_CORRECTIONS_POST_TEST.md`, `TODO_FIX_METADATA_RAG.md`, `TODO_REFONTE_ARCHITECTURE_V2.md`, `PROGRESS.log`. `docs/BACKLOG_TECH.md` (8 lignes, vide) à supprimer ou remplir. | ✅ **fait** — 7 docs périmés déplacés dans `docs/archives/` (vérifié 8 juin). |

---

## 6. GRAPHIFY — synthèse structurelle (run 2026-06-06, commit 7cc913e, 0 coût LLM)

- 488 fichiers, 9240 nœuds, 13647 arêtes, 605 communautés. HTML viz sautée (>5000 nœuds).
- **God nodes** : User(136), Project(108), Execution(99), ExecutionStatus(77), useLang(77), ExecutionStateMachine(74), **PMOrchestratorServiceV2(66)**, ArtifactService(59), CreditService(56), AgentDeliverable(55).
- **Bridges (betweenness)** : PhaseStatus, PhaseContextRegistry, User.
- A confirmé : Fat Controller P4 (PMOrchestratorServiceV2), résidu backup Dec 2025.
- Limites : 15% d'arêtes INFERRED (conf. 0.57) à vérifier ; communautés non nommées (pas de passe LLM) ; 3630 nœuds isolés = bruit AST.
- Artefacts : `graphify-out/{graph.json, GRAPH_REPORT.md, manifest.json}`. Rebuild sans coût : `graphify update .`.


---

## 7. DÉCOUVERT pendant la consolidation (2026-06-06)

| ID | Prio | Description | Statut |
|----|------|-------------|--------|
| DOCBUILD-VERIFYPAGE | 🟡 P2 | Le hook post-commit qui rebuild la doc admin **échoue** : `VerifySignupPage` est dans `App.tsx` mais absent de `frontend_pages.yaml` (garde-fou `collect_frontend_pages` → BuildError). La doc admin ne se régénère plus depuis l'ajout de ce composant (onboarding). Fix = enregistrer la page dans `frontend_pages.yaml`. | ✅ **fait** (`b2a7478`) — page enregistrée, hook post-commit rebuild OK (vérifié 8 juin). |

---

## 8. Sujets à explorer / R&D (à reprendre avec Sam)

_Notés le 2026-06-06, à creuser après lecture du document de consolidation._

| ID | Sujet | Notes |
|----|-------|-------|
| RND-REFS (6 juin) | Références vérifiées pour la session R&D | Source primaire « MALFADS » INTROUVABLE (vidéo probablement générée par IA, chiffres 97/95/1,3s non fiables). Pattern réel = LLaMAR (Planner/Actor/Corrector/Verifier, arXiv 2407.10031), MetaGPT, ChatDev, CAMEL, CoALA. Caveats clés : comm O(N²) entre agents (≠ « plus rapide »), mémoire active vs passive (chute 40-60% sur tâches décisionnelles). Mémoire partagée « Team Mind » = piste centrale, recoupe RND-MEMORY-SKILLS. |
| RND-MEMORY-SKILLS | Système de mémoire incrémentale & auto-apprentissage | Analyser comment un agent (Hermes / Claude Code) construit une mémoire incrémentale et **se crée des skills** après avoir résolu un problème (boucle d'auto-apprentissage). À creuser ensemble. |
| RND-MULTIAGENT-4 | MALFADS — multi-agent 4 agents | Multi-Agent LLM Framework for Autonomous Decision Systems : agents Planner / Memory / Execution / Evaluation + principe de « cognitive fragmentation ». Source : vidéo explainer YouTube (LBo40Co4G2k). À faire : retrouver le papier académique original — les chiffres de la vidéo (97% / 95% / 1,3s) sont non vérifiés. |

---

## 9. SESSION 8 juin (PM) — Test boucle d'amélioration Marcus + bugs assemblage SDS (exec 159, projet 103 « Réclamations Télécom »)

**Contexte :** test de la boucle d'amélioration d'architecture (refus de l'archi v1 par Sam) + premier SDS complet de bout en bout. Compte admin = tier **free → tout sur Sonnet** (Marcus inclus). Snapshots disque : `/root/dh_arch_snapshots/{exec159_before,exec159_after,exec159_sds}/` + `BASELINE_compare.json`.

### ✅ Validé (positif)
- **Boucle d'amélioration = ciblage CORRECT.** Comparaison v1 (deliv 728) vs v2 (732) : seules `data_model` + `automation_design` ont changé, **les 10 autres sections byte-identiques**. Marcus ne « refait plus tout ». Patches ciblés (730 data_model, 731 automation_design). v1 préservée (pas écrasée). *L'inquiétude de Sam est levée.*

### 🐞 Bugs confirmés (à corriger) — TOUS de la même famille : troncature JSON par `max_tokens` + parseurs non tolérants

| ID | Prio | Description | Preuve / emplacement | Statut |
|----|------|-------------|----------------------|--------|
| FIX-PARSE-001 | 🔴 P1 | `_parse_raw_markdown_json` renvoie `unrecoverable` sur un JSON tronqué au lieu de fermer les structures ouvertes → sections expert vides alors que le contenu existe en base. **Le plus rentable + rétroactif.** | `tools/lib/collect_sds.py` (fonction `_parse_raw_markdown_json`, étape « 5 » de récup défaillante). **PROUVÉ** : fermeture des structures récupère Aisha 98,9% (54701/55322) et Elena 98,5% (49493/50240). Fix → **re-render SDS exec 159 remplit Aisha+Elena sans réexécution.** Smoke test = vérifier les 2 sections présentes. | À FAIRE (reco : démarrer par là, branche dédiée) |
| FIX-MAXTOKENS-002 | 🔴 P1 | Specs expert tronquées en fin de JSON car `max_tokens` trop bas / pas de streaming sur ces chemins. Empêche la récidive. | Aisha `salesforce_data_migration.py:341` (=16000), Elena `salesforce_qa_tester.py:642` (=16000). **+ chemin patch archi** : `salesforce_solution_architect.py:574` — ajouter `'patch'` à `max_out = 64000 if mode in (...)` (sinon `else 16000` → troncature data_model patch). Autres `max_tokens=16000` repérés : apex 236/251/454/469, trainer 270, devops 236, admin 263/362, lwc 397/412/577, pm 371. | À FAIRE |
| PATCH-MERGE-001 | 🟠 P2 | Le patch `automation_design` ne renvoie que `flows` (20, ex-30) et **supprime** `apex_triggers`/`scheduled_jobs`/`platform_events` (le merge remplace au lieu de fusionner). | Template `marcus_architect/patch` (`get_patch_prompt`, `salesforce_solution_architect.py:450`) + logique de merge. Imposer le renvoi de la section COMPLÈTE et/ou deep-merge. | À FAIRE |
| FIX-EMPTY-001 | 🟠 P2 | Jordan/DevOps : appel LLM (interaction 1368) renvoie **chaîne vide, 0 token, `success=true`** → deliverable `{raw_markdown: ""}` stocké en silence. | `salesforce_devops.py`. Retry sur réponse vide + échouer bruyamment au lieu de stocker du vide. | À FAIRE |
| FEAT-LANG-001 | 🟠 P2/produit | Brief FR → toutes les specs en EN. Aucune directive de langue transmise aux agents ; template SDS figé `lang="en"`. | Injecter la langue du projet dans les system prompts agents + rendre `lang` dynamique dans `sds_shell.html.j2`. (Elena avait glissé un bout de FR « Ma facture du mois dernier est incorrecte » → le brief FR transparaît mais l'agent rédige EN par défaut.) | À FAIRE |
| OBSERV-001 | 🟡 P3 | Appels Sonnet très longs sans aucun log (WBS = **806 s / 173K tokens**, gap 457s) → indiscernable d'un worker planté (on a failli redémarrer un run sain). | Ajouter un heartbeat log (1 ligne / 30-60s) pendant les appels streaming. + **réactiver le monitoring N8N** (rien n'a détecté la mort du worker la semaine passée). | À FAIRE |
| TIER-PROOF | 🟡 note | Compte admin = free → SDS sur Sonnet (Marcus inclus), sorties énormes/lentes. Pour la vraie démo qualité, **basculer le compte en Team/Enterprise** pour repasser Marcus sur Opus. | — | À FAIRE (Sam) |

**Reco d'enchaînement quand reprise :** FIX-PARSE-001 (+ re-render 159 = preuve) → FIX-MAXTOKENS-002 (racine) → FIX-EMPTY-001 / PATCH-MERGE-001 → FEAT-LANG-001. Ne rien éditer pendant qu'une exécution tourne.

**Non-bug noté :** « Diagram render error » dans le monitor = chunk périmé après mon déploiement studio (ancien `flowDiagram-…-C9tKmZNI.js` supprimé). Fix utilisateur = **Ctrl+Shift+R**. Pas de tâche.

**Réf. preuves :** exec 159 ; deliverables 728 (sol v1) / 732 (sol v2) / 741 (Aisha 55K) / 743 (Elena 50K) / 744 (Jordan vide 424o) / 745 (SDS assemblé HTML 377K) ; llm_interactions 1364 (wbs 806s) / 1365 (aisha) / 1367 (elena) / 1368 (jordan 0 token).
