# Backlog — Digital Humans Production

**Dernière mise à jour** : 2026-05-02 (O1 tranché, plan d'exécution 3 vagues)

Le suivi détaillé des sessions est dans `CHANGELOG.md`. Ce fichier liste **uniquement
les actions futures** + l'état des phases du Master Plan V4 (cible : ouverture early
access publique).

---

## 🎬 Décisions actées (2 mai 2026)

**O1 — Planning d'ouverture par palier (tranché par Sam)** :
- **Free** (Sophie + Olivia chat) → ouverture dès que le site marketing complet + tunnel
  signup + email verification + passerelle Studio sont validés bout-en-bout
- **Pro 49 €/mois** → ouverture dès que le SDS est validé à 100% (qualité + UX cohérente)
- **Team 1 490 €/mois** → ouverture dès que SDS + BUILD sont validés bout-en-bout

**O2 — Palier Mid 299-399 €** : différé. Sera réévalué après 3-6 mois de data Pro.

**O3 — Cinématique agents plateforme** : ✅ **TRANCHÉ — direction Théâtre retenue**
(2 mai). Cohérence narrative totale avec le site (actes I-V déjà présents, livrables à
chaque acte). Les 4 mockups restent disponibles à `/mockups-o3/` pour skins futurs
(ex. casting pour version on-premise). Implémentation : STUDIO-S4.1 (composant Stage
+ Curtain + ActorRow) puis STUDIO-RIM-AGENTS (sidebar agents rim-only avec spotlight
brass sur agent actif).

**LEGAL-001/002, BIZ-001, STRIPE-PROD-001** : différés. Sam s'en occupe quand la
structure juridique est montée et quand on est prêt à ouvrir Pro/Team.

---

## 🎯 État Master Plan V4 — par phase

Référence : `MASTER_PLAN_V4.md` (26 avr 2026, fichiers projet).

| Phase | Description | État | Reste à faire |
|---|---|---|---|
| **0** | Sécurité (audit secrets + manager) | ❌ **NON DÉMARRÉE** | Tout : audit `.env`, choix Doppler/Infisical, migration secrets, `docs/SECURITY.md` |
| **1** | SDS templating (lots A→D + merge main) | ✅ **CLOSE** | RAS — exec 148 valide la chaîne complète (12 sections, 347 K HTML rendu, mode patch) |
| **2** | Site marketing complet | ✅ **QUASI CLOSE** | Mods 1→30 appliqués + pages légales + a11y/SEO 100/100/100. Reste : MARKETING-EX2-001 (2e exemple SDS) |
| **3** | Modèle de crédits + Stripe | ✅ **DEV CLOSE** | STRIPE-001/002/003/004 livrés. Reste : bascule prod réelle (rotation secrets test→live + recréation produits) — action humaine |
| **4** | Plateforme refonte UI Studio | ⚠️ **MAJORITAIREMENT FAIT** | Sprint A5 mergé (`8bc569c`). CreditCounter en place. Reste : **atelier cinématique agents (S4.1 / O3)** + sidebar agents rim-only |
| **5** | Onboarding + passerelle site→plateforme | ⚠️ **PARTIEL** | SignupPage présente. Reste : flow onboarding tier-aware (Free vs Pro), pre-fill projet depuis CTA marketing |
| **6** | Galerie SDS industries | ⚠️ **2/3 DONE pour lancement** | LogiFleet ✅, Pharma (Essais Cliniques exec 148) ✅. Reste **Télécom + Retail** (recommandation O4 pour lancement) — Service Client Omnicanal exec 144 peut servir de base Télécom |

**Items P0 côté Sam (action humaine, pas dev)** :
- **LEGAL-001** — Validation juriste CGV (300-500 €, 1-2h). Boilerplate FR+EN livré (Mod 28).
- **LEGAL-002** — Compléter SIRET + adresse siège (placeholders dans Mentions Légales).
- **BIZ-001** — Décision tier Free : ouvert ou "Bientôt" au launch (impact /signup).
- **Arbitrages MP V4 §2** : O1 (planning ouverture), O2 (palier Mid), O3 (cinématique agents). Séance 60-90 min recommandée.

---

## 🌊 Plan d'exécution — 3 vagues (séquence validée 2 mai)

Ordre choisi par Sam : **B avant A** parce que les changements UX (Vague B) doivent
être validés à chaud, sinon la Vague A sécurité (qui modifie comment les services
lisent leurs secrets) ajoute une couche de validation supplémentaire pas souhaitable.

