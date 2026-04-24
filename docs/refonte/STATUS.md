# Refonte doc — État courant

**Dernière mise à jour** : 2026-04-24 11:40 UTC (session Claude+Sam)

## Phase courante
**Phases 0, 1, 2 terminées**. Prochaine action : Phase 3 (collectors Python + templates Jinja2).

## Décisions actées
- **Framework** : Jinja2 + Python stdlib (pas MkDocs / Hugo). Raison : léger, zéro dépendance neuve, sources de vérité spécifiques au projet.
- **CI** : reportée à post-N2 (après que le hook git local ait fait ses preuves pendant ~1 mois).
- **Branche** : `feature/docs-refonte` (dédiée).
- **Backups auto** : `*.bak.YYYYMMDD_HHMMSS` à conserver 7 jours minimum, auto-générés par `build_docs.py` (Phase 4).
- **Source unique par type** : chaque fait vit à un seul endroit (cf `DOCS_REFONTE_PLAN.md §3`).
- **Validation rebuild** : chaque build doit produire un HTML strictement identique (ou documenté) à la version précédente tant qu'aucune source n'a changé. `split_sections.py` pose la référence byte-à-byte.

## Fait cette session (2026-04-24)
- ✅ `index.html` à jour (RAG 70K→92K, P0-P11 statuts Session 3, timeline 12/18/23-24 avr)
- ✅ `DOCS_REFONTE_PLAN.md` rédigé (13.8 KB, 8 sections)
- ✅ Branche `feature/docs-refonte` créée, commits posés
- ✅ `SESSION_PROTOCOL.md` livré
- ✅ 3 YAML sources créés : `problems.yaml`, `stack.yaml`, `meta.yaml`
- ✅ `STATUS.md` livré
- ✅ **Phase 2 livrée** : 14 fragments `sections/*.html` + `templates/shell.html` + `tools/split_sections.py` (rebuild byte-à-byte identique à l'original, 0 diff). Commit `eb0a803`.

## Inventaire des sections (réel = 14, pas 11)
overview, architecture, agents, sds-flow, build-flow, hitl, rag, infra, database, api, frontend, problems, refonte, journal.

## Prochaine étape recommandée
**Phase 3** : implémenter `tools/lib/collect.py` + templates Jinja2.

Livrables attendus :
- `tools/lib/collect.py` avec 6 fonctions (`collect_agents`, `collect_llm_profiles`, `collect_rag_stats`, `collect_services`, `collect_problems`, `collect_timeline`)
- `docs/refonte/templates/partials/*.html.j2` (6 templates)
- Première version de `tools/build_docs.py` qui assemble `shell.html` + `sections/*.html` + `partials/*.html.j2` rendus avec les données collectées
- Validation : build doit produire un HTML qui diffère de l'original **uniquement** sur les sections dynamiques (problems, rag stats, timeline), pas sur le rédactionnel statique.

Durée estimée : ~2h.

## Questions en attente
_(aucune)_

## Pièges connus (à relire avant toute modif)
- ⚠️ `index.html` existe en 2 exemplaires : `docs/refonte/` (repo) et `/var/www/digital-humans.fr/docs/refonte/`. Toujours synchroniser les 2.
- ⚠️ Deux fichiers `.env` pour clé OpenAI : `backend/.env` + `/opt/digital-humans/rag/.env` (cf `problems.yaml` → P12).
- ⚠️ Ne jamais éditer `index.html` à la main une fois Phase 4 livrée — modifier les sources (`sources/*.yaml` ou `sections/*.html`) puis rebuild.
- ⚠️ Vérifier `curl -I https://digital-humans.fr/docs/refonte/` après chaque déploiement — `HTTP 200` attendu.
- ⚠️ `sections/*.html` et `templates/shell.html` forment un couple : si on change l'indentation du marker `<!-- SECTION:X -->` dans le shell, adapter `split_sections.py` en conséquence.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Branche : `feature/docs-refonte`
- Python venv : `backend/venv/` (Jinja2 disponible via FastAPI)
- Dernier commit : `eb0a803` (Phase 2)
