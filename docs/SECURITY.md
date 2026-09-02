# Sécurité — secrets et rotation

Rédigé le 02/09/2026, lot A10 (vague A, pré-ouverture). Chaque ligne de ce
document vient d'un `grep` joué dans ce worktree à cette date, jamais d'une
reprise d'un document antérieur (règle 4 de la discipline de preuve). Aucune
valeur de secret n'apparaît dans ce fichier.

## 1. Objet et périmètre

Inventaire des secrets consommés par le backend Digital·Humans (fichier qui
les porte, où vit la valeur, qui la lit, constat), et procédure de rotation
par secret. Ce document ne couvre que ce qui a été grepé dans ce worktree :
`backend/app/config.py`, `backend/.env.example`, `CLAUDE.md`, `.claude/`,
`scripts/`, `docs/`, `backend/scripts/`, les fichiers `*.service`, et un
sondage ciblé de l'historique git. Voir §6 pour ce qui n'a pas été couvert.

## 2. Inventaire des secrets

### `backend/app/config.py` (modèle `Settings`, pydantic)

| Variable | Où vit la valeur | Consommateur | Constat |
|---|---|---|---|
| `SECRET_KEY` | `.env` hors dépôt (prod) ; auto-générée en mémoire si absente | `backend/app/config.py:151-169`, signature JWT | Optionnelle par défaut. Si absente et `DEBUG=False`, le démarrage est refusé (`config.py:157`). Si absente et `DEBUG=True`, une clé est auto-générée à chaque redémarrage (avertissement affiché) — pas de valeur en clair dans le dépôt. |
| `CREDENTIALS_ENCRYPTION_KEY` | `.env` hors dépôt (prod) ; absente en dev | `backend/app/config.py:183-192`, `backend/app/utils/encryption.py` | Exigée seulement si `DEBUG=False` (`config.py:183`). Si absente à `DEBUG=True`, une clé Fernet est **dérivée de `SECRET_KEY`** — pas de valeur en clair dans le dépôt, mais voir §4 pour l'effet de bord documenté dans `docs/audit-20260821/EXECUTION_VAGUE2.md` §5.2. |
| `OPENAI_API_KEY` | `.env` hors dépôt | `backend/app/config.py:58`, RAG/embeddings | Valeur par défaut `""` dans le modèle — pas de valeur en clair dans le dépôt. |

### `backend/.env.example` (gabarit versionné)

Fichier de gabarit uniquement : `DATABASE_URL`, `SECRET_KEY`,
`CREDENTIALS_ENCRYPTION_KEY`, `OPENAI_API_KEY` y sont présents avec des
valeurs placeholder (`changeme`, `your-secret-key-...`,
`sk-your-openai-api-key-here`) ou vides — aucune valeur en clair.

Constat : ce gabarit ne mentionne pas `ANTHROPIC_API_KEY`, `STRIPE_SECRET_KEY`
/ `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_ID_PRO` /
`STRIPE_PRICE_ID_TEAM`, `CHAT_IP_SALT`, ni `JOURNAL_WEBHOOK_SECRET`, alors que
ces sept variables sont lues par le code (tableau ci-dessous). Un déploiement
qui suit `backend/.env.example` à la lettre ne saura pas qu'il doit les poser.

### Variables lues directement via `os.environ` (hors modèle `Settings`)

