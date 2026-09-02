# Mission — Vague A (Digital·Humans, pré-ouverture)

Tu travailles sur `/root/workspace/digital-humans-production`, branche
`claude/vague-a-20260903`, déjà créée depuis `main` (`d9798f6`) — tu y es.
Tu ne touches jamais à `main`, ni à `.env`, ni à la base `digital_humans_db`,
ni aux services systemd. Rien n'est poussé en production : Sam relit la branche
avec Claude avant tout merge.

## Environnement, modèles, outils

- Tu tournes dans le bac à sable Claude Code (clone GitHub), **pas sur le VPS**. C'est
  le processus habituel : tu travailles sur la branche, Sam et Claude relisent,
  puis Claude déploie sur le VPS. Ne cherche ni `.env`, ni services systemd,
  ni tunnel Spark : ils n'existent pas ici.
- Modèles : orchestrateur Fable 5.1 ; sous-agents Opus (A1, A5, A6) et Sonnet
  (A2, A3, A4, A7, A8, A9, A10, rédaction des tests).
- Base de test : `tests/conftest.py` exige PostgreSQL. Installe-le dans le bac à
  sable (`apt-get install postgresql`, crée `digital_humans_test`), puis exporte
  `TEST_DATABASE_URL` et `DATABASE_URL` sur cette base. Jamais SQLite.
- Référence pytest : **mesurée par toi dans ce bac à sable** au lot A1, pas
  reprise des chiffres du 02/09 (461/24/7/118, mesurés sur le VPS). Les deux
  environnements peuvent diverger ; c'est la tienne qui compte pour la vague.
- Le venv : crée-le (`python3.12 -m venv backend/venv && pip install -r backend/requirements.txt`).
- La suite complète dure plusieurs minutes : lance-la en arrière-plan et lis le log.
- Pour A8, démarre le backend localement (`uvicorn app.main:app --port 8002`) avec
  `DEBUG=False` et les variables minimales que `app/config.py` exige.
- Pour A7, le script est dans `scripts/dh-watchdog.sh` (copie du VPS). La sonde
  Spark échouera ici : c'est le cas de test.

## Discipline (chaque règle vient d'un incident réel)

1. **Exécuté ≠ lu.** Tu n'écris « vérifié » que pour une commande jouée et sa
   sortie collée. Sinon « lu, non exécuté ».
2. **Mesure la référence** de tests au début de chaque lot. Ne la reprends pas
   d'un document ni du lot précédent.
3. **Test rouge d'abord.** Écris le test, vois-le échouer, corrige, vois-le
   passer. Ajoute un contrôle négatif si le correctif discrimine deux cas.
4. **Lis l'assertion, pas la couleur.** Un test vert qui vérifie la présence de
   la ligne fautive ne prouve rien.
5. **Jamais de repli silencieux.** Une valeur inconnue est refusée avec un
   message nommant la valeur reçue et les valeurs valides.
6. **Un lot = un périmètre de fichiers exclusif.** Si un lot t'oblige à toucher
   un fichier d'un autre lot, arrête et écris-le dans le rapport.
7. **Un défaut trouvé n'est pas un trophée.** Dis-le platement, corrige, passe.
8. **Commit par lot, en français** : défaut, cause, correctif, commande de
   preuve et sa sortie. Si un chiffre du message est faux, amende.

## Ordre

**A1 d'abord, seul.** Ensuite A2, A3, A4, A5, A6, A7, A8, A9, A10 en parallèle
(sous-agents, périmètres disjoints, un `git worktree` par sous-agent si tu
veux éviter tout croisement). Chaque sous-agent lit
`docs/audit-20260821/EXECUTION_VAGUE2.md` et `.claude/skills/dh-discipline-de-preuve/SKILL.md`
avant d'écrire une ligne.

## Lots

### A1 — Remettre les 118 tests en jeu
Périmètre : `backend/requirements.txt`, venv.
Défaut : `httpx 0.28.1` a retiré `TestClient(app=…)` ; `starlette 0.27.0`.
Fin : `pip install 'httpx>=0.27,<0.28'`, épingler dans `requirements.txt`,
pytest → `errors == 0`. Colle la nouvelle ligne `N passed, M failed`. C'est la
référence de tous les lots suivants.

