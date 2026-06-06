# TASKS MASTER — vue unique des tâches Digital Humans

**Généré** : 2026-06-06 — consolidation factuelle (audit croisé docs ↔ git ↔ DB ↔ working tree).
**Vocation** : remplacer le suivi éclaté (BACKLOG.md, 2× STATUS.md, NEXT_SESSION_TODO, SESSION_NEXT_TODO, 4× TODO_*, PROGRESS.log) par une source unique.
**Méthode statut** : ✅ vérifié fait · 🟡 partiel / à valider · ❌ à faire · ⚠️ incohérence détectée.

---

## 0. ÉCARTS DE STATUT DÉTECTÉS (à arbitrer en priorité)

### A. Marqué « à faire » alors que c'est FAIT
- ⚠️ **P10 BaseAgent** — BACKLOG le classe en "P2 dette, sprint post-launch". Réalité : **fait**, commit `258c5c3`, tag `v2026.05-p10-baseagent`. → corriger BACKLOG.
- ⚠️ **Galerie Télécom (MARKETING-EX3-001)** — BACKLOG : "reste Télécom". Réalité : exec **144** (Service Client Omnicanal) est COMPLETED ; le SDS Télécom existe. Reste seulement la page site, pas la génération.
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

## 1. NOUVELLES TÂCHES (post-2 mai, absentes des docs)

| ID | Prio | Description | Statut |
|----|------|-------------|--------|
| STREAM-001 | 🔴 P0 | Passer `_call_anthropic` en **streaming**. Fix systémique des 3 bugs canary (extraction BR, corruption JSON sections experts aux raccords, timeout Elena 600s). Confirmé absent de `llm_service.py`. | ❌ |
| SDS-PIPELINE-TUNER | P1 | Générer SDS Pipeline Tuner. Aucune exec. Brief → `business_requirements` (PAS `description`). | ❌ |
| SDS-GRID-FORESIGHT | P1 | Générer SDS Grid Foresight. Idem. | ❌ |
| SDS-OMNICHANNEL-LOOP | P1 | Générer SDS Omnichannel Loop. Idem. | ❌ |
| BR-FOOTGUN-FIX | P1 | Corriger l'emplacement du brief (`business_requirements`) sur les 3 projets ci-dessus. Footgun : brief dans `description` → 0 BR extraite. | ❌ |
| TEST-4-PARALLEL | P1 | Test d'exécution 4-parallèle. | ❌ |
| MOD40-CAPABILITY | P2 | Resolver de capacités au startup (auto-config params modèle via `GET /v1/models/{id}`, niveaux effort). À faire APRÈS STREAM-001. | ❌ |
| SDS-148-QA-EMPTY | P2 | SDS Pharma exec 148 : section QA vide (même bug raccord). Différé, non bloquant. | 🟡 |
| SITE-155-PUBLISH | P2 | Publier Claim Resolver (exec 155) sur le site — il est COMPLETED mais affiché "bientôt". | ❌ |

---

## 2. P0 — BLOQUANTS OUVERTURE (inchangés, action humaine Sam)

| ID | Description | Statut |
|----|-------------|--------|
| LEGAL-001 | Validation juriste CGV (300-500€). Boilerplate FR+EN livré. | ❌ Sam |
| LEGAL-002 | Compléter SIRET + adresse siège (placeholders Mentions Légales). | ❌ Sam |
| BIZ-001 | Décision tier Free ouvert/fermé au launch. | ❌ Sam |
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
| MARKETING-EX3-001 | SDS Télécom — base exec 144 COMPLETED ; reste revue + page. | 🟡 (génération faite) |
| MARKETING-EX4-001 | SDS Retail — pas lancé. | ❌ |

---

## 4. DETTE TECHNIQUE

| ID | Description | Statut |
|----|-------------|--------|
| AGENT-FK-001 | `agent_deliverables.agent_id` NULL depuis exec 142+. Band-aid OUTER JOIN posé (9262a96) ; vrai fix au write site. | 🟡 band-aid |
| DOCX-OBSOLETE-001 | Supprimer Phase 6 `_generate_sds_document` (dead code depuis SDS HTML). | ❌ |
| ELENA-TIMEOUT-001 | Timeout 10min Phase 4 marque Elena failed alors que le LLM réussit après. Recouvert par STREAM-001. | ❌ |
| JORDAN-PROMPT-001 | Sortie `monitoring.alerting` non contrainte (dict/list selon exec). Template défensif posé ; vrai fix = Pydantic. | 🟡 |
| GHOST-001 | SMTP réel (Postmark) pour Ghost + réactiver staffDeviceVerification. | ❌ |
| COST-001 | cost_usd 6-tuple : Marcus/Emma/Olivia ✅ ; reste Aisha/Lucas/Elena/Jordan. | 🟡 |
| BUNDLE-001 | Bundle marketing 16MB, split lazy-load. Perf Lighthouse 25/100. | ❌ |
| P4-FAT-CONTROLLER | `PMOrchestratorServiceV2` = god node n°1 (66 arêtes, Graphify). Non traité. | ❌ |
| UI-002/003/004 | ELAPSED "—", "first take" figé, sidebar chevauche au scroll. | ❌ |
| UX-003/004 | Coverage gaps détaillés ; find()→filter() agents parallèles. | ❌ |

---

## 5. HYGIÈNE REPO & DOC (issu Graphify + git)

| ID | Description | Statut |
|----|-------------|--------|
| DEADCODE-BACKUPS | Supprimer `backups_20251219_114242/` (196K, vieux pm_orchestrator_service_v2.py + BuildPhaseService). Scanné par Graphify, pollue le graphe, résidu P1 split-brain. | ❌ |
| GIT-CLEANUP-001 | 40+ branches stale (locales `feat/*` mergées + `claude/*` refonte). | ❌ |
| DOC-ARCHIVE | Archiver les docs périmés (6 mois) : `NEXT_SESSION_TODO.md`, `SESSION_NEXT_TODO.md`, `docs/TODO_AUDIT_TRACABILITE.md`, `TODO_CORRECTIONS_POST_TEST.md`, `TODO_FIX_METADATA_RAG.md`, `TODO_REFONTE_ARCHITECTURE_V2.md`, `PROGRESS.log`. `docs/BACKLOG_TECH.md` (8 lignes, vide) à supprimer ou remplir. | ❌ |

---

## 6. GRAPHIFY — synthèse structurelle (run 2026-06-06, commit 7cc913e, 0 coût LLM)

- 488 fichiers, 9240 nœuds, 13647 arêtes, 605 communautés. HTML viz sautée (>5000 nœuds).
- **God nodes** : User(136), Project(108), Execution(99), ExecutionStatus(77), useLang(77), ExecutionStateMachine(74), **PMOrchestratorServiceV2(66)**, ArtifactService(59), CreditService(56), AgentDeliverable(55).
- **Bridges (betweenness)** : PhaseStatus, PhaseContextRegistry, User.
- A confirmé : Fat Controller P4 (PMOrchestratorServiceV2), résidu backup Dec 2025.
- Limites : 15% d'arêtes INFERRED (conf. 0.57) à vérifier ; communautés non nommées (pas de passe LLM) ; 3630 nœuds isolés = bruit AST.
- Artefacts : `graphify-out/{graph.json, GRAPH_REPORT.md, manifest.json}`. Rebuild sans coût : `graphify update .`.