| Fichier | Variable | Où vit la valeur | Consommateur | Constat |
|---|---|---|---|---|
| `backend/app/services/llm_router_service.py:290-291` | `ANTHROPIC_API_KEY` (nom configurable via `backend/config/llm_routing.yaml` clé `api_key_env`) | `.env` hors dépôt | Appels Claude (routeur LLM) | Pas de valeur en clair trouvée. Absente de `backend/.env.example` (voir ci-dessus). |
| `backend/app/services/stripe_service.py:45-54` | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO`, `STRIPE_PRICE_ID_TEAM` | `.env` hors dépôt | Facturation Stripe, webhook `backend/app/api/routes/billing.py` | Défaut `""` dans le code — pas de valeur en clair dans `backend/app/`. `docs/STRIPE_PROD_CHECKLIST.md` documente les noms de variables avec des valeurs masquées (`sk_test_…`, `pk_test_…`, `whsec_…`) — pas de valeur réelle lue. Absentes de `backend/.env.example`. |
| `backend/app/api/routes/journal_webhook.py:23` | `JOURNAL_WEBHOOK_SECRET` | `.env` hors dépôt | Endpoint webhook journal | Défaut `""` ; la route refuse la requête si non configuré (`journal_webhook.py:48`) — pas de repli silencieux. Absente de `backend/.env.example`. |
| `backend/app/services/sophie_concierge_service.py:46` | `CHAT_IP_SALT` | `.env` hors dépôt | Hachage IP visiteur (concierge public) | Défaut `""` ; `RuntimeError` explicite si non configuré (`sophie_concierge_service.py:76-82`) — comportement correct depuis LOT-E (cf. `docs/audit-20260821/rapport-kimi.md` `kim:COH-05`). Absente de `backend/.env.example`. |

### Secrets par fichier — valeur en clair dans le dépôt (grep confirmé)

| Fichier | Variable / secret | Où vit la valeur | Consommateur | Constat |
|---|---|---|---|---|
| `CLAUDE.md` (section « Reporting », ligne ~169-170) | jeton de bot Telegram + `chat_id` | **en clair, dans le dépôt** | Snippet Python de reporting manuel (aucun module applicatif ne l'importe) | Confirmé par grep : un jeton au format `bot<chiffres>:<clé>` et un `chat_id` numérique apparaissent en clair dans `urllib.request.urlopen(...)`. Présent depuis le commit qui a introduit ce fichier (confirmé par `git log -S` sur le motif du chat_id : 1 commit). Valeur en clair : **oui**. |
| `backend/app/api/routes/blog.py:16` | mot de passe PostgreSQL (repli de `DATABASE_URL`) | **en clair, dans le dépôt** | `os.getenv("DATABASE_URL", "postgresql://digital_humans:<mot de passe>@localhost:5432/digital_humans_db")` | Confirmé par grep. Valeur en clair : **oui**. Le repli n'est utilisé que si `DATABASE_URL` n'est pas positionnée — mais la valeur reste lisible dans le dépôt et son historique. |
| `backend/app/services/document_generator.py:40` | idem | **en clair, dans le dépôt** | idem, repli `DATABASE_URL` | Confirmé par grep. Valeur en clair : **oui**. Même mot de passe que ci-dessus. |
| `backend/app/services/sds_template_generator.py:24` | idem | **en clair, dans le dépôt** | idem, repli `DATABASE_URL` | Confirmé par grep. Valeur en clair : **oui**. Même mot de passe que ci-dessus. |

Constat sur `docs/audit-20260821/EXECUTION.md` §5.3 : ce document annonçait
**7 fichiers** portant ce mot de passe en dur, dont 4 fichiers de test/outillage
(`backend/tests/e2e/test_sds_workflow_e2e.py`, `backend/tests/test_wbs_task_types.py`,
`backend/tests/test_wizard_phase5.py`, `tools/lib/collect_sds.py`). Grepé à
nouveau dans ce worktree le 02/09/2026 : ces 4 fichiers existent mais ne
contiennent plus le motif `postgres` — **infirmé pour ces 4-là, confirmé et
inchangé pour les 3 fichiers `backend/app/` ci-dessus**. Le mot de passe reste
présent dans l'historique git (`git log --all -S` sur le motif : 2 commits).

### Secret consommé sans jamais transiter par un `.env` du dépôt

| Fichier | Secret | Où vit la valeur | Consommateur | Constat |
|---|---|---|---|---|
| `scripts/dh-watchdog.sh:4-6` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `/root/workspace/dh-comite/.env`, **hors de ce dépôt** | Alerte watchdog VPS | Confirmé par lecture : le script lit un `.env` situé hors du dépôt versionné, jamais un fichier suivi par git. Pas de valeur en clair dans le dépôt. À l'inverse de `CLAUDE.md` ci-dessus, qui porte le même type de secret (bot Telegram) mais en clair et versionné. |

### Scripts de rotation existants (pas de secret hardcodé)

| Fichier | Rôle | Constat |
|---|---|---|
| `scripts/rotate_anthropic_key.sh` | Rotation interactive de `ANTHROPIC_API_KEY` sur le VPS | Lu : demande la nouvelle clé en saisie interactive, écrit dans `.env`, ne contient aucune valeur en dur. |
| `backend/scripts/rotate_encryption_key.py` | Rotation / migration de `CREDENTIALS_ENCRYPTION_KEY` | Lu : prend la nouvelle clé en argument, ne contient aucune valeur en dur. |

### `GITHUB_TOKEN` — écart avec `docs/operations/secrets-rotation.md`

`docs/operations/secrets-rotation.md` §7 (document préexistant, hors périmètre
de ce lot) décrit `GITHUB_TOKEN` comme vivant dans `backend/.env`, consommé par
`jordan_deploy_service`. Grep dans ce worktree : `backend/app/models/project_credential.py:17`
définit un type `GIT_TOKEN`, et `backend/app/services/jordan_deploy_service.py:77`
le lit via `SELECT encrypted_value FROM project_credentials WHERE ... credential_type = 'GIT_TOKEN'`
— **un identifiant par projet, chiffré en base, pas une variable globale de
`.env`**. Aucune valeur en clair trouvée dans le dépôt pour ce secret. Ce
document existant n'a pas été corrigé : hors périmètre de ce lot (`docs/operations/`
n'y figure pas).

### Historique git — sondage ciblé

`git log --all -p -S"sk-" --oneline` (masqué, réponse binaire) : **1 commit**
correspond, et chaque occurrence retrouvée dans son diff est un gabarit
placeholder (`sk-...`, `sk-your-openai-api-key-here`, `sk-ant-api03-...`),
jamais une valeur réelle. `git log --all -S"<mot de passe PostgreSQL, masqué>"` (motif du mot
de passe PostgreSQL trouvé ci-dessus, masqué) : **2 commits**. `git log --all
-S` sur le motif du `chat_id` Telegram (masqué) : **1 commit**. Ce sondage est
ciblé sur les motifs déjà identifiés en §2 ; il ne prouve pas l'absence
d'autres secrets dans l'historique (voir §6).

## 3. Secrets exposés dans le dépôt — à faire tourner immédiatement

Liste de ce qui doit tourner **dès que possible**, avec l'endroit ou la
commande pour régénérer. Aucune rotation n'a été exécutée par ce lot.

- **Jeton de bot Telegram + `chat_id`** (`CLAUDE.md`, en clair, dans
  l'historique) : régénérer le jeton via **@BotFather** sur Telegram
  (`/revoke` puis `/token` sur le bot concerné, ou création d'un nouveau bot),
  puis retirer la valeur en clair de `CLAUDE.md` et la faire lire depuis un
  fichier hors dépôt (sur le modèle de `scripts/dh-watchdog.sh`, §2). Le
  `chat_id` n'est pas un secret de sécurité au même titre, mais republier le
  couple jeton+chat_id revient à republier un canal d'alerte utilisable par
  quiconque lit le dépôt.
- **Mot de passe PostgreSQL** (`backend/app/api/routes/blog.py:16`,
  `backend/app/services/document_generator.py:40`,
  `backend/app/services/sds_template_generator.py:24`, en clair, dans
  l'historique) : changer le mot de passe du rôle applicatif —
  `ALTER USER <role> WITH PASSWORD '<nouveau mot de passe>';` (procédure déjà
  décrite dans `docs/operations/secrets-rotation.md` §5) — puis retirer le
  repli en dur des trois fichiers (hors périmètre de ce lot : ce sont des
  fichiers `backend/app/`, pas `docs/BACKLOG_TECH.md` ni `docs/SECURITY.md`).
- **Clé Anthropic (`ANTHROPIC_API_KEY`)** : aucune valeur en clair trouvée
  dans ce grep, mais une rotation de routine reste recommandée par
  `docs/operations/secrets-rotation.md` (cadence 90 jours) via la console
  **console.anthropic.com** et `scripts/rotate_anthropic_key.sh`.
- **Clés Stripe** (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`) : aucune
  valeur en clair trouvée ; en mode test à ce jour selon
  `docs/STRIPE_PROD_CHECKLIST.md`. Régénération via le **dashboard Stripe**
  (Developers → API keys / Webhooks) si une fuite est un jour suspectée.
