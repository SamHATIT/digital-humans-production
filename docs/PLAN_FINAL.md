# PLAN D'EXÉCUTION FINAL — Digital Humans

**Généré** : 2026-06-08. **Stratégie validée par Sam.**

## Stratégie
Terminer **TOUS** les correctifs et améliorations d'abord. Ensuite seulement, lancer le **batch SDS complet** comme preuve unique de bon fonctionnement. Si le batch passe propre → plateforme prouvée, gel du pipeline.

## Jalons
- **M1 — avant l'été** : campagne de lancement + **Free tier ouvert**.
- **M2 — rentrée** : lancement **Pro payant**.

## Décisions enregistrées
- LEGAL-002 ✅ FAIT (SIRET + adresse siège).
- BIZ-001 ✅ Free tier **OUVERT** au launch.
- Galerie : exec 144 (fév) = **pré-refonte, inutilisable**. Premier SDS post-refonte = LogiFleet (146). Télécom & Retail = à générer.
- QA/formation vides sur 148 & 155 = bug corruption sections experts → réglé par STREAM-001.

## Modèle d'orchestration Claude Code
- 1 session orchestratrice + sous-agents spécialisés par lane.
- Chaque agent : sa branche → PR vers `staging` ; smoke test après merge ; **jamais de push main ni de mutation prod**.
- Haut enjeu (STREAM-001, sécurité, Stripe prod, runs SDS payants) : l'agent **prépare**, Sam **relit/approuve**.
- Garde-fous = `AGENT_BRIEF.md` (à écrire) : conventions (branche/tag/commit atomique, smoke test, preuve testée), périmètre autorisé vs interdit, **cap budget API dur**, secrets jamais en chat.

---

## VAGUE 0 — Préparation (en cours)
- TASKS_MASTER à jour ✅
- `AGENT_BRIEF.md` — directives + périmètre des agents
- Worktree/clone dédié + stratégie de branches + caps budget

## VAGUE 1 — Correctifs (lanes parallèles)

**Lane A — Cœur SDS / infra (HAUT ENJEU : agent prépare, Sam relit) — séquentiel**
1. **STREAM-001** — streaming `_call_anthropic`. Keystone, débloque tout le batch.
2. ELENA-TIMEOUT-001 — vérifier qu'il est recouvert par le streaming.
3. JORDAN-PROMPT-001 — contrainte Pydantic sur `monitoring.alerting`.
4. AGENT-FK-001 — `agent_id` renseigné au write site.
5. BR-FOOTGUN-FIX — briefs dans `business_requirements` pour les projets du batch.
6. MOD40 — capability resolver (après streaming).
7. COST-001 — `cost_usd` pour Aisha/Lucas/Elena/Jordan.

**Lane B — Finalisation SDS templating (mix agent/Sam)**
- merge `feat/sds-templating` + tag `v2.0-sds-db-driven` (gate Sam).
- cleanup : guard Annexe A (`<!DOCTYPE`), rename `raw_markdown`→`raw_html`, réécrire test e2e, supprimer `.bak.*`, DOCX-OBSOLETE-001.
- valider `build_sds` via API/navigateur (live preview, snapshot, eye).

**Lane C — Plateforme UI (agent)**
- STUDIO-RIM-AGENTS, UI-002/003/004, UX-003/004, vérif Free tier (Sophie+Olivia chat).

**Lane D — Marketing / site (agent + spec Sam)**
- BUNDLE-001 (perf Lighthouse), bug light mode (spec Sam requise), transcréation FR (skill `dh-fr-copywriting`), brouillon contenu LinkedIn.

**Lane E — Hygiène (agent, faible risque)**
- DEADCODE-BACKUPS, GIT-CLEANUP-001.

**Lane F — Humain / Sam (parallèle)**
- LEGAL-001 (juriste CGV), spec light mode, validation des contenus.

**Porte de sortie Vague 1** : PRs mergées en staging + smoke tests verts + STREAM-001 validé par Sam.

## VAGUE 2 — Batch de validation SDS (la preuve)
**Préconditions** : Vague 1 close.
- Lancer **ensemble** : Télécom, Retail, Pipeline Tuner, Grid Foresight, Omnichannel Loop + **re-run** Pharma 148 & Claim Resolver 155. Inclut TEST-4-PARALLEL.
- **Critères d'acceptation** : 12/12 sections · QA (§7) + Training (§9) pleines · aucune section experte vide · JSON propre aux raccords · Elena passe (pas de timeout 600s) · `cost_usd` complet · coût ≤ cap.
- **Gate Sam** : qualité Marcus (différenciateur commercial).
- Si tout passe → **plateforme PROUVÉE, gel des modifs pipeline**.

## VAGUE 3 — Go-live commerce (vers M2)
- Galerie finalisée depuis les SDS validés : EX2 (Pharma), EX3 (Télécom), EX4 (Retail), SITE-155-PUBLISH.
- SECURITY-001..005 (rotation secrets + manager) — vague finale, piloté Sam.
- STRIPE-PROD-001 (après sécurité).
- LEGAL-001 validé.

---

## Mapping jalons
- **M1 (avant été)** : Vague 1 lanes C+D + Free tier vérifié + contenu LinkedIn → **campagne + Free ouvert**. Galerie M1 = LogiFleet 146 (+ Pharma si QA réparée). **DÉCISION À PRENDRE** : campagne M1 avec galerie partielle, ou attendre le batch Vague 2 pour une galerie complète ?
- **M2 (rentrée)** : Vague 2 + Vague 3 → **Pro payant**.

## Risques / notes
- STREAM-001 = goulot : tout le batch en dépend, à démarrer en premier.
- Batch ≈ 7 runs × ~10\$ = ~60-80\$ API. Cap mod37 = 30\$/exec.
- Autonomie agents : périmètre lanes C/D/E ; lanes A/B relues par Sam.
