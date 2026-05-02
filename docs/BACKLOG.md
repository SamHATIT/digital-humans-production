# Backlog — Digital Humans Production

**Dernière mise à jour** : 2026-05-02 (post E2E #144 recovery, exec 148 COMPLETED)

Le suivi détaillé des sessions est dans `CHANGELOG.md`. Ce fichier liste **uniquement
les actions futures** (priorisées par bloquant pour le launch puis dette technique).

---

## P0 — Pre-launch bloquants (côté Sam)

| ID | Description | Notes |
|----|-------------|-------|
| LEGAL-001 | Validation juriste CGV (300-500 €, 1-2h) | Le contenu boilerplate FR+EN est livré (Mod 28), reste à faire valider par un juriste avant ouverture publique. |
| LEGAL-002 | Compléter SIRET + adresse siège | `[À COMPLÉTER]` placeholders dans Mentions Légales actuellement. |
| BIZ-001 | Décision tier Free Studio : ouvert ou "Bientôt" au launch | Si fermé, le bouton "My Studio" du marketing renvoie vers un trou. Si ouvert, /signup est en prod et fonctionne. |

## P1 — Phase 3 finalisation Stripe

| ID | Description | Notes |
|----|-------------|-------|
| STRIPE-001 | Reset crédits mensuel sur `invoice.payment_succeeded` | Webhook handler à étendre dans `stripe_service.py`. |
| STRIPE-002 | Grace period 5j sur `invoice.payment_failed` | Avant downgrade automatique en free. |
| STRIPE-003 | Mod 24 — wiring frontend Stripe | Utile uniquement quand Pro/Team passent de "Bientôt" à actif. |
| STRIPE-004 | Bascule prod Stripe | Rotation secrets test → live + recréation produits live. |

## P1 — Journal publication

| ID | Description | Notes |
|----|-------------|-------|
| JOURNAL-001 | Configurer `JOURNAL_WEBHOOK_SECRET` dans .env | Le webhook code est sur `feature/journal-publication` (commit `8fe4082`). |
| JOURNAL-002 | Configurer le webhook côté Ghost admin | Pointer vers `https://app.digital-humans.fr/api/webhooks/journal/rebuild?secret=...`. |
| JOURNAL-003 | Test endpoint `/webhooks/journal/health` puis `/rebuild` | Vérifier rebuild et /var/www/journal/ généré. |
| JOURNAL-004 | Merger `feature/journal-publication` dans main | Quand stable. |

## P2 — Dettes techniques (post-launch acceptable)

| ID | Description | Notes |
|----|-------------|-------|
| REVISION-001 | Marcus revision via mode `patch` (par section) au lieu de `fix_gaps` (regenere tout) | Code patch déjà écrit dans `salesforce_solution_architect.py:441` (`get_patch_prompt`), pas branché dans `pm_orchestrator_service_v2.py:880-935`. Mapping `CATEGORY_TO_SECTION = {DATA_MODEL → data_model, AUTOMATION → automation_design, UI → ui_components}`. Cause de la régression Rev1→Rev2 documentée E2E #143 (64.8% → 54.8%). |
| COST-001 | Propager `cost_usd` des autres agents (Emma, Olivia, ...) | Marcus déjà fait en feb 14 (commit `7aa5db9`). Reste : Emma, Olivia, Aisha, Lucas, Elena. Capture actuelle ~22% du coût réel. |
| P10 | BaseAgent : contrat commun pour les 11 agents | Pas de classe parent commune actuellement (`_call_llm`/`execution_id`/logging dupliqués). |
| LINT-001 | Nettoyage F541 (56) + F841 (21) + F401 (4) cosmétiques | `ruff --fix --unsafe-fixes` sur app/ + agents/. Risque très faible. |
| BUNDLE-001 | Bundle 16 MB site marketing : split lazy-load post-launch | Dette tech qui bloque le score Lighthouse Performance à 25/100 (les 4 autres scores sont à 100). |

## P2 — UX améliorations restantes

| ID | Description | Notes |
|----|-------------|-------|
| UX-003 | Coverage gaps frontend : afficher description, pas que severity | Frontend lit `gap.severity` mais pas `gap.what_is_missing` ni `gap.fix_instruction`. Vu E2E #143. |
| UX-004 | Active Agent : `.find()` → `.filter()` pour agents parallèles | `ExecutionMonitoringPage.tsx:544`. Permet d'afficher Diego + Zara + Raj simultanément en phase BUILD. |

## P3 — E2E tests

| ID | Description | Notes |
|----|-------------|-------|
| E2E-144 | Lancer E2E #144 | Précédé d'une revue prompt Marcus + Emma (déjà préparée dans `MARCUS_PROMPTS_V4_SPEC.md` et `PROMPT_REWRITE_SPEC_E2E144.md`). Worker actuellement OFF. |
| E2E-145 | Validation patch mode (post-REVISION-001) | Une fois REVISION-001 livré, valider que Rev2 ne régresse plus. |

## P3 — Cleanup git (5 min)

| ID | Description | Notes |
|----|-------------|-------|
| GIT-001 | Supprimer branche locale + remote `feature/tier-based-routing` | Mergée dans main au commit `2f72f5c`. |
| GIT-002 | Statuer sur `feat/platform-studio` | Conserver pour historique Sprint A5 ou supprimer (mergée dans main au commit `8bc569c`). |

---

## Nouveaux items E2E #144 — 2 mai 2026

| ID | Priorité | Description |
|----|----------|-------------|
| REVISION-001-WORKER | P0 prochain E2E | Toujours restart **worker + backend** après patch orchestrator. Le 2 mai, restart backend seul a fait que le worker ARQ a tourné l'ancien code (REVISION-001 HITL pas testé, fallback fix_gaps a tourné à la place). Documenter dans `HOTFIXES_E2E_TEST.md`. |
| AGENT-FK-001 | P1 | Populer `agent_deliverables.agent_id` (FK vers `agents.id`) dans `_save_deliverable` côté pm_orchestrator. Actuellement NULL pour TOUS les deliverables depuis exec 142+. Band-aid OUTER JOIN posé dans `DeliverableService.get_deliverable_previews` (commit `9262a96`), mais le vrai fix est au write site. |
| MARKETING-EX2-001 | P2 | Intégrer un 2e exemple SDS sur le site marketing : "Essais Cliniques E2E" (pharmacovigilance, exec 148). Donne un contraste vertical avec LogiFleet (logistique). Décision format à prendre : (a) HTML statique copié vers `/var/www/dh-preview/sds/exec_148.html` et linké depuis bundle marketing, (b) lien live vers `app.digital-humans.fr/api/deliverables/705/render`. Probablement (a) pour maîtriser l'évolution. À faire après Mod 23 Pricing. |
| DOCX-OBSOLETE-001 | P2 | Supprimer Phase 6 `_generate_sds_document` dans `pm_orchestrator_service_v2.py:2900-2925`. Depuis iter 8, le SDS est rendu en HTML in-app via `tools/build_sds.py` et l'utilisateur peut imprimer en PDF via le navigateur. Le `.docx` généré + populer `executions.sds_document_path` est dead code. |
| ELENA-TIMEOUT-001 | P2 | Le timeout 10-min de Phase 4 a marqué Elena `failed: Skipped: Timeout` à 13:21 alors que son LLM call (118K tokens output) a effectivement réussi 30s plus tard. Soit allonger le timeout pour Sonnet long output, soit cancel le LLM call cleanly pour ne pas orphan le travail terminé. |
| JORDAN-PROMPT-001 | P3 | Prompt Jordan ne contraint pas le format de `monitoring.alerting`. LLM produit alternativement dict (exec 146), clé différente `alerting_thresholds` (exec 147), ou liste (exec 148, qui a planté Phase 5). Template `cicd_deployment.html.j2` rendu défensif (commit `a5ba624`), mais le vrai fix est de Pydantic-valider la sortie Jordan. |
| GHOST-001 | P3 | Configurer un SMTP réel (Mailgun/Postmark) pour Ghost puis réactiver `security__staffDeviceVerification`. Désactivé en hotfix le 2 mai (commit `b728a69`) parce que mail Direct ne livre pas à Gmail, ce qui bloque le reset password Owner. |
| UI-001 | ✅ DONE | "No deliverables found" alors que les deliverables existent. Fix INNER → OUTER JOIN (commit `9262a96`). |
| UI-002 | P3 | ELAPSED affiche toujours `—` même quand l'execution tourne. useEffect manquant probablement. |
| UI-003 | P3 | "first take" reste affiché en sidebar pendant une révision en cours (devrait passer à "revision 1"). |
| UI-004 | P3 | Sidebar (BOX OFFICE / REVISIONS / STATE / ACTS) se chevauche avec le main content au scroll. |

---

## Bugs latents — Status snapshot 1er mai 2026

| ID | Status | Resolution |
|----|--------|------------|
| F821 (22 erreurs runtime du 18 avr) | ✅ FIXED | Tous corrigés entre le 18 avril et le 1er mai (audit ruff confirmé). |
| F823 (1 latent) | ✅ FIXED | Commit `1281e9a` du 1er mai. Pré-init défensive + noqa documenté. |
| F402 (1 latent) | ✅ FIXED | Commit `1281e9a` du 1er mai. Renommage variable de loop. |
| Studio en prod legacy purple/cyan | ✅ FIXED | Sprint A5.1 → A5.4 mergé dans main au commit `8bc569c` du 1er mai. Charte ink/bone/brass cohérente avec le marketing. |
| SignupPage absente du Studio | ✅ FIXED | Commit `9dab8cb` du 1er mai sur feat/platform-studio (mergé dans main). |
| Page /pricing legacy "Starter/Pro/Enterprise" | ✅ FIXED | Refactor freemium 4-tier (commit `e538605`) + Mod 23 (commit `d679652`) + A5.4 Pricing.tsx refonte. |
| Pages légales /cgv /legal /privacy 404 | ✅ FIXED | Mod 28 (commit `cf86231`) du 1er mai, contenu boilerplate FR+EN livré. |
| Lighthouse mobile a11y 86, SEO 91 | ✅ FIXED | Mod 29 (commit `3366d29`) du 1er mai, scores 100/100/100. |
| Console error 404 /favicon.ico | ✅ FIXED | Mod 30 (commit `18698e5`) du 1er mai. |
| Stripe webhook backend manquant | ✅ DONE | Phase 3 S3.3 (commit `b8e4f82`) du 29 avril. |
| Marcus régression Rev2 (E2E #143) | ⏳ KNOWN | Voir REVISION-001 P2. Code patch écrit, pas branché. |
| Cost tracking 22% capture | ⏳ KNOWN | Voir COST-001 P2. |
