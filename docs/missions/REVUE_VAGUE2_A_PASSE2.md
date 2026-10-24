# Revue indépendante, passe 2 — Vague 2 / File A — RAG et données (AS-06)

**Testeur :** testeur-A2. Je n'ai vu ni le travail ni la première revue se faire. **Rédigée le 24/10/2026.**
**Worktree :** `/root/workspace/wt-vague2-a` · **Branche :** `claude/vague2-a` · **HEAD revu :** `c9373fcba98d9e11c8cecb26501075df1317a1f2` (base `388299a`).
**Lu :** la mission `VAGUE2_A_RAG_DONNEES.md`, la revue 1 `REVUE_VAGUE2_A.md` (`d28b8d1`), le rapport `RAPPORT_VAGUE2_A.md` (§3 et §8 en entier), les diffs de `8ce1fdd`, `63d2b03`, `f933d01` et `426b2fe`.
**Journaux :** sous `/root/.dh_orch_vague2/`, préfixe `testeur-A2-`. Copies d'export sous `/root/.dh_orch_vague2/testeur-A2/<scénario>/`.

Conventions. « Exécuté » : j'ai lancé la commande et je cite sa sortie. « Lu, non exécuté » : lecture seule. Je n'ai rien modifié dans le worktree hormis ce fichier. Aucune commande git dans le répertoire de production, aucun appel de modèle, aucune alerte réelle : `alerter_admin` est capturé par la fixture `env`, et uvicorn tourne avec `--lifespan off`.

---

## Verdict : **À REPRENDRE** (défauts mineurs ; les 4 reprises de la revue 1 sont corrigées)

Les quatre reprises sont corrigées. Pour chacune, le test est rouge sur le code d'avant la reprise et vert à HEAD, et je l'ai re-mesuré. La suite complète est sans régression : mêmes 31 échecs que la référence, et 1 085 passés, soit +33. La mesure sous uvicorn est confirmée, avec un contrôle négatif sur le code parent.

Il reste **deux défauts mineurs** (§3). Le premier est un nouveau repli silencieux introduit par la reprise 2 : la commande `--reprendre` sort en code 0 et affiche « encore en attente : 0 » alors qu'un effacement vient de passer `bloque`. Le second est une affirmation inexacte sur la portée de la reprise 1 : un ajout compensé par une suppression n'est **pas** vu à la requête suivante. La règle « jamais de repli silencieux » ne permet pas de conclure « conforme ». Comme cette passe est la dernière, ces deux points sont à consigner comme ouverts pour Sam.