### A2 — REQ-001
Périmètre : `backend/requirements.txt`.
Fin : `grep -qiE '^arq==' backend/requirements.txt && grep -qiE '^redis=='` et
`pip install -r requirements.txt --dry-run` sans erreur. Versions = celles du
venv (`pip show arq redis`).

### A3 — Prix Pro 79 € et crédits Pro
Périmètre : `frontend/src/pages/Pricing.tsx`, `backend/app/models/subscription.py`,
`backend/tests/test_credit_service.py`, **une** migration Alembic qui met
`tier_config.pro.price = 79.00` (ne l'exécute pas sur prod : produis-la,
teste-la sur `digital_humans_test`).
Bloqué par D1 : si le chiffre de crédits Pro n'est pas dans le fichier
`docs/vague-a/DECISIONS_SAM.md`, **arrête ce lot** et signale-le.
Fin : `grep -cE "[^0-9 ]49€" Pricing.tsx` → 0 ; `grep -q '79 €/mois' subscription.py` ;
4 tests crédits verts avec le chiffre tranché.

### A4 — Clé Haiku morte
Périmètre : `backend/app/models/subscription.py`.
Fin : `grep -c llm_haiku` → 0 ; test négatif : `has_feature(SubscriptionTier.FREE, "llm_haiku")` renvoie False.

### A5 — Concierge public cloisonné
Périmètre : `backend/app/services/sophie_concierge_service.py` + un test.
Test rouge d'abord : un chunk inséré dans une collection avec `project_id=999`
ne doit jamais sortir d'une requête concierge. Fin : test vert + `py_compile`.

### A6 — Comptage RAG hors boucle d'événements
Périmètre : le fichier qui journalise `[RAG HEALTH] OK — N chunks` (trouve-le
par grep). Sortir le comptage via `asyncio.to_thread`. Fin : test qui lance le
comptage sur une collection factice lente (sleep 3 s) et vérifie que `/health`
répond en < 1 s pendant ce temps.

### A7 — Watchdog
Périmètre : `/usr/local/bin/dh-watchdog.sh` (copie dans `scripts/` du dépôt,
Sam recopiera). Supprimer le double `000` ; ajouter une sonde Spark
(`curl --max-time 5 http://127.0.0.1:18001/v1/models`). Fin : `bash -n` OK, et
exécution manuelle avec le tunnel volontairement injoignable → message d'alerte
formé (n'envoie pas sur Telegram : mode `DRY_RUN=1` à ajouter).

### A8 — smoke_test.sh réécrit
Périmètre : `scripts/smoke_test.sh`.
Assertions justes : `/health` 200 ; `/docs` 404 si `DEBUG=False` ; `/api/projects`
401 sans jeton puis 200 avec un jeton obtenu par `/api/auth/login` sur un compte
de test lu depuis `SMOKE_USER`/`SMOKE_PASS` en variables d'environnement (jamais
en dur). Fin : 5/5 contre le backend en cours d'exécution.

### A9 — display_name
Périmètre : `backend/config/llm_routing.yaml`, **valeurs `display_name:` seulement**.
Interdit de modifier une ligne commençant par `#`. Fin : YAML valide,
`grep -c 'display_name:.*\(Gemma 4 31B\|Qwen 3.6\)'` → 0,
`git diff | grep '^[-+]\s*#'` → vide.

### A10 — Ménage docs
Périmètre : `docs/BACKLOG_TECH.md` (supprimer), `docs/SECURITY.md` (créer :
inventaire des secrets par fichier, rotation, gestionnaire retenu = « à décider »).
Fin : `! test -f docs/BACKLOG_TECH.md && test -f docs/SECURITY.md`.

## Livrable de fin de vague

`docs/vague-a/EXECUTION.md` avec quatre sections, dans cet ordre :
1. Fait — commande et sortie par lot.
2. Non confirmé — constats qui ne se sont pas vérifiés dans le code.
3. Ouvert — ce qui reste, et pourquoi.
4. Non fait par choix — distinct de la section 3.

Puis : `git log --oneline main..HEAD` collé, et la ligne pytest finale. Tu ne
merges pas. Tu ne dis pas « c'est fait ».
