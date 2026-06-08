# AGENT_BRIEF — directives pour Claude Code (correctifs Digital Humans)

**Mission** : exécuter les correctifs de `docs/PLAN_FINAL.md` (Vague 1), proprement et vite.

## Modèle de collaboration
- **Claude Code (toi, l'agent)** = exécute les tâches.
- **Claude orchestrateur (chat)** = vérifie chaque sortie contre les critères ci-dessous.
- **Sam** = approuve les merges à fort enjeu et tranche les décisions produit.

## Références (à lire avant de commencer)
- `docs/TASKS_MASTER.md` — source unique des tâches + statuts vérifiés.
- `docs/PLAN_FINAL.md` — stratégie, vagues, lanes.

## Règles globales (NON négociables)
1. **Une branche par tâche** : `fix/<ID>` ou `feat/<ID>`. Jamais de commit direct sur `main`.
2. **PR vers `main`** ouverte pour relecture ; ne PAS merger soi-même les items Lane A/B (gate humain).
3. Commits **atomiques**, message clair, **preuve testée** dans la PR (pas de « c'est fait » sans preuve).
4. **Smoke test** après tout changement backend (`systemctl is-active` + `curl /health`).
5. **Cap budget API dur** : ne pas lancer de runs SDS payants (réservés au batch Vague 2, supervisé).
6. **Secrets** : jamais en chat ni en commit ; lecture via `.env` serveur uniquement.
7. **Interdit (gate Sam obligatoire)** : rotation de secrets, Stripe prod, runs SDS payants, modif du cœur LLM/orchestrateur, mutation prod (DB/déploiement).

## Lanes & périmètre

### Lane A — Cœur SDS / infra (HAUT ENJEU : agent prépare → orchestrateur vérifie → Sam merge)
- ✅ **STREAM-001** — FAIT (mergé main 04ea3c5, déployé). **Ne pas refaire.**
- **ELENA-TIMEOUT-001** : vérifier si le timeout 600s phase 4 est résolu par le streaming (probable) ; sinon ajuster.
- **JORDAN-PROMPT-001** : contraindre `monitoring.alerting` via Pydantic (au lieu du template défensif).
- **AGENT-FK-001** : renseigner `agent_id` au write site (fin du band-aid OUTER JOIN).
- **BR-FOOTGUN-FIX** : garde-fou pour que le brief soit lu depuis `business_requirements` (pas `description`).
- **MOD40** : capability resolver au startup (spec dans `docs/BACKLOG_TECH.md`).
- **COST-001** : compléter `cost_usd` pour Aisha/Lucas/Elena/Jordan.

### Lane B — Finalisation SDS templating (agent prépare → orchestrateur vérifie ; merge/tag = Sam)
- merge `feat/sds-templating` + tag `v2.0-sds-db-driven`.
- cleanup : guard Annexe A (`<!DOCTYPE`), rename `raw_markdown`→`raw_html`, réécrire test e2e, supprimer `.bak.*`, DOCX-OBSOLETE-001.
- valider le chemin `build_sds` via API/navigateur.

### Lane C — Plateforme UI (agent fait → orchestrateur vérifie → merge)
- STUDIO-RIM-AGENTS, UI-002/003/004, UX-003/004, vérif Free tier (Sophie+Olivia chat).

### Lane D — Marketing / site (agent fait → orchestrateur vérifie ; light mode attend la spec de Sam)
- BUNDLE-001 (perf), bug light mode (spec Sam requise), transcréation FR (skill `dh-fr-copywriting`), brouillon contenu LinkedIn.

### Lane E — Hygiène (agent fait → orchestrateur vérifie → merge ; faible risque)
- DEADCODE-BACKUPS (supprimer `backups_20251219_114242/`), GIT-CLEANUP-001 (branches stale).

## Definition of Done (par PR)
- [ ] Code sur branche dédiée, PR ouverte vers main.
- [ ] Preuve testée jointe (sortie de test / smoke).
- [ ] Pas de régression (py_compile + smoke `/health` si backend).
- [ ] TASKS_MASTER.md mis à jour (statut).
- [ ] Lane A/B : attendre l'approbation Sam avant merge.