| Reprise | Corrigée | Rouge sur le code d'avant | Vert à HEAD |
|---|---|---|---|
| 1 — `_verifier_classement`, cache à vie | **oui** | **oui** (2 tests, voir la réserve d'instrument en §2.1) | **oui** |
| 2 — `reprendre_effacements_en_attente` arrêtée par un orphelin | **oui**, testée seule (`63d2b03` sans `f933d01`) | **oui** | **oui** (seule et à HEAD) |
| 3 — `doc.collection_name or "technical"` | **oui** | **oui** | **oui** |
| 4 — assertion lot_c devenue vide | **oui** | **oui** sur un mutant ciblé (commit de test seul) | **oui** |

---

## 1. Suite complète à HEAD (exécutée)

```
$ cd /root/workspace/wt-vague2-a/backend && nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurA2_head; /root/workspace/wt-vague2-a/backend/venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' > /root/.dh_orch_vague2/testeur-A2-suite-head.log 2>&1 &
...
31 failed, 1085 passed, 2 skipped, 7 xfailed, 1636 warnings in 802.81s (0:13:22)
PYTEST_EXIT=1

$ grep "^FAILED" testeur-A2-suite-head.log | sed 's/ - .*//' | sort > testeur-A2-suite-head-failed.txt
$ grep "^FAILED" reference_tests.log | sed 's/ - .*//' | sort > testeur-A2-reference-failed.txt
$ diff testeur-A2-reference-failed.txt testeur-A2-suite-head-failed.txt && echo "MEMES ECHECS QUE LA REFERENCE"
MEMES ECHECS QUE LA REFERENCE
$ sed 's/::.*//' testeur-A2-suite-head-failed.txt | sort | uniq -c
      3 FAILED tests/test_auth.py
      1 FAILED tests/test_emma_phase3.py
     27 FAILED tests/test_lot_c_injection_commandes.py
$ grep -E "^[0-9]+ failed" reference_tests.log
31 failed, 1052 passed, 2 skipped, 7 xfailed, 1464 warnings in 573.41s (0:09:33)
```

- On passe de 1 052 à 1 085 passés, soit +33 : 29 tests de la remise initiale (décompte de la revue 1) et 4 tests ajoutés par les reprises 1 à 3. La reprise 4 modifie un test existant. Ce chiffre est égal aux 1 085 annoncés au §8 du rapport.
- Les compteurs `skipped` et `xfailed` sont inchangés (2 et 7). Aucun marqueur n'a été ajouté :
  `git diff origin/claude/vague-c-20260906...HEAD -- backend | grep -nE "^\+.*(pytest\.mark\.(skip|xfail)|pytest\.skip|xfail)"` → aucune ligne (`grep_rc=1`).
- La base de comparaison vaut bien la référence : `git merge-base origin/claude/vague-c-20260906 HEAD` = `388299aa…` = `origin/claude/vague-c-20260906`.

## 2. Reprises, une par une

**Méthode (exécutée).** Script `testeur-A2-prep.sh`, journal `testeur-A2-prep.log`. Pour chaque scénario, j'exporte HEAD (`git archive HEAD backend`) dans `testeur-A2/<scénario>/`, je remplace **tout `backend/app`** par `git archive <commit> backend/app`, et je garde les tests de HEAD. Les commandes passent par le venv du worktree (`testeur-A2-run.sh`). Je n'ai fait aucun `checkout` dans le worktree. Le contrôle `cmp` indique, pour chaque scénario, quels fichiers de code diffèrent de HEAD :

```
== r1_rouge : backend/app de d28b8d1, tests de HEAD     (= 8ce1fdd^)
  differe de HEAD: app/api/routes/documents.py, app/models/effacement_compte.py, app/services/account_service.py, app/services/rag_service.py, app/services/rag_visibilite.py
== r1_vert : backend/app de 8ce1fdd, tests de HEAD
== r2_rouge : backend/app de 8ce1fdd, tests de HEAD     (= 63d2b03^)
== r2_seul : backend/app de 63d2b03, tests de HEAD
  differe de HEAD: app/api/routes/documents.py, app/services/account_service.py, app/services/rag_service.py
== r3_vert : backend/app de f933d01, tests de HEAD
  (aucune difference : f933d01 est le dernier commit de code)
```

### 2.1 Reprise 1 — verdict de classement gardé à vie (`8ce1fdd`) — **corrigée**

**Le correctif (lu).** Un verdict, positif ou négatif, n'est réutilisé que si `collection.count()` est inchangé **et** s'il date de moins de `DELAI_REVERIFICATION_CLASSEMENT_S` (300 s). Sinon, la collection est revérifiée.

**Ce que prouvent les tests (lus).**
- `test_un_chunk_non_classe_ajoute_apres_verification_est_signale` rejoue exactement la sonde E de la revue 1. Une première requête est vérifiée sans signalement. Un chunk `{"source": "ingest_all_docs"}` sans `visibility` est ensuite ajouté. La seconde requête doit donner `signalements == ["technical"]` et `docs2 == []`. Ce test **prouve** la reprise pour le cas d'un ajout qui change le compte.
- `test_une_visibilite_modifiee_sans_changer_le_compte_est_revue_apres_le_delai` ramène le délai à 0, passe `visibility` à `"Public"` (valeur inconnue) à compte constant et attend un signalement. Il **prouve** la revérification périodique, mais pas la durée de 300 s elle-même (voir §3, D2).

**Rouge et vert (exécutés).**
```
# r1_rouge_aide : code de 8ce1fdd^ + tests de HEAD + tests/vague2_a_outils.py de 8ce1fdd^ (testeur-A2-r1-rouge-aide.log)
E       AssertionError: chunk non classé ajouté après vérification exclu en silence : docs2=['DOC-PUBLIQUE-SEC04-ed21f0 — documentation Salesforce (technical)']
E       AssertionError: valeur de visibilité inconnue non signalée
FAILED tests/test_vague2_a_sec04_rag_cloisonnement.py::test_un_chunk_non_classe_ajoute_apres_verification_est_signale
FAILED tests/test_vague2_a_sec04_rag_cloisonnement.py::test_une_visibilite_modifiee_sans_changer_le_compte_est_revue_apres_le_delai
2 failed, 22 passed, 37 warnings in 24.05s

# r1_vert : code de 8ce1fdd (testeur-A2-r1-vert.log) — sec04 + gl10 + a5
24 passed, 37 warnings in 20.11s
PYTEST_EXIT=0
```

**Réserve d'instrument, dite platement.** Avec l'aide de test **de HEAD** (`tests/vague2_a_outils.py`, qui installe `_collections_classees = {}`) sur le code d'avant la reprise, le rouge est **structurel** et non comportemental. Le code d'avant appelle `.add()` sur un ensemble et trouve un dictionnaire, ce qui donne `6 failed` et 22 lignes `'dict' object has no attribute 'add'` dans `testeur-A2-r1-rouge.log`. Le rouge qui compte est donc celui du scénario `r1_rouge_aide`, où l'aide est remise à `8ce1fdd^` (diff d'une ligne : `set()` contre `{}`). Les deux messages obtenus sont exactement ceux que le rapport cite (`impl-A-r1-rouge.log`).