- **`CREDENTIALS_ENCRYPTION_KEY`** : non posée en production selon
  `docs/audit-20260821/EXECUTION_VAGUE2.md` §5.2 (garde-fou inerte tant que
  `DEBUG=True`) — ce n'est pas une fuite mais une absence. Génération :
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  Ne pas la poser sans suivre l'ordre décrit dans
  `docs/audit-20260821/BASCULE_DEBUG_FALSE.md` (§4 ci-dessous).

## 4. Procédure de rotation par secret

`docs/operations/secrets-rotation.md` (document préexistant, hors périmètre de
ce lot) détaille déjà la procédure pas à pas pour `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY`, `DATABASE_URL`, `SECRET_KEY`, `GITHUB_TOKEN` et
`SALESFORCE_ACCESS_TOKEN` (sauvegarde, remplacement, validation, révocation de
l'ancienne valeur). Ce document n'y ajoute que ce qui en est absent, et
l'avertissement d'ordre qui s'applique à `SECRET_KEY` et
`CREDENTIALS_ENCRYPTION_KEY` ensemble.

- **`CREDENTIALS_ENCRYPTION_KEY`** — absente de `docs/operations/secrets-rotation.md`.
  Procédure : `backend/scripts/rotate_encryption_key.py` (à blanc puis
  `--apply`), séquence complète dans
  `docs/audit-20260821/BASCULE_DEBUG_FALSE.md`.
- **Effet de bord `SECRET_KEY` ↔ `CREDENTIALS_ENCRYPTION_KEY`** — **à lire
  avant toute rotation de `SECRET_KEY`** : quand `CREDENTIALS_ENCRYPTION_KEY`
  est absente et `DEBUG=True`, `backend/app/config.py` dérive la clé de
  chiffrement des credentials **depuis `SECRET_KEY`** (garde-fou inerte,
  documenté dans `docs/audit-20260821/EXECUTION_VAGUE2.md` §5.2 et
  `docs/audit-20260821/BASCULE_DEBUG_FALSE.md`). Dans cet état, faire tourner
  `SECRET_KEY` seule — geste par ailleurs banal, prévu par
  `docs/operations/secrets-rotation.md` §6 en cas de fuite de jeton — rend
  d'un coup **illisibles tous les credentials Salesforce et Git de tous les
  projets** (`InvalidToken` à chaque lecture). Avant de faire tourner
  `SECRET_KEY` sur un environnement où `CREDENTIALS_ENCRYPTION_KEY` n'est pas
  posée, poser d'abord une clé dédiée en suivant
  `docs/audit-20260821/BASCULE_DEBUG_FALSE.md` (ordre impératif : rotation des
  jetons en clair → clé dédiée → redémarrage → bascule `DEBUG=False`).
- **`STRIPE_SECRET_KEY` / `STRIPE_PUBLISHABLE_KEY` / `STRIPE_WEBHOOK_SECRET` /
  `STRIPE_PRICE_ID_*`** — absentes de `docs/operations/secrets-rotation.md`.
  Régénération dans le dashboard Stripe (Developers → API keys /
  Webhooks / Products), puis mise à jour de `.env` et redémarrage. Pas de
  script dédié dans ce dépôt à ce jour.
- **`CHAT_IP_SALT`** — absente de `docs/operations/secrets-rotation.md`.
  Rotation : générer une nouvelle valeur aléatoire, la poser dans `.env`,
  redémarrer. Effet de bord : les hachages d'IP déjà stockés avec l'ancien sel
  ne correspondront plus au nouveau — pas de procédure de ré-hachage dans ce
  dépôt à ce jour.
- **`JOURNAL_WEBHOOK_SECRET`** — absente de `docs/operations/secrets-rotation.md`.
  Rotation : générer une nouvelle valeur, la poser dans `.env`, mettre à jour
  l'émetteur du webhook en même temps (sinon 403 immédiat, comportement voulu
  — pas de repli silencieux, `journal_webhook.py:48`).
