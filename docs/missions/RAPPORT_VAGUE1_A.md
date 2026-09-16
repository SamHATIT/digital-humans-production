# Rapport — Vague 1 / File A — Sécurité (AS-01 reste, AS-03, AS-04, AS-05)

**Date :** 16/09/2026 · **Branche :** `claude/vague1-a`, depuis `claude/vague-c-20260906`
à **`f78e8ad`** (PR #11 de la vague 0 fusionnée). **Mission :**
`docs/missions/VAGUE1_A_SECURITE.md`. **Aucune fusion, aucune PR ouverte.**

**Environnement : bac à sable Claude Code, pas le VPS.** Python 3.11,
PostgreSQL 16 et Redis locaux, `frontend/node_modules` absent, réseau sortant
bloqué par le bac à sable *et* par le bootstrap hermétique de la vague 0.
Rien n'a été mesuré sur la production ; aucun service n'a été redémarré ;
`backend/.env` n'a pas été touché. Le venv `backend/venv` est un lien vers un
venv partagé par les quatre agents : **aucun `pip install`** n'a été fait —
c'est ce qui a décidé l'implémentation de l'assainisseur HTML (§ SEC-10).

Commande de toutes les mesures :

```bash
cd /home/user/wt-vague1-a/backend
export $(cat /root/.dh_test_db.env)
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

---

## 0. Mesure de la suite, avant et après (règle 4)

| État | Commit | Résultat |
|---|---|---|
| **Référence, mesurée ici** | `f78e8ad` | `31 failed, 695 passed, 2 skipped, 7 xfailed in 196.87s` |
| **Après les 11 commits** | `595f09b` | `31 failed, 799 passed, 2 skipped, 7 xfailed in 238.94s` |

**+104 verts, 0 rouge nouveau, 0 rouge disparu** : les listes `FAILED`
avant et après, comparées par `comm`, sont **identiques**.

La référence annoncée par l'orchestrateur (`32 failed, 694 passed` sur
`5d35156`) ne s'est pas reproduite à l'identique : sur `f78e8ad` j'ai mesuré
**31 rouges**, c'est-à-dire sans le test instable
`test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections`, qui
est passé dans mes trois exécutions complètes. Les 31 sont exactement ceux
que la vague 0 avait listés : 27 `test_lot_c_injection_commandes.py`
(routeur `agent_tester` démonté par SEC-02), 3 `test_auth.py`, 1
`test_emma_phase3.py` (chemin VPS en dur). Aucun n'a été corrigé ni marqué
xfail.

**Deux rouges ont été introduits puis corrigés en cours de route**, mesurés
par la suite complète et non par déduction : le commentaire d'en-tête de
`app/utils/path_guard.py` citait la chaîne littérale cherchée par
`test_grep_litteral_shell_true_ne_renvoie_rien` ; et deux tests de
`test_auth.py` portaient sur `/register`, fermé par SEC-12. Commit `595f09b`.

**Dit explicitement :** la *cause* de trois rouges antérieurs de
`test_auth.py` a changé. `test_login_success`,
`test_get_current_user_success` et `test_get_current_user_no_token` créaient
leur utilisateur via `/api/auth/register` — déjà refusé avant cette vague
(consentement CGV manquant, plus le rate-limit décrit dans l'en-tête de
`test_vague_b_b3_consentement.py`). Ils reçoivent maintenant un 410. Ils
restent rouges, ils n'ont pas été touchés, et leur réparation appartient à
OPS-06.

---

## 1. Fait, avec preuve

Un commit par constat. Chaque message de commit porte le défaut, la cause, le
correctif et les sorties exécutées ; elles ne sont pas répétées ici en
entier.

| Commit | Constat | Rouge mesuré avant | Vert mesuré après |
|---|---|---|---|
| `d76de68` | SEC-11 | `5 failed, 2 passed` | `35 passed` (avec SEC-01/02 et le bootstrap hermétique) |
| `7c91ad2` | SEC-05 | `3 failed, 2 passed` | `33 passed, 1 xfailed` |
| `64b3c42` | SEC-19 | `4 failed, 3 passed` | `21 passed, 1 xfailed` |
| `4b08a2a` | SEC-06 | `3 failed, 2 passed` | `34 passed` |
| `c67d2db` | BILL-05 + SEC-08 | `13 failed, 3 passed` ; puis `6 failed, 11 passed` garde présente non branchée | `17 passed` |
| `afedda9` | SEC-10 | `6 failed, 1 passed` | `48 passed, 1 xfailed` |
| `2d1332a` | SEC-15 | `11 failed, 1 passed` | `57 passed` (+ 3 rouges antérieurs de `test_auth.py`) |
| `34d0159` | SEC-09 | `19 failed, 1 passed` | `26 passed, 1 skipped` |
| `761719f` | SEC-12 | `4 failed, 2 passed` | `30 passed` |
| `100bffe` | SEC-03 | `18 failed, 3 passed` | `60 passed` |
| `595f09b` | — (deux rouges introduits, corrigés) | — | `3 failed, 5 passed` (les 3 = référence) |

**Trois modules de garde neufs**, écrits dans le périmètre de la file A pour
que les autres files puissent les appeler sans dupliquer la règle :

- `backend/app/utils/build_guard.py` — droit d'écrire en BUILD (route et
  worker), et fermeture des écritures Salesforce (SEC-08 / BILL-05) ;
- `backend/app/utils/url_guard.py` — destinations réseau sortantes (SEC-09) ;
- `backend/app/utils/path_guard.py` — chemins d'écriture (SEC-03) ;
- plus `backend/app/utils/redaction.py` (SEC-15) et
  `backend/app/utils/html_sanitizer.py` (SEC-10).

**Deux migrations** : `016_sec06_sds_versions_unicite` (contrainte unique
`(project_id, version_number)`, qui **refuse de s'appliquer** en nommant les
collisions déjà présentes plutôt que de choisir seule) et
`017_sec12_chat_logs_reclamation` (colonne `claimed_by_user_id`, **non
remplie** depuis `email_collected` : ce serait reconduire exactement
l'assimilation que SEC-12 reproche).

### Quelques mesures qui méritent d'être lues

- **SEC-05** : trois de mes premiers verts l'étaient pour la mauvaise raison
  — préfixe de route erroné (`/api/hitl/...` au lieu de
  `/api/pm-orchestrator/...`), donc 404 partout. Corrigé avant de conclure
  (règle 2).
- **SEC-06** : un `SELECT … FOR UPDATE` sur la ligne du projet bloquait
  indéfiniment le middleware d'audit — `audit_logs` porte une clé étrangère
  vers `projects`, et un contrôle de FK prend un verrou incompatible.
  Diagnostiqué par `pg_blocking_pids`, remplacé par un verrou consultatif.
- **SEC-08** : un test était vert avant tout correctif parce que le
  déploiement échouait faute d'org configurée dans le bac à sable, pas grâce
  à une garde. Assertion resserrée sur un code de refus stable avant de
  corriger.
- **SEC-09** : mon premier contrôle négatif utilisait `203.0.113.10`, que
  `ipaddress` classe comme non publique (plage de documentation) — le
  validateur avait raison, le test avait tort.

---

## 2. Non confirmé

Rien de ce qui a été mesuré dans cette file n'a infirmé un constat d'Astra :
**les onze constats confiés étaient tous vérifiables sur `f78e8ad`**, chacun
par un test rouge dont la sortie est dans le commit correspondant.

Deux nuances, qui ne sont pas des infirmations mais des écarts avec la
lettre du rapport :

- **SEC-05**, premier volet : la route HITL portait *déjà* le filtre
  `execution_id` sur son propre chargement du livrable, contrairement à ce
  que « la première lecture … l'ignore » laisse entendre. Le défaut réel
  était qu'un identifiant incohérent était **ignoré en silence** puis
  transmis au classificateur, qui le rechargeait sans filtre. La fuite
  mesurée est bien celle décrite ; le point d'entrée diffère.
- **SEC-11** : `scripts/blog_api.py` distribuait bien des JWT Ghost Admin
  sans authentification, mais **son exposition effective sur le port 8765
  n'est toujours pas vérifiée** — je suis dans un bac à sable, je ne peux pas
  la mesurer. La route a été supprimée de toute façon.

**SEC-01 / SEC-02, vérifiés et non refaits** : `tests/test_vague_c_sec01_sec02.py`
(4 tests) joué à chaque étape, vert — routeur `agent_tester` absent des
routes montées, aucune clé Ghost en clair dans `scripts/`, pages de test
publiques absentes.

---

## 3. Reste ouvert

| Sujet | Où | Pourquoi |
|---|---|---|
| Lecture **anonyme** du budget d'exécution (SEC-19) | `app/api/routes/orchestrator/execution_routes.py` | Fichier à intégrateur unique (file C/D). Mesuré à **200 avec le coût en clair**. Diff + test dans `docs/missions/diffs-vague1-a/file-cd-sec19-budget.diff`. |
| Porte BUILD sur la validation de porte, le retry et le worker (BILL-05/AS-05) | `validation_gate_routes.py`, `retry_routes.py`, `workers/tasks.py` | Fichiers file C. La garde existe et est testée par appel direct de service ; il reste à l'appeler à ces trois endroits. `file-c-bill05-garde-build.diff`. |
| Allocation de version SDS dans l'orchestrateur (SEC-06) | `pm_orchestrator_service_v2.py` | File C. Avec la contrainte unique posée, une course s'y traduira par une `IntegrityError` au lieu d'un doublon silencieux — mieux, mais le job échouera. `file-c-sec06-versions-orchestrateur.diff`. |
| Copie intégrale de `sf org display --json` dans un livrable puis un prompt (SEC-15) | `pm_orchestrator_service_v2.py` | File C. La liste blanche est livrée et testée. `file-c-sec15-metadata-salesforce.diff`, avec la requête de repérage des livrables déjà produits. |
| Jeton OAuth envoyé à l'URL saisie au lieu de l'instance retournée par Salesforce (SEC-09) | `app/api/routes/projects.py` | Contrats d'API : file D. `file-d-sec09-oauth-projects.diff`. |
| DNS rebinding (SEC-09) | `app/utils/url_guard.py` | La validation précède la connexion ; la résolution peut changer entre les deux. Fermer demande de se connecter à l'IP validée ou un proxy sortant en liste blanche. Hors périmètre de cette vague. |
| Deux points d'écriture non bordés (SEC-03) | `jordan_deploy_service.deploy_source_code`, `sf_admin_service._generate_object_metadata` | Inatteignables pour Free/Pro tant que toutes les écritures Salesforce sont fermées (SEC-08), mais à border avant l'ouverture Team. |
| Vérification du changement frontend (SEC-10) | `frontend/src/services/api.ts` | Vérifié par **assertion de source** seulement. Le dépôt n'a pas de banc de test frontend et `frontend/node_modules` est absent du bac à sable : `tsc --noEmit` n'a pas pu être joué. À contrôler dans un navigateur avant l'ouverture. |
| Conversations concierge antérieures (SEC-12) | données de production | La migration ne rattache rien automatiquement. Un export RGPD ne rendra plus les conversations antérieures tant qu'elles n'ont pas été revendiquées. Décision d'exploitation à prendre par Sam. |
| Révocation des jetons déjà exposés (SEC-15) | production | Astra le demande ; c'est une action d'exploitation, pas de code. Requête de repérage fournie dans le diff. |

---

## 4. Non fait, et pourquoi

- **SEC-04 (RAG global qui inclut les documents privés), SEC-07, SEC-13,
  SEC-16** : hors de la liste des onze constats de cette file. SEC-04 est
  explicitement planifié en vague 2 (AS-06).
- **Aucune vérification sur le VPS** : la mission place le travail dans un
  bac à sable, et interdit prod, systemd et redémarrages. Tout ce qui est
  écrit ici est mesuré localement.
- **`test_lot_g_db_sessions::test_open_websockets_do_not_pin_connections`** :
  connu instable, passé dans mes trois exécutions complètes, non traité.

---

## 5. Tableau constat par constat

| Constat | Ligne | État | Preuve |
|---|---|---|---|
| **SEC-11** | L203 | **corrigé** | `d76de68` — routeur blog démonté, `--` avant le titre, `/ghost-token` supprimée |
| **SEC-05** | L102 | **confirmé puis corrigé** | `7c91ad2` — filtre d'exécution sur le livrable, filtre de projet sur le BR, 404 sur identifiant incohérent |
| **SEC-06** | L127 | **confirmé puis corrigé** | `4b08a2a` — chemin par projet, écriture exclusive, verrou consultatif, contrainte unique + migration 016 |
| **SEC-19** | L360 | **partiellement corrigé** | `64b3c42` — agents cloisonnés, références secondaires vérifiées ; **budget anonyme ouvert** (file C/D) |
| **SEC-12** | L221 | **confirmé puis corrigé** | `761719f` — `/register` en 410, `signup-confirm` refuse le squat, rattachement par revendication + migration 017 |
| **SEC-09** | L173 | **corrigé, une limite ouverte** | `34d0159` — `url_guard`, redirections non suivies, `GIT_ALLOW_PROTOCOL` ; DNS rebinding ouvert ; chemin OAuth → file D |
| **SEC-10** | L187 | **corrigé** | `afedda9` — assainissement liste blanche, CSP `sandbox`, iframe sans `allow-scripts` |
| **SEC-15** | L269 | **partiellement corrigé** | `2d1332a` — réponse 422 réduite, journaux git expurgés, jeton hors argv ; métadonnées Salesforce → file C |
| **SEC-03** | L53 | **partiellement corrigé** | `100bffe` — `path_guard` sur trois points d'écriture ; deux points restants |
| **SEC-08** | L159 | **corrigé pour l'ouverture** | `c67d2db` — écritures Salesforce fermées au niveau service ; contrôle complet d'org (Team) préparé mais non activé |
| **BILL-05** | L701 | **partiellement corrigé** | `c67d2db` — quatre chemins secondaires garantis ; porte de validation, retry et worker → file C |
| SEC-01 / SEC-02 | — | **fermés, re-vérifiés** | `tests/test_vague_c_sec01_sec02.py`, 4 tests verts |

---

## 6. Diffs non commis, destinés aux autres files

Tous dans **`docs/missions/diffs-vague1-a/`**, commités en tant que documents
(pas appliqués au code) :

| Fichier | File destinataire | Objet |
|---|---|---|
| `file-c-bill05-garde-build.diff` | C | porte BUILD sur `validation_gate_routes`, `retry_routes`, `workers/tasks.py` |
| `file-cd-sec19-budget.diff` | C (reprise) / D (contrat) | authentification + cloisonnement de `GET /execute/{id}/budget`, avec son test |
| `file-c-sec06-versions-orchestrateur.diff` | C | verrou d'allocation dans les deux créateurs de `SDSVersion` de l'orchestrateur |
| `file-c-sec15-metadata-salesforce.diff` | C | liste blanche sur `org_data["result"]`, + requête de repérage des livrables déjà produits |
| `file-d-sec09-oauth-projects.diff` | D | destination bornée et usage de l'instance retournée par Salesforce dans le flux OAuth |

---

## 7. Tests d'autres vagues adaptés — à signaler

Quatre fichiers de test antérieurs devenaient rouges **par construction**,
parce que le comportement qu'ils décrivaient est celui que les constats
demandent de supprimer. Aucun n'a été affaibli : chacun vérifie toujours ce
qu'il vérifiait, sur un compte ou un chemin qui a le droit d'y accéder.

| Fichier | Changement | Pour qui |
|---|---|---|
| `tests/test_lot_b_cloisonnement.py` | ses deux tenants passent en `pro` (l'upload porte désormais sa porte Free) ; il teste le cloisonnement, pas la frontière payante | file B, pour information |
| `tests/test_vague_b_b1bis_credits_hors_orchestrateur.py` | l'analyse de CR se joue sur `compte_pro` ; il teste la facturation | **file B** |
| `tests/test_vague_b_b3_consentement.py` | ses 5 tests `/register` remplacés par un test de fermeture ; le même fichier exerce déjà le consentement sur `signup-request`/`signup-confirm` | **file B** |
| `tests/test_vague_b_b4_droits_rgpd.py` | revendique sa session avant d'exporter/effacer | **file B** |
| `tests/test_auth.py` | ses 2 tests d'inscription remplacés par un test de fermeture | OPS-06 |

---

*Rapport rédigé le 16/09/2026 — file A de la vague 1, bac à sable Claude Code.*