### 2.2 Reprise 2 — un orphelin arrêtait la boucle de reprise (`63d2b03`) — **corrigée**, testée seule

**Le correctif (lu).** Il ajoute un statut `bloque`, absent de `STATUTS_OUVERTS`. Pour un compte introuvable, il note une erreur datée, envoie une alerte et lève `EffacementIncomplet`. La boucle capte en plus toute autre exception, la note (`partiel`), envoie une alerte et continue.

**Ce que prouve le test (lu).** `test_un_effacement_orphelin_n_arrete_pas_la_reprise_des_autres` crée un orphelin `partiel` (`user_id=None`), puis un effacement valide d'identifiant plus grand. Il vérifie qu'aucune exception ne sort, que `termines == [valide.id]`, que l'orphelin est `bloque` avec « introuvable » dans ses erreurs, qu'une alerte cite son identifiant, que l'effacement valide est `termine` et qu'un second passage rend `[]`. Ce test **prouve** la reprise.

**Rouge, puis `63d2b03` seul (exécutés).** Groupe rgpd03 + b4 + prod09 + lot_b :
```
# r2_rouge : code de 63d2b03^ = 8ce1fdd (testeur-A2-r2-rouge.log)
E       AssertionError: la boucle de reprise s'arrête sur l'orphelin : LookupError('Effacement 1 : compte None introuvable')
E       AssertionError: chunks orphelins après suppression d'un document sans collection : ['proj1_doc4_0']
2 failed, 41 passed, 1 xfailed, 334 warnings in 98.54s (0:01:38)

# r2_seul : code de 63d2b03, SANS f933d01 (testeur-A2-r2-seul.log)
E       AssertionError: chunks orphelins après suppression d'un document sans collection : ['proj1_doc4_0']
FAILED tests/test_vague2_a_rgpd03_effacement_rejouable.py::test_suppression_d_un_document_sans_collection_purge_ses_chunks_ou_qu_ils_soient
1 failed, 42 passed, 1 xfailed, 344 warnings in 94.23s (0:01:34)
```
Avec `63d2b03` seul, le test de la reprise 2 passe. Le seul échec est le test de la reprise 3, ce qui est attendu puisque `f933d01` est absent. Rien d'autre ne casse. Le trou signalé au §8 du rapport (« la version commitée de 63d2b03 seule n'a pas été rejouée isolément ») est donc comblé : **exécuté, conforme**.

**Branche `except Exception`, non couverte par un test (sonde exécutée, `testeur-A2-sonde4.log`).** J'injecte une `KeyError` dans `_executer` pour le premier effacement :
```
[SONDE-4] leve=None termines=[2] e1=partiel erreurs_e1=[{'tentative': 0, 'a': '2026-10-24T14:26:13.615860', 'cause': "KeyError: 'panne generique injectee'"}] e2=termine alertes=['Effacement RGPD en echec']
```
La boucle continue, l'échec est noté et une alerte part. Détail sans gravité : `tentative: 0`, parce que l'exception survient avant l'incrément. Mais voir **D1** pour ce que la CLI en dit.

### 2.3 Reprise 3 — collection devinée à la suppression d'un document (`f933d01`) — **corrigée**

