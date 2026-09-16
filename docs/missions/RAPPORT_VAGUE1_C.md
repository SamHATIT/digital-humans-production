# Rapport — Vague 1 / File C — Pipeline, jobs et reprises (AS-08 + calibration)

**Date :** 16/09/2026 · **Branche :** `claude/vague1-c`, depuis
`claude/vague-c-20260906` a `f78e8ad` (PR #11 de la vague 0 fusionnee).
**Mission :** `docs/missions/VAGUE1_C_PIPELINE_REPRISE.md`.

**Ou ce travail a ete fait :** dans un **bac a sable Claude Code**, pas sur le
VPS. Python 3.11, PostgreSQL 16 et Redis locaux ; reseau sortant bloque par le
bootstrap hermetique **et** par le bac a sable. Aucun appel LLM reel n'a eu
lieu : le transport est simule, et les appels d'agents sont comptes dans
`llm_interactions` comme la mission le demande. Rien n'a ete execute sur le
VPS, ni sur la production, ni sur une org Salesforce.

Chaque « fait » ci-dessous est une commande jouee dont la sortie est collee. Le
reste est dit « lu, non execute ».

---

## 0. Mesure avant / apres (regle 4)

Commande, pour les deux mesures :

```bash
cd /home/user/wt-vague1-c/backend
export $(cat /root/.dh_test_db.env)
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

| Etat | Resultat |
|---|---|
| **`f78e8ad`** (tete de branche, avant tout changement) | `31 failed, 695 passed, 2 skipped, 7 xfailed in 194.12s` |
| **`2da2819`** (avant l'adaptation du test hotfix) | `33 failed, 819 passed, 2 skipped, 7 xfailed in 258.95s` |
| **`64e7f21`** (dernier commit de code) | `32 failed, 824 passed, 2 skipped, 7 xfailed in 252.65s` |

Les trois mesures ont ete jouees en entier, dans le meme bac a sable, avec la
meme commande. Le nombre de tests passe de 695 a 824 : ce sont les **129 tests
ajoutes par cette file** (dix-huit fichiers `test_vague1_c_*.py`, plus les
ajustements de fichiers existants).

Ecart des rouges, par comparaison des listes `FAILED` (`comm` sur les listes
triees) : **aucun rouge de reference n'a disparu** (je n'en ai corrige aucun,
comme demande). Sur `2da2819`, **deux etaient apparus** ; sur `64e7f21`, il
n'en reste **qu'un**, le test instable :

1. `test_hotfix_gpu_model_id.py::test_sophie_chat_ne_rend_pas_un_200_vide` —
   **cause : mon correctif PROD-01.** Ce test remplacait `generate_llm_response`
   (synchrone) ; `chat()` appelle desormais la variante asynchrone, donc le
   double n'etait plus emprunte. Corrige au commit `64e7f21` : le double suit
   le chemin reel, le critere du test est inchange. Verifie :
   `6 passed, 24 warnings in 2.21s` sur
   `tests/test_hotfix_gpu_model_id.py tests/test_vague1_c_prod01_boucle_api.py`.
2. `test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections` —
   **non imputable a cette file**, et deja signale instable par la vague 0
   (« 2 echecs sur 3 »). Mesure faite en ramenant le code a l'etat d'origine :

   ```bash
   git checkout f78e8ad -- backend/app backend/alembic
   # trois executions du test seul :  1 failed / 1 failed / 1 failed
   git checkout HEAD -- backend/app backend/alembic
   ```

   Il echoue donc 3 fois sur 3 sur le code d'origine lorsqu'il est joue seul,
   et il etait passe dans ma mesure de reference (suite complete). Non corrige,
   non marque xfail, signale.

Mesure finale sur `64e7f21`, apres correction du premier : **32 failed**, soit
les 31 rouges de reference **plus** ce seul test instable. Le comptage est
donc exactement celui attendu.

Le chiffre annonce par l'orchestrateur (`32 failed, 694 passed`, mesure du
matin sur `5d35156`) differait d'une unite : le 32e etait le test instable
`test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections`, qui
est passe dans ma mesure de reference. C'est exactement ce que la regle 4
prevoit — le document decrit l'etat au moment ou il a ete ecrit.

Les 31 rouges de reference (liste complete conservee, `comm` sur les listes
`FAILED`) sont anterieurs a cette file et non corriges, comme demande :

| Fichier | Rouges | Cause (lue, non corrigee) |
|---|---|---|
| `test_lot_c_injection_commandes.py` | 27 | routeur `agent_tester` commente dans `app/main.py:147` |
| `test_auth.py` | 3 | OPS-06 (inscription sans consentement) |
| `test_emma_phase3.py` | 1 | chemin VPS en dur, `FileNotFoundError` |

---

## 1. Fait, avec preuve

Trente-et-un commits, un par correctif, chacun precede de son test rouge. Les
sorties de chaque rouge et de chaque vert sont dans les messages de commit ;
je ne les recopie pas toutes ici.

### 1.1 PROD-04 = CAL-11 — le demarrage d'un worker tuait les executions des autres

`4f9ddd1` (rouge), `027828e` (worker), `f76d930` (rouge), `6ee72db` (routes).

La reconciliation ne marque plus FAILED qu'une execution RUNNING dont le job
ARQ est **absent de Redis** (`JobStatus.not_found`). Un job en cours dans un
autre worker (cle `arq:in-progress:`), en file, ou termine, est laisse intact.
La purge de file (`queued_jobs()` + `abort()`) est supprimee : un job en
attente est du travail legitime. Une execution sans `arq_job_id` n'est pas
tuee mais nommee en WARNING.

Pour que ce critere existe, les routes posent desormais `arq_job_id` et
`arq_queue_name` **avant** d'enfiler (`app/workers/enqueue.py`, point de
passage unique des six sites d'enfilage).

Preuve la plus parlante, jouee sur le Redis reel de la session
(`test_vague1_c_injection_de_panne.py`) : deux executions actives, une seule
dont le job a disparu ; apres `startup()`, la premiere est toujours RUNNING,
la seconde est FAILED. C'est le scenario du 15/09 18:0x.

### 1.2 PROD-05 = CAL-03 — la reprise repart du dernier checkpoint

`f14b69e` (rouge), `bae254c`, puis `9603c05` / `aac030b` pour le recul.

`CHECKPOINT_TO_RESUME_POINT` est desormais **publique** et lue par les deux
reprises — automatique (`execute_workflow`) et demandee (`/resume`). Une
execution arretee apres Emma reprend en `phase3`, non plus en `phase2` :
c'est le cas exact de l'execution 172, reprise a la main le 15/09.

Defaut trouve **par** le test d'injection de panne, et corrige : la branche
« Phase 1 SKIPPED » reposait `phase1_pm`, donc faisait **reculer** le
checkpoint des la premiere seconde d'une reprise. Si cette reprise echouait
avant le checkpoint suivant — le cas ordinaire —, la suivante rejouait Olivia
et Emma. Le gain de la vague 3 etait reperdu au deuxieme essai.

### 1.3 CAL-05 — une reprise explicite n'est plus un fantome

`bae254c`. `resume_from` distingue le job orphelin de la reprise demandee.
Une execution CANCELLED reste refusee : une annulation est une decision.

### 1.4 CAL-02 / CAL-04 — un job annule ferme l'execution ; la reprise est une transition legitime

`4c17532` (rouge), `7aae724`.

`asyncio.CancelledError` n'herite pas d'`Exception` : les `except Exception`
de `tasks.py` ne la voyaient pas, et une execution tuee par `job_timeout`
restait RUNNING jusqu'au redemarrage suivant. Les trois taches passent
desormais par `_clore_en_echec` (statut, `execution_state`, motif,
`completed_at`) et **relancent** l'annulation, pour qu'ARQ continue de voir sa
tache annulee.

Table de transitions elargie : `-> queued` depuis tout etat non terminal
(reprise), `-> failed`/`-> cancelled` depuis les `*_complete` et `waiting_*`,
et `sds_phase5_running -> waiting_sds_validation`, qui manquait alors que la
porte du SDS est posee depuis cet etat.

### 1.5 PROD-06 — les portes HITL

`c281993` (rouge), `ad28f2c`. Trois defauts, trois correctifs :

1. **la decision etait perdue** — `pause_for_validation` ecrivait
   `pending_validation` puis demandait la transition ; un refus declenchait un
   `rollback()` qui annulait l'ecriture. L'ordre est inverse ;
2. **la porte etait consommee avant de savoir si la reprise etait possible** —
   l'etat reel au moment de la decision est `waiting_sds_validation`, que
   `resolve_export_action` ne connaissait pas : **toute** approbation de
   `after_sds_generation` rendait 409, apres consommation. `STATES_CONTENT_READY`
   couvre les etats d'attente, et la route joue la decision **a blanc** avant
   d'enregistrer quoi que ce soit ;
3. **la porte se reposait sur le meme contenu** — `empreinte_livrable()`
   (sha256 du resume) rattache l'approbation a une version. Un rejet ne ferme
   rien, un livrable modifie rouvre la porte, et sans livrable a comparer le
   comportement d'origine tient.

### 1.6 CAL-01 / CAL-07 — delai par profil, abandon et annulation cooperative

`8398013` (rouge), `83546e4`.

`job_timeout` suit `DH_DEPLOYMENT_PROFILE` (3600 s en cloud, 21600 s en local)
et se surcharge par `DH_JOB_TIMEOUT_SECONDS` ; un profil inconnu prend la
valeur cloud **en le disant**, une surcharge illisible est refusee.
`allow_abort_jobs = True`. Nouvelle route `POST /execute/{id}/cancel` : note
`cancel_requested_at` **avant** de tenter l'abandon, et abandonne le job sur
**sa** file. Point d'arret cooperatif a l'entree du workflow et apres chaque
checkpoint : l'execution se ferme en CANCELLED, le travail produit reste.

CAL-07 demandait aussi que la file soit memorisee et reutilisee : c'est fait
(`file_de_reprise`), et `validation_gate_routes` n'ecrit plus
`_queue_name="digital-humans"` en dur — trois sites oublies par la vague 0.

### 1.7 GL-10 — une panne RAG alerte l'exploitant et marque l'execution

`4527942` (rouge), `579796f`.

`admin_alert_service` : journal ERROR + Telegram si configure + journal
d'audit, deduplication de 15 minutes. Sans jeton, **aucun envoi n'est tente**
et le journal dit que le transport est inerte. `executions.degraded` porte
`{motif, detail, at}`. L'execution courante suit le fil d'execution
(`execution_context`), ce qui evite de faire traverser `execution_id` par onze
agents. Le contexte rendu aux agents reste vide : rien n'entre dans un prompt.

### 1.8 PROD-07 — les echecs cessent de passer pour un SDS termine

`2439c60` (rouge), `0428e5e`. `_save_deliverable` rend `True`/`False` et trace
`deliverable_not_persisted` ; `_verifier_finalisation_possible()` interdit la
finalisation sur une degradation bloquante ; les echecs d'experts sont traces ;
`/progress` et le flux SSE exposent `degraded` (champ **additif**, cles
existantes asserties inchangees).

### 1.9 PROD-12 — le livrable rendu est celui qui existe

`e5c661c` (rouge), `8a5e25b`. `_generate_sds_document` rend le chemin
**produit** par le convertisseur et verifie le fichier ; `resolve_export_action`
regarde le disque ; la route de telechargement rend 404 avec motif quand le
fichier manque et annonce le type MIME reel.

### 1.10 PROD-01 — le chat Sophie rend la boucle

`63b1b0c` (rouge), `7db6150`. Mesure : pendant un appel de 0,4 s, une tache
temoin n'avancait d'**aucun** pas. Apres bascule sur
`generate_llm_response_async`, elle avance. Controle : le fichier corrige a ete
remis de cote (`git stash`) et les tests rejoues rouges, pour verifier qu'ils
mordent sur le code d'origine.

### 1.11 Critere de sortie d'Astra

`test_vague1_c_injection_de_panne.py` : panne injectee apres chaque phase,
reprise, et comptage des appels dans **`llm_interactions`** (transport simule
qui ecrit une ligne par appel). Verifie : la reprise ne rappelle pas l'amont,
la chaine avance quand meme jusqu'a Marcus, l'execution passe FAILED avec
message, le checkpoint ne recule pas, deux workers ne se marchent pas dessus,
et l'export seul ne relance aucun agent.

### 1.12 Diffs des autres files, appliques

Les cinq diffs transmis ont ete appliques, chacun avec son test :

| Diff | Commits | Etat |
|---|---|---|
| A — BILL-05 garde BUILD (3 chemins) | `a512efc`, `1e8d763` | applique |
| A — SEC-06 verrou d'allocation | `2b509c2` | applique |
| A — SEC-15 jeton d'org | `9767690` | applique |
| B — BILL-10 cout ecrit une fois | `5a937b7`, `1b2eb60` | applique |
| D — GL-16 cron de purge | `30ad174`, `66991fa` | applique |

**Trois fichiers appartenant a d'autres files ont ete copies a l'identique**
(`git show origin/<branche>:<fichier>`) pour que ma branche soit testable :
`app/utils/build_guard.py` et `app/utils/redaction.py` (file A),
`app/services/retention_service.py` (file D). Leurs versions d'origine font
foi a la fusion. Sans eux, ni les gardes ni leurs tests ne peuvent s'executer,
et une garde qui se desactiverait si son module manque serait exactement le
repli silencieux que BILL-05 denonce.

---

## 2. Non confirme — constats infirmes ou nuances

- **CAL-09 — infirme, mesure a l'appui.** Le score de couverture apres revision
  n'est **ni un plafond ni une valeur assignee** : c'est une moyenne ponderee,
  `agents/roles/salesforce_research_analyst.py:261-267`
  (`overall = obj*0.20 + auto*0.15 + ui*0.10 + trace*0.55`, `round(overall, 1)`).
  Execute sur trois entrees : **92,5**, **10,0**, **0**. 85,0 revient parce que
  trois composantes saturent a 100 (dont `ui_coverage`, a 100 par defaut quand
  les UC ne listent aucun composant d'interface) et qu'`auto_coverage` tombe a
  0 : `0.20*100 + 0.15*0 + 0.10*100 + 0.55*100 = 85,0`. C'est la signature
  d'une seule composante a zero, et elle tombe a zero pour la raison de CAL-08 —
  rapprochement par nom exact. Rien a corriger dans le calcul. Test :
  `test_vague1_c_cal09_score_couverture.py` (`2da2819`).
- **PROD-05, « les tests attendaient expressement ces valeurs erronees »** : ce
  n'est plus vrai. La vague 3 avait deja traduit les valeurs emises
  (`resolve_resume_point`) ; ce qui restait faux etait la **regle** de la route
  `/resume`, pas la table.
- **Le retry etait deja garde** pour les taches BUILD (`ensure_feature`) : le
  diff BILL-05 n'y change que la forme. Mesure : ce test etait vert avant
  application.

## 3. Reste ouvert

- **CAL-08** (faux positifs d'Emma sur les variantes terminologiques) : non
  traite. Le rapprochement semantique et la discipline de nommage des prompts
  Marcus/Olivia se verifient en rejouant un brief reel avec des appels LLM — le
  bac a sable n'a pas de reseau. Le test CAL-09 signalera le jour ou ce
  comportement changera.
- **PROD-07, statut `partial`** : Astra demande de separer `completed` /
  `partial` / `failed` / `waiting_validation`. Un statut nouveau change le
  contrat lu par le frontend, qui appartient a la file D de cette meme vague.
  La trace `degraded` porte l'information sans casser personne ; le statut
  reste a trancher.
- **PROD-07, visibilite dans le livrable** : les omissions sont visibles dans
  l'API, pas encore dans le document. Cela suppose une section du SDS, donc
  `sds_section_writer.py`, hors perimetre.
- **PROD-07, porte de comptage des UC** : les UC bruts non parses franchissent
  encore la porte de comptage, et un lot BA echoue est encore ignore si
  d'autres UC existent. Non traite.
- **PROD-12, format canonique** : ce correctif garantit que le format annonce
  est celui du fichier, **pas** qu'il n'y en ait qu'un. La decision « quel
  format est livre le 1er octobre » est une decision produit.
- **PROD-01, seconde moitie** : `chat()` fait encore du SQLAlchemy synchrone
  dans la coroutine. Ces acces sont courts et locaux, la ou l'appel LLM durait
  jusqu'a dix minutes.
- **PROD-02, PROD-03** : hors de mes constats, et toujours ouverts. PROD-03
  (etat SQL valide avant enfilage) est partiellement adouci par l'enfilage
  identifie — l'execution porte desormais son job — mais l'ordre
  « RUNNING puis enqueue » demeure.
- **AS-06 / cloisonnement du stockage** : les deux createurs de version posent
  `file_path` depuis `settings.OUTPUT_DIR`, repertoire **commun** a tous les
  projets. Signale par le diff SEC-06 de la file A, verifie, non traite
  (vague 2).
- **Le VPS** : rien n'y a ete execute. La reconciliation du demarrage, la route
  d'annulation et le delai par profil n'ont ete joues que dans ce bac a sable.
- **Trois tests connectent encore `psycopg2` en dur** vers
  `172.17.0.1/digital_humans_db` (OPS-06, heritage vague 0).

## 4. Non fait, et pourquoi

- **Aucun redemarrage, aucune modification de `.env`, aucune action sur le VPS
  ni sur la production** : interdits par la mission.
- **Aucun appel LLM reel** : le reseau est bloque, et c'est voulu. Tous les
  transports sont simules.
- **Aucune migration jouee sur une base reelle** : les deux migrations sont
  idempotentes et reversibles, mais elles n'ont ete exercees que par la
  creation de schema de la suite de tests (`Base.metadata.create_all`).
- **Aucune renumerotation de migration** : voir l'avertissement ci-dessous.
- **`git push --force`, merge, ou changement de branche** : jamais.

---

## 5. Tableau constat par constat

| Constat | Etat | Ou |
|---|---|---|
| **PROD-01** L378 | corrige (moitie asynchrone) ; SQL synchrone ouvert | `7db6150` |
| **PROD-04** L422 = CAL-11 | corrige | `027828e`, `6ee72db` |
| **PROD-05** L438 = CAL-03 | corrige, + recul du checkpoint | `bae254c`, `aac030b` |
| **PROD-06** L460 | corrige (3 defauts) | `ad28f2c` |
| **PROD-07** L478 | partiellement corrige ; `partial` et livrable ouverts | `0428e5e` |
| **PROD-12** L562 | corrige ; format canonique a trancher | `8a5e25b` |
| **CAL-01** | corrige | `83546e4` |
| **CAL-02** | corrige | `7aae724` |
| **CAL-03** | corrige | `bae254c` |
| **CAL-04** | corrige | `7aae724` |
| **CAL-05** | corrige | `bae254c` |
| **CAL-07** | corrige (file memorisee, abandon, annulation cooperative) | `83546e4`, `6ee72db` |
| **CAL-08** | non traite (necessite des appels LLM reels) | — |
| **CAL-09** | **infirme** : score mesure, pas plafonne | `2da2819` |
| **CAL-11** | corrige (= PROD-04) | `027828e` |
| **GL-10** | corrige (alerte admin + `degraded`) ; sonde `[RAG HEALTH]` = OPS-01, file D/vague 2 | `579796f` |
| **BILL-05** (diff A) | applique | `1e8d763` |
| **SEC-06** (diff A) | applique | `2b509c2` |
| **SEC-15** (diff A) | applique | `9767690` |
| **BILL-10** (diff B) | applique | `1b2eb60` |
| **GL-16** (diff D) | applique | `66991fa` |

---

## 6. Diffs et points destines a d'autres files

Je n'ai **aucun diff non commis a transmettre** : tout ce que j'ai touche
relevait de mon perimetre (orchestrateur, `workers/*`, reprise des routes
orchestrator), a l'exception des trois fichiers copies a l'identique et cites
en 1.12.

Deux points a l'attention des autres files, ecrits ici plutot que corriges :

1. **File D (parcours)** — `sophie_chat_service._build_system_prompt` faisait
   `project_info.get('description', 'Non disponible')[:500]`. Le defaut d'un
   `.get` ne s'applique que si la cle est **absente** : une colonne
   `description` a NULL donnait `None[:500]`, donc un 500 sur le premier
   message de Sophie. **Corrige ici** (`7db6150`) parce que je touchais deja ce
   fichier pour PROD-01, avec son test ; signale pour que la file D le sache.
2. **Exploitation (hors code)** — SEC-15 : des livrables deja produits peuvent
   contenir un `accessToken`. Requete de reperage, en lecture seule sur la base
   de production :
   ```sql
   SELECT id, execution_id, deliverable_type, created_at
   FROM agent_deliverables WHERE content LIKE '%accessToken%';
   ```
   Les jetons effectivement exposes sont a revoquer. Je n'ai pas acces a cette
   base.

---

## 7. Avertissement de fusion — numerotation des migrations

Cette branche ajoute **deux migrations** :

- `016_execution_job_arq.py` — `arq_job_id`, `arq_queue_name`,
  `cancel_requested_at` sur `executions` (`down_revision = "015_free_50_credits_jour"`) ;
- `017_execution_degraded.py` — `degraded` (JSONB) sur `executions`
  (`down_revision = "016_execution_job_arq"`).

Les files A et B ont chacune ajoute leurs propres **016** et **017** : la
collision est certaine. Je n'ai rien renumerote, comme demande. Les deux
migrations sont idempotentes (elles verifient la presence des colonnes avant de
les ajouter) et reversibles, ce qui laisse a l'orchestrateur le choix de
l'ordre.

---

## 8. Commandes de verification

```bash
cd /home/user/wt-vague1-c/backend
export $(cat /root/.dh_test_db.env)

# Toute la file C
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/test_vague1_c_*.py -q -p no:cacheprovider

# Le critere de sortie d'Astra, seul
env -u GITHUB_TOKEN ./venv/bin/python -m pytest \
    tests/test_vague1_c_injection_de_panne.py -q -p no:cacheprovider

# La suite complete (environ 4 minutes)
env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider
```

`env -u GITHUB_TOKEN` est indispensable : le shell du bac a sable porte un
jeton reel, et le bootstrap hermetique refuse de demarrer avec — c'est voulu
(vague 0 / AS-02).
