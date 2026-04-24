# Refonte doc — État courant

**Dernière mise à jour** : 2026-04-24 11:35 UTC (session Claude+Sam)

## Phase courante
**Phase 0 + Phase 1 terminées**. Prochaine action : Phase 2 (split `index.html` en fragments).

## Décisions actées
- **Framework** : Jinja2 + Python stdlib (pas MkDocs / Hugo). Raison : léger, zéro dépendance neuve, sources de vérité spécifiques au projet.
- **CI** : reportée à post-N2 (après que le hook git local ait fait ses preuves pendant ~1 mois).
- **Branche** : `feature/docs-refonte` (dédiée).
- **Backups auto** : `*.bak.YYYYMMDD_HHMMSS` à conserver 7 jours minimum, auto-générés par `build_docs.py` (Phase 4).
- **Source unique par type** : chaque fait vit à un seul endroit (cf `DOCS_REFONTE_PLAN.md §3`).

## Fait cette session (2026-04-24)
- ✅ `index.html` à jour (RAG 70K→92K, P0-P11 statuts Session 3, timeline 12 avr + 18 avr + 23-24 avr)
- ✅ `DOCS_REFONTE_PLAN.md` rédigé (13.8 KB, 8 sections)
- ✅ Branche `feature/docs-refonte` créée, 2 commits
- ✅ `SESSION_PROTOCOL.md` livré
- ✅ 3 YAML sources créés : `problems.yaml`, `stack.yaml`, `meta.yaml`
- ✅ `STATUS.md` livré (ce document)

## Prochaine étape recommandée
**Phase 2** : découper `index.html` en fragments `sections/*.html` + shell commun.

Pré-requis :
- Validation Sam du plan (faite ✅)
- Inventaire sections : 11 sections détectées (overview, architecture, agents, sds, build, hitl, rag, infra, database, api, frontend, problems, refonte, journal)

Durée estimée : ~1h.

## Questions en attente
_(aucune)_

## Pièges connus (à relire avant toute modif)
- ⚠️ `index.html` existe en 2 exemplaires : `docs/refonte/` (repo) et `/var/www/digital-humans.fr/docs/refonte/`. Toujours synchroniser les 2.
- ⚠️ Deux fichiers `.env` pour clé OpenAI : `backend/.env` + `/opt/digital-humans/rag/.env` (cf `problems.yaml` → P12).
- ⚠️ Ne jamais reformater l'HTML actuel à la main (risque de dérive vs `build_docs.py` futur). Utiliser `str_replace` ciblé.
- ⚠️ Vérifier `curl -I https://digital-humans.fr/docs/refonte/` après chaque déploiement — `HTTP 200` attendu.

## Environnement de travail
- VPS : `72.61.161.222`, Ubuntu 24.04
- Repo : `/root/workspace/digital-humans-production`
- Branche : `feature/docs-refonte`
- Python venv : `backend/venv/` (Jinja2 disponible via FastAPI)