**Le correctif (lu).** `rag_service.delete_document_chunks_partout(document_id)` purge les cinq collections et refuse un `document_id` vide. Le repli `or "technical"` disparaît de `documents.py` et de `account_service.py` (le périmètre stocke `d.collection_name` tel quel, à titre d'information).

**Ce que prouve le test (lu).** `test_suppression_d_un_document_sans_collection_purge_ses_chunks_ou_qu_ils_soient` ingère dans `business`, met `collection_name` à NULL, appelle `DELETE` et attend 200 puis zéro chunk restant. Il **prouve** la reprise.

**Rouge et vert (exécutés).** Rouge à `f933d01^` : `['proj1_doc4_0']` (journaux `r2_rouge` et `r2_seul` ci-dessus). Vert à `f933d01` (identique à HEAD pour le code), `testeur-A2-r3-vert.log` :
```
43 passed, 1 xfailed, 344 warnings in 84.19s (0:01:24)
PYTEST_EXIT=0
```

**`delete_document_chunks_partout` remonte-t-il une erreur si une collection échoue ? Oui (sonde exécutée, `testeur-A2-sonde.log`).** J'ai placé un chunk dans `business` et injecté une panne sur `Collection.get` pour `operations`, qui passe avant `business` :
```
[SONDE-2 panne] statut=502 corps='{"detail":"Suppression des fragments RAG impossible : document conserve, reessayez."}' ligne_gardee=1 fichier=True chunks_business_restants=['proj1_doc4_0'] collections_touchees=['technical_collection', 'operations_collection', 'business_collection']
[SONDE-2 reprise] statut=200 corps='{"deleted":true,"filename":"b.txt","chunks_removed":1}' chunks_business_restants=[]
```
La route répond 502, le document et son fichier sont conservés, puis le second essai purge tout. La boucle s'arrête à la première collection en échec. Le dernier `business_collection` de la liste vient de ma propre relecture des restants, pas de la purge. Il n'y a pas de repli silencieux.

### 2.4 Reprise 4 — assertion lot_c devenue vide (`426b2fe`) — **corrigée**

`426b2fe` ne touche que le test : il n'y a pas de « code d'avant » à rejouer. J'ai donc mesuré sur des mutants de `documents.py`, dans des copies, en lançant côte à côte le garde de HEAD et celui de `426b2fe^` (copié sous le nom `tests/test_lot_c_ancien_426b2fe_parent.py`). Scripts `testeur-A2-r4.sh` et `testeur-A2-r4b.sh`, journaux `testeur-A2-r4.log` et `testeur-A2-r4b.log` :

| Mutant de `documents.py` | Garde HEAD | Garde `426b2fe^` | Lecture |
|---|---|---|---|
| M0 : aucun (code de HEAD) | vert | vert | `2 passed` |
| **M1b** : la ligne `uuid` reste, puis `file_path = project_dir / fichier.filename` | **rouge** : `nom disque derive du nom client : ['file_path = project_dir / fichier.filename']` | **vert** | `1 failed, 1 passed`. L'ancienne assertion était bien vide, la nouvelle détecte. **Preuve de la reprise.** |
| M1 : ligne `uuid` remplacée par `… / fichier.filename` | rouge | rouge | `2 failed`. L'ancien garde échoue aussi, mais sur l'assertion de présence de la ligne `uuid`, pas sur l'assertion visée |
| M2 : `… / safe_filename` | rouge | rouge | `2 failed` |
| M3 : la ligne `uuid` reste, puis `file_path = project_dir / Path(fichier.filename).name` | **vert** | vert | Limite du motif textuel : `[\w.]*filename\b` ne voit pas `Path(…)`. Les tests de comportement le voient : `FAILED test_lot_b…::test_documents_nom_de_fichier_traversant` et `FAILED test_vague2_a_prod09…::test_deux_uploads_de_meme_nom_ne_partagent_pas_le_fichier` (`FileExistsError … notes.txt`), `2 failed` |

Le garde reste textuel. La preuve de comportement repose sur les tests lot_b et prod09, qui attrapent M3. Ce n'est pas un défaut de la reprise.

## 3. Défauts restants

**D1 — [mineur, nouveau repli silencieux introduit par `63d2b03`] La CLI `python -m app.services.account_service --reprendre` déclare un succès alors qu'un effacement est `bloque`.**
- Cause (lu) : `main()` ne compte que `STATUTS_OUVERTS` (`en_cours`, `partiel`) pour « encore en attente » et pour son code de sortie. `bloque` en est exclu par construction. Avant la reprise, ce même cas faisait planter la commande (`LookupError`), ce qui était bruyant. Désormais, elle rend 0.
- Preuve (sonde `test_sonde_1_cli_reprendre_avec_un_effacement_bloque`, `testeur-A2-sonde.log`). Un orphelin `partiel`, deux passages de `main(["--reprendre"])` sur la session de test :
  ```
  [SONDE-1 passage 1] rc=0 sortie='effacements terminés : [] ; encore en attente : 0' statut_orphelin=bloque alertes=1
  [SONDE-1 passage 2] rc=0 sortie='effacements terminés : [] ; encore en attente : 0' statut_orphelin=bloque alertes=1
  ```
  Le passage même qui rencontre l'échec et bloque l'effacement sort en code 0 et affiche « 0 en attente ». La seule trace est une alerte unique, dédupliquée par `rgpd_effacement:<id>:bloque`. Sans Telegram, cette alerte n'existe que dans le journal et le tableau de bord (message `[ALERTE ADMIN] Telegram non configuré …` vu dans `testeur-A2-r1-rouge.log`). Ensuite, plus rien ne mentionne cet effacement. Le passage 2 ne réémet pas d'alerte.
- Attendu : compter et afficher les effacements `bloque` (et ceux tombés en échec pendant le passage), et sortir en code non nul tant qu'il en existe ; un test.

**D2 — [mineur, affirmation inexacte] La portée de la reprise 1 est surestimée.**
- Le commit `8ce1fdd` affirme : « tout ajout est donc revu à la requête suivante ». Le rapport, §3, dit : « l'ajout est détecté à la requête suivante (changement de `count()`) ; une métadonnée modifiée en place, à compte constant, l'est au plus tard 5 min après ». C'est faux quand l'ajout est **compensé par une suppression**, par exemple un script externe qui retire puis réingère un document avec le même nombre de chunks. Le compte ne bouge pas : l'exclusion reste silencieuse jusqu'à 300 s.
- Preuve (sonde `test_sonde_3_fenetre_de_300s_a_compte_constant`, `testeur-A2-sonde.log`, délai réel de 300 s) :
  ```
  [SONDE-3] DELAI_REVERIFICATION_CLASSEMENT_S=300
  [SONDE-3a supprimer+ajouter, compte=2] docs1=['DOC-PUBLIQUE-SEC04-ed21f0 — documentation Salesforce (technical)', 'SECOND-PUBLIC'] docs2=['DOC-PUBLIQUE-SEC04-ed21f0 — documentation Salesforce (technical)'] signalements=[]
  [SONDE-3c apres delai] docs4=[] signalements=['technical']
  ```
  Le chunk `EXTERNE-NON-CLASSE` est exclu sans signalement. Il est signalé une fois le délai écoulé, que la sonde simule en le ramenant à 0. La borne de 300 s est donc réelle, mais elle couvre davantage que « métadonnée modifiée en place ».
  Constat infirmé au passage (3b) : un `upsert` sans `visibility` sur un identifiant existant ne déclasse pas le chunk. Chroma fusionne les métadonnées et le chunk reste public (`docs3=['DOC-PUBLIQUE-SEC04-ed21f0 reingere'] signalements=[]`).
- Attendu : corriger le rapport et le commentaire du code (« tout changement à compte constant, y compris une suppression suivie d'un ajout, est vu au plus 300 s après »). Ou bien choisir un critère plus fin que `count()` si cette fenêtre silencieuse de 5 min n'est pas acceptable. **C'est à Sam de décider.**

**Remarque (pas un défaut ; lu, et mesuré en lecture seule).** `delete_project_document_chunks` filtre sur `document_id` seul, sans `project_id` ni `visibility`. Depuis la reprise 3, ce filtre s'applique aux **cinq** collections. Un chunk du corpus public qui porterait un jour une métadonnée `document_id` (ingestion externe) serait effacé par la suppression d'un document client de même identifiant. Aujourd'hui, aucun chunk de production ne porte cette clé :
```
$ sqlite3 "file:/opt/digital-humans/rag/chromadb_data/chroma.sqlite3?mode=ro&immutable=1" "select key, count(distinct id) from embedding_metadata where key in ('project_id','document_id','visibility') group by key; select count(*) from embeddings;"
91866
```
La première requête ne rend aucune ligne, et il y a 91 866 embeddings. Ajouter `visibility = private` au filtre fermerait ce cas.

## 4. Affirmations de la section « Reprises après revue 1 » : contrôlées

- **Mesure sous uvicorn, « 413 avant tout octet de corps » : re-mesurée, exacte, et cette fois avec un contrôle négatif.** J'ai utilisé le script de l'implémenteur, copié sous `testeur-A2-uvicorn.py`. Seuls changent : une base jetable `digital_humans_test_testeura2_uvicorn` (détruite à la fin), le chemin absolu du venv, la lecture de la réponse tardive et l'option de sauter le cas à 200 Mio. Il est lancé depuis mes copies, en `--lifespan off`, sur un port libre différent de 18084.
  ```
  # HEAD (testeur-A2-uvicorn-head.log)
  [25 Mio] corps annonce=26214400 octets_de_corps_envoyes_avant_reponse=0 reponse='HTTP/1.1 413 Request Entity Too Large' delai=0.81s
  [25 Mio] apres reponse : 26214400 octets acceptes sur 26214400 -> complet
  [200 Mio] corps annonce=209715200 octets_de_corps_envoyes_avant_reponse=0 reponse='HTTP/1.1 413 Request Entity Too Large' delai=0.07s
  [200 Mio] apres reponse : 209715200 octets acceptes sur 209715200 -> complet
  memoire uvicorn avant : {'VmHWM': '189724 kB', ...}  apres 200 Mio : {'VmHWM': '200248 kB', ...}
  base jetable detruite : digital_humans_test_testeura2_uvicorn
  EXIT=0
  # Contrôle négatif : backend/app de 8511943^ (route avec UploadFile = File(...)), testeur-A2-uvicorn-parent.log
  [25 Mio] corps annonce=26214400 octets_de_corps_envoyes_avant_reponse=0 reponse='' delai=10.01s
  [25 Mio] reponse obtenue seulement APRES envoi du corps : b'HTTP/1.1 400 Bad Request'
  EXIT=0
  ```
  Au parent, aucune réponse n'arrive en 10 s tant que le corps n'est pas envoyé. À HEAD, le 413 part sans attendre un octet. La mesure discrimine. La consommation de bande passante après la réponse, quand le corps est vidé, est bien réelle et déclarée ouverte.
- « +4 passés, 1 085, mêmes 31 échecs » : **exact** (§1).
- « Statut `bloque` … alerte » : **exact pour l'alerte** (test et SONDE-1 : `alertes=1`), **mais la CLI le tait** (D1).
- « Une métadonnée modifiée en place … au plus tard 5 min après » : **exact, mais incomplet** (D2).
- Le hook `post-commit` n'aurait rien déployé pour les commits initiaux : **non re-vérifié** (lu seulement).

## 5. Contrôle rapide du reste

Je n'ai pas refait la revue de fond. Rien d'autre ne m'a paru faux en passant. Ce qui reste ouvert au §3 et au §4 du rapport l'est toujours : classement du corpus de production avant déploiement, Stripe, tâches ARQ en cours, deux `DELETE /api/account` simultanés, plafonds d'upload incohérents entre nginx (10 Mo), `config.MAX_FILE_SIZE` et la route (20 Mio). Les deux têtes Alembic à la fusion avec la file C, signalées par la revue 1, sont toujours à traiter.

## 6. Ce que j'ai écrit, et où

- Dans le worktree : ce fichier seulement.
- Sous `/root/.dh_orch_vague2/` :
  - les journaux `testeur-A2-*.log` et les listes `testeur-A2-*failed.txt` ;
  - les scripts `testeur-A2-prep.sh`, `-run.sh`, `-scenarios.sh`, `-r4.sh`, `-r4b.sh` et `-uvicorn.py` ;
  - les copies d'export `testeur-A2/` (avec mes sondes `tests/test_zz_sonde*_testeur_a2.py`, jamais commitées) ;
  - les répertoires temporaires `/tmp/testeura2-uvicorn-*`.
- Bases jetables : `digital_humans_test_testeura2_uvicorn`, détruite (deux fois) ; les bases des exécutions pytest sont gérées par `tests/hermetic.py`.