### Vague O3 — Mockups cinématique agents (préalable, en cours)
3-4 directions HTML statiques (casting / théâtre / orchestre / carte d'ensemble) →
Sam choisit → bascule vers STUDIO-S4.1 + STUDIO-RIM-AGENTS dans la Vague B.

### Vague B — Plateforme + Onboarding (séquentiel, 2-3 sessions)
Pendant que Sam réfléchit aux mockups, exécution séquentielle (zones chaudes : 
AuthContext + SignupPage + Pricing.tsx).
- ONBOARDING-001 — flow signup tier-aware
- ONBOARDING-002 — email verification au signup
- ONBOARDING-003 — pre-fill projet depuis CTA marketing
- STUDIO-S4.1 — implémentation du mockup retenu après choix Sam
- STUDIO-RIM-AGENTS — sidebar agents rim-only

### Vague C — Galerie SDS + dette agents (parallèle, 3 worktrees)
- **wt-marketing-sds** : MARKETING-EX2-001 + EX3-001 + EX4-001 (bundle preview isolé)
- **wt-orchestrator-cleanup** : AGENT-FK-001 + DOCX-OBSOLETE-001 + BUILD-AGENT-AVATARS
- **wt-agents-cost** : COST-001 (Aisha/Lucas/Elena/Jordan)

### Vague A — Sécurité + cleanup final (en dernier, 1 session)
Bouclage propre une fois les autres vagues validées en prod.
- SECURITY-001..005 (audit + Doppler/Infisical + migration + bascule + docs)
- GIT-CLEANUP-001 (branches stale)
- UI-002/003/004 (cosmetic)
- REVISION-001-WORKER (documenter dans HOTFIXES_E2E_TEST.md)

---

## 🚧 Pour finaliser le Master Plan V4 — items prioritaires

### P0 — Bloquants ouverture early access

| ID | Phase | Description | Estimation |
|----|----|-------------|-----------|
| LEGAL-001 | — | Validation juriste CGV | Sam, 300-500 € |
| LEGAL-002 | — | Compléter SIRET + adresse | Sam, 30 min |
| BIZ-001 | — | Décision tier Free ouvert/fermé au launch | Sam, arbitrage |
| STRIPE-PROD-001 | 3 | Bascule prod Stripe (suivre `docs/STRIPE_PROD_CHECKLIST.md`) — rotation `sk_test_*` → `sk_live_*`, recréation produits Pro/Team en mode live, smoke test paiement réel | 1h, après BIZ-001 tranché |
| SECURITY-001 | 0 | Audit `grep -r` sur secrets en clair sur le VPS + `/opt/digital-humans/` + `/root/workspace/` | 30 min |
| SECURITY-002 | 0 | Choisir + installer secrets manager (Doppler ou Infisical, gratuit jusqu'à 5 users) | 30 min |
| SECURITY-003 | 0 | Migrer secrets actuels (Anthropic, OpenAI, Stripe, SendGrid) vers le manager | 1-2h |
| SECURITY-004 | 0 | Bascule services FastAPI pour lire via le manager au startup, `.env` minimal | 1-2h |
| SECURITY-005 | 0 | `docs/SECURITY.md` : procédure rotation, checklist déploiement | 30 min |

### P1 — Compléter Phase 6 galerie pour lancement

| ID | Phase | Description | Estimation |
|----|----|-------------|-----------|
| MARKETING-EX2-001 | 6 | Intégrer SDS Essais Cliniques (exec 148) sur site marketing — choix format : (a) HTML statique copié vers `/var/www/dh-preview/sds/exec_148.html`, (b) lien live `/api/deliverables/705/render`. Recommandation (a). | 1-2h |
| MARKETING-EX3-001 | 6 | SDS Télécom — base : exec 144 (Service Client Omnicanal Agentforce) déjà COMPLETED. Revue qualité + page dédiée site. | 2-3h |
| MARKETING-EX4-001 | 6 | SDS Retail — pas encore lancé. Préparer brief enrichi → pipeline Studio → SDS HTML → page galerie. | 4-6h |

### P1 — Compléter Phase 4 plateforme

| ID | Phase | Description | Estimation |
|----|----|-------------|-----------|
| STUDIO-S4.1 | 4 | Atelier cinématique agents plateforme (sujet O3) — décision casting / théâtre / orchestre / carte d'ensemble. Mockups statiques + validation Sam. | 2-3h atelier + 1 session impl |
| STUDIO-RIM-AGENTS | 4 | Sidebar gauche agents rim-only avec accent par acte, conformément brief §12 — actuellement absent du code. | 1 session après S4.1 |

### P1 — Phase 5 onboarding

| ID | Phase | Description | Estimation |
|----|----|-------------|-----------|
| ONBOARDING-001 | 5 | Flow onboarding tier-aware au signup : Free → Sophie chat direct, Pro → wizard projet complet, Team → contact sales | 1-2 sessions |
| ONBOARDING-002 | 5 | Pre-fill projet depuis CTA marketing (passerelle site→plateforme avec context preserved) | 1 session |

---

## 🔧 Dette technique post-launch acceptable

### P2 — E2E #144 follow-ups (2 mai 2026)

| ID | Description | Notes |
|----|-------------|-------|
| REVISION-001-WORKER | Toujours restart **worker + backend** après patch orchestrator. Le 2 mai, restart backend seul a fait que le worker ARQ a tourné l'ancien code (REVISION-001 HITL pas testé en pratique, fallback fix_gaps). À documenter dans `HOTFIXES_E2E_TEST.md`. |
| AGENT-FK-001 | Populer `agent_deliverables.agent_id` (FK vers `agents.id`) dans `_save_deliverable` côté pm_orchestrator. Actuellement NULL pour TOUS les deliverables depuis exec 142+. Band-aid OUTER JOIN posé dans `DeliverableService.get_deliverable_previews` (commit `9262a96`), mais le vrai fix est au write site. |
| DOCX-OBSOLETE-001 | Supprimer Phase 6 `_generate_sds_document` dans `pm_orchestrator_service_v2.py:2900-2925`. Depuis iter 8, le SDS est rendu en HTML in-app via `tools/build_sds.py`, l'utilisateur peut imprimer en PDF via le navigateur. Le `.docx` + `executions.sds_document_path` est dead code. |
| ELENA-TIMEOUT-001 | Timeout 10-min Phase 4 marque Elena `failed: Skipped: Timeout` alors que son LLM call (118K tokens output) réussit après. Soit allonger timeout pour Sonnet long output, soit cancel le LLM call cleanly. |
| JORDAN-PROMPT-001 | Prompt Jordan ne contraint pas le format `monitoring.alerting`. LLM produit alternativement dict (exec 146), `alerting_thresholds` (exec 147), liste (exec 148 → plante). Template défensif posé (`a5ba624`), vrai fix = Pydantic-valider la sortie Jordan. |
| GHOST-001 | SMTP réel (Mailgun/Postmark) pour Ghost puis réactiver `security__staffDeviceVerification`. Désactivé en hotfix le 2 mai (`b728a69`) — mail Direct ne livre pas à Gmail, ce qui bloque reset password Owner. |

### P2 — Bugs UI execution monitor

| ID | Description |
|----|-------------|
| BUILD-AGENT-AVATARS | Pendant la phase BUILD, ce sont les anciens avatars qui défilent au lieu des nouveaux portraits photo (cohérents avec ceux du site marketing et de la sidebar Studio). Vu par Sam le 2 mai. À fixer dans Vague C en cohérence avec STUDIO-RIM-AGENTS. |
| UI-002 | ELAPSED affiche toujours `—` même quand l'execution tourne. useEffect manquant probablement. |
| UI-003 | "first take" reste affiché en sidebar pendant une révision en cours (devrait passer à "revision 1" / "revision 2"). |
| UI-004 | Sidebar (BOX OFFICE / REVISIONS / STATE / ACTS) se chevauche avec le main content au scroll. |

### P2 — Dette technique de la refonte V3

| ID | Description |
|----|-------------|
| REVISION-001 | Mode `patch` est ÉCRIT et BRANCHÉ (commits `d6c1799`, `2c9659e`, `54577f5`) — AUTO-REVISE Phase 3.3 et HITL. Reste à valider en E2E qu'il s'exécute (E2E #144 a tombé en fallback fix_gaps à cause du worker non restart, voir REVISION-001-WORKER). |
| COST-001 | `cost_usd` 6-tuple : Marcus + Emma + Olivia ✅ (commit `d6c1799`). Reste : Aisha, Lucas, Elena, Jordan. Capture actuelle ~50% du coût réel (était 22% avant). |
| P10 | BaseAgent class pour les 11 agents (`_call_llm`/`execution_id`/logging dupliqués). Sprint dédié post-launch. |
| BUNDLE-001 | Bundle 16 MB site marketing : split lazy-load post-launch. Lighthouse Perf 25/100 (a11y/SEO/best-practices à 100). |

### P3 — UX / qualité

| ID | Description |
|----|-------------|
| UX-003 | Coverage gaps frontend : afficher `gap.what_is_missing` + `gap.fix_instruction`, pas que `gap.severity`. |
| UX-004 | Active Agent : `.find()` → `.filter()` pour agents parallèles (ExecutionMonitoringPage.tsx:544). Permet d'afficher Diego + Zara + Raj simultanément en BUILD. |

### P3 — Cleanup git

| ID | Description |
|----|-------------|
| GIT-CLEANUP-001 | Supprimer branches mergées : `feat/sds-templating`, `feat/platform-studio`, `feature/journal-publication`, etc. (15+ branches stale). `git branch -a` montre l'inventaire. |

---

## ✅ Fait depuis le 1er mai 2026

Snapshot des items clos ces 2 derniers jours.

| ID | Phase | Resolution |
|----|----|------------|
| STRIPE-001 | 3 | ✅ DONE — `_handle_invoice_paid` reset crédits sur `subscription_cycle` (commit `74c4a0d`, 2 mai) |
| STRIPE-002 | 3 | ✅ DONE — `_handle_invoice_failed` log + dunning natif Stripe (commit `74c4a0d`) |
| STRIPE-003 | 3 | ✅ DONE — Mod 24 frontend wiring `Pricing.tsx` + `BillingSuccess/Cancel.tsx` + helper `startStripeCheckout` (commit `74c4a0d`) |
| STRIPE-004 | 3 | ✅ DONE — `docs/STRIPE_PROD_CHECKLIST.md` (181 lignes, 8 étapes + rollback 2 min) |
| JOURNAL-001/2/3/4 | — | ✅ DONE — Webhook live, Ghost owner reset, 5 webhooks configurés (commit `fb9155e`, tag `v2026.05-journal-live`) |
| REVISION-001 (code) | 1 | ✅ DONE — Mode `patch` AUTO-REVISE + HITL + `CATEGORY_TO_SECTION` mapping (commits `d6c1799`, `2c9659e`, `54577f5`). Validation E2E pending (REVISION-001-WORKER). |
| COST-001 (Emma + Olivia) | — | ✅ DONE — `_call_llm` 6-tuple + cost_usd (commit `d6c1799`). Reste Aisha/Lucas/Elena/Jordan. |
| LINT-001 | — | ✅ DONE — 81 → 0 warnings ruff (commit `d6c1799`) |
| SDS template alerting | 1 | ✅ DONE — Rendu défensif dict OR list (commit `a5ba624`) |
| UI-001 | 4 | ✅ DONE — INNER → OUTER JOIN + Optional agent_id (commit `9262a96`) |
| Open SDS | 4 | ✅ DONE — Endpoint `/api/deliverables/{id}/render` + bouton "Open SDS" frontend (commit `511abfa`) |
| SDS Pharma exemple | 6 | ✅ DONE — Essais Cliniques E2E #144, exec 148 COMPLETED, SDS HTML 347 K rendu, status APPROVED |
| ONBOARDING-001 | 5 | ✅ DONE — Signup tier-aware Free self-serve (Pricing→Signup query string, badge tier, WelcomeBanner) (commit `25f226b`) |
| ONBOARDING-002 | 5 | ✅ DONE — Verify-then-create (JWT 30 min payload, anti-enumeration) (commit `17ee65d`) — couvre la remarque Sam : ne plus créer de compte avant validation email |

---

## 📦 Backlog parking lot (post-launch, V4 §11)

Hors scope V4. À traiter post-lancement ou si bande passante.

- Spec gouvernance Team tier (RC pro, audit log SFDX, chiffrement credentials, procédure révocation)
- Palier Mid 299-399 € (à évaluer après 3-6 mois de data Pro)
- Documentation API publique (Stripe-style) pour Enterprise + intégrations partenaires
- Programme partenaires / revendeurs (agences Salesforce, intégrateurs)
- Internationalisation site/plateforme (FR-only actuellement, EN à prévoir)
- RAG live (mise à jour automatique sur nouvelles releases Salesforce)
- P3 split-brain résiduel + P7 transactions (refonte technique V3 résidus)
- E2E #145 ciblé pour valider REVISION-001 mode patch en HITL (post worker restart)
