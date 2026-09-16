# Mission Claude Code — Vague 0 / AS-02 — Environnement de correction sûr (OPS-05)

**Date :** 16/09/2026. **Branche :** `claude/vague0-as02-env-test` depuis `claude/vague-c-20260906`. **Durée visée :** 6-10 h (estimation Astra).
**Pourquoi maintenant :** quatre files Claude Code vont toucher le code en parallèle du 18 au 22/09. Aujourd'hui, une suite de tests lancée depuis le dépôt de prod peut écrire dans la base, la file et les services réels. Tant que ce n'est pas fermé, aucune vague ne démarre.

## 1. Lis d'abord, dans cet ordre
1. `docs/audit-20260906/rapport-astra.md` — constat **OPS-05** (lignes ~972-988) et **OPS-06**. C'est la commande.
2. `backend/tests/conftest.py` (lignes 1-40) et `backend/tests/db_guard.py` — la garde existante (vague 2, lot 1c), à conserver et à étendre, pas à remplacer.
3. `/mnt/skills/user/dh-discipline-de-preuve/SKILL.md` si tu y as accès, sinon la section 5 ci-dessous : elle en reprend les règles.
4. `docs/BACKLOG_GOLIVE_2026-10-01.md` — section 4, vague 0 : le contexte de cette mission.

## 2. État mesuré le 16/09 (commandes exécutées, pas relues)
- La garde `assert_not_production_database()` s'applique à `SQLALCHEMY_DATABASE_URL` **du conftest uniquement**. `app.main` charge ensuite `backend/.env` et `settings.DATABASE_URL` reste la base réelle : **17 fichiers de tests** importent `app.main` ou `app.database.engine/SessionLocal` directement (`grep -rlE "from app.main import|from app.database import (engine|SessionLocal)" backend/tests` → 17).
- Bases Postgres présentes : `digital_humans_db` (prod), `digital_humans_v3`, `digital_humans_test`.
- Redis : `REDIS_SETTINGS` unique dans `backend/app/workers/arq_config.py` — aucune séparation test/prod ; file `digital-humans` partagée.
- Chroma : `DH_CHROMA_PATH=/opt/digital-humans/rag/chromadb_v2` fixé par le service systemd, lu tel quel par les tests.
- Clés réelles dans `backend/.env` (Anthropic, OpenAI, Stripe, ModelArk absent) : rien n'empêche un test d'appeler l'API réelle ; le 15/09 la suite a été lancée depuis ce répertoire.
- 63 fichiers `test_*.py`. Aucune CI ; un seul hook git (`post-commit`, reconstruit la doc). État de la suite **à mesurer par toi** (règle 4) : `cd backend && TEST_DATABASE_URL=... ./venv/bin/python -m pytest -q` — note passés/échoués/ignorés avant tout changement.
- Il existe déjà `backend/tests/test_vague2_lot1_garde_database_url.py` et `backend/tests/test_no_hardcoded_secrets.py` (16/09).

## 3. Objectif — critère de sortie d'Astra, mot pour mot
> Les suites et agents de développement ne peuvent joindre **aucune** base, file, org ou clé de production.

Décliné en cinq exigences vérifiables :
1. **Une seule source pour la base de test**, imposée **avant tout import applicatif** : `settings.DATABASE_URL`, l'engine de `app.database`, et le conftest doivent pointer la même base jetable. Toute divergence fait échouer la session pytest à la collecte, avec un message qui dit quoi exporter.
2. **Redis, Chroma, stockage fichiers séparés** en test : une base Redis dédiée (ou un préfixe de file `test-<id>`), un répertoire Chroma temporaire, un `WORKSPACE`/`outputs` sous `tmp_path`. Rien ne s'écrit sous `/opt/digital-humans`, `/root/workspace/*/outputs` ni dans la file `digital-humans` pendant un test.
3. **Aucune clé réelle en test** : `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `STRIPE_*`, `GHOST_*`, jetons Git/Salesforce sont remplacés par des valeurs factices dès la collecte ; un test qui tente un appel réseau sortant hors `127.0.0.1` échoue (plugin socket, par exemple `pytest-socket` ou un garde maison).
4. **Parallélisme d'agents** : `TEST_DATABASE_URL` par exécution (nom de base dérivé d'un identifiant), création/destruction de la base par la session, pas de `drop_all` sur une base partagée.
5. **Contrôle négatif** : un test qui simule `DATABASE_URL` = prod (nom `digital_humans_db`) avec `TEST_DATABASE_URL` absent doit voir la collecte refusée **avant** toute connexion ; un test qui simule une clé Anthropic réelle doit voir la collecte refusée.

Hors périmètre : réparer les tests métier qui échouent pour d'autres raisons (OPS-06 est une autre mission) — mais **les compter** avant/après.

## 4. Livrables
- Le code : conftest/bootstrap, garde étendue, fichier `backend/.env.test` (sans secret), doc `backend/tests/README.md` (comment lancer, comment isoler par agent).
- Les tests : rouge d'abord (commit « test rouge »), puis correctif (commit « vert »), y compris les deux contrôles négatifs.
- Le rapport : `docs/missions/RAPPORT_VAGUE0_AS02.md` avec les quatre sections de la discipline (fait avec preuve / non confirmé / reste ouvert / non fait et pourquoi), et la mesure avant/après de la suite complète.
- Un commit par correctif, message en français : défaut, cause, correctif, preuve exécutée.

## 5. Règles (chacune vient d'un incident daté)
1. Distinguer « exécuté » de « lu ». Livrer les commandes et leurs sorties, pas des conclusions.
2. Lire l'assertion, pas la couleur : un test vert qui vérifie la présence d'une ligne fautive n'est pas un test.
3. Test rouge avant correctif, contrôle négatif quand le correctif discrimine deux cas.
4. Mesurer la référence (l'état de la suite) plutôt que la reprendre d'un document.
5. `grep` les appelants avant de proposer une architecture.
6. Jamais de repli silencieux : une valeur inconnue est refusée, un service injoignable fait échouer l'appel en le disant.
7. Un défaut trouvé n'est pas un trophée. Le dire platement, corriger, passer.

## 6. Interdits
- Ne pas toucher à `backend/.env` de prod ni aux services systemd ; ne pas redémarrer backend/worker.
- Ne pas exécuter la suite sans `TEST_DATABASE_URL` posée sur une base jetable, jamais sur `digital_humans_db`.
- Ne pas « corriger » un test en affaiblissant son assertion.
- Ne pas fusionner dans `vague-c` : PR ouverte, Sam ou Claude relit.