- **Jeton de bot Telegram** (`CLAUDE.md`) — voir §3. Après régénération via
  BotFather, faire lire la valeur depuis un fichier hors dépôt (comme
  `scripts/dh-watchdog.sh` le fait déjà), jamais depuis `CLAUDE.md`.

## 5. Gestionnaire de secrets retenu

**À décider.** Ce lot ne tranche pas. Options identifiées, sans
recommandation :

- **Rester sur `.env` par service**, hors dépôt, avec la discipline actuelle
  (gabarit `backend/.env.example` à jour, script de rotation par secret sur le
  modèle de `scripts/rotate_anthropic_key.sh`).
- **HashiCorp Vault** — déjà cité comme piste dans
  `docs/operations/secrets-rotation.md` §10 (« Next steps »).
- **AWS Secrets Manager** — également cité au même endroit.

## 6. Ce que ce document ne couvre pas

- Les fichiers hors du périmètre grepé en §1 (par exemple `frontend/`, `n8n/`,
  `.github/`) n'ont pas été inspectés pour ce document.
- Aucune rotation n'a été exécutée : ce document décrit, il n'agit pas.
- Le sondage d'historique git (§2) est ciblé sur les motifs déjà trouvés en
  clair dans l'état actuel du dépôt ; il ne constitue pas un audit exhaustif
  de l'historique complet.
- `docs/audit-20260821/EXECUTION.md` §5.3 signalait aussi des identifiants
  d'org Salesforce exposés dans l'historique, hors périmètre du grep de
  secrets de ce lot (motifs `SECRET_KEY`/`API_KEY`/`TOKEN`/etc., pas des
  identifiants d'org) — non revérifié ici.
- `docs/operations/secrets-rotation.md` reste le document de référence pour la
  procédure opérationnelle pas à pas (sauvegarde, validation, révocation) des
  secrets qu'il couvre déjà ; ce document ne le duplique pas et ne le corrige
  pas au-delà du constat sur `GITHUB_TOKEN` en §2.
