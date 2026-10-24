# Revue indépendante — Vague 2 / File A — RAG et données (AS-06)

**Testeur :** testeur-A (n'a pas vu le travail se faire) · **Rédigée le 24/10/2026**
**Worktree :** `/root/workspace/wt-vague2-a` · **Branche :** `claude/vague2-a` · **HEAD revu :** `d5a7567d8e17883895f10a7af66892be01159dee` (base `388299a`)
**Lu :** mission `VAGUE2_A_RAG_DONNEES.md`, rapport `RAPPORT_VAGUE2_A.md`, diff complet `origin/claude/vague-c-20260906...HEAD` (18 fichiers).
**Journaux :** tous sous `/root/.dh_orch_vague2/`, préfixe `testeur-A-`.

Conventions : « mesuré / exécuté » = commande lancée par moi, sortie citée. « Lu, non exécuté » = lecture seule. Je n'ai rien refait en production (point f) ; aucune commande dans le répertoire de production.

---

## Verdict : **À REPRENDRE**

Le travail est solide sur l'essentiel : suite sans régression (mêmes 31 échecs que la référence, +29 tests verts), chaque correctif a son test rouge au parent (re-mesuré), migration réversible re-vérifiée, reprise d'effacement re-vérifiée y compris sur une panne que les tests ne couvrent pas. **Mais** une affirmation du rapport est fausse et recouvre un repli silencieux (reprise 1), ce qui interdit le verdict « conforme » selon les critères fixés. Trois reprises mineures suivent.

### Reprises

1. **[bloquante pour « conforme »] `app/services/rag_service.py::_verifier_classement` — exclusion silencieuse après la première vérification ; affirmation fausse au §3 du rapport.**
   - Défaut : une collection trouvée classée entre dans `_collections_classees` **pour toute la vie du processus** (aucune ré-vérification). Un chunk sans `visibility` ajouté ensuite (par exemple par les scripts externes `/opt/digital-humans/rag/ingest_all_docs.py`, cités au §3) est exclu par le filtre **sans aucun signalement**.
   - Le rapport, §3 : « Toute ingestion future par ces scripts créerait des chunks non classés → collection signalée en panne (**bruyant, pas silencieux**). » C'est faux tant que le backend n'a pas redémarré.
   - Preuve (sonde hors dépôt, `testeur-A-sonde/backend/tests/test_zz_sonde_testeur_a.py::test_sonde_e_chunk_non_classe_ajoute_apres_verification`, journal `testeur-A-sonde.log`) : collection temporaire avec un chunk `public`, une requête (vérification passée), ajout d'un chunk `{"source": "ingest_all_docs"}` sans `visibility`, seconde requête :
     ```
     [SONDE-E] docs1= ['PUBLIC'] docs2= ['PUBLIC'] signalements= []
     ```
   - Attendu : ré-vérifier aussi les collections classées (même délai de 5 min, par exemple) ou au minimum corriger le rapport et la docstring ; plus un test rouge-puis-vert « chunk non classé ajouté après vérification → signalé ».

2. **[mineure] `app/services/account_service.py::reprendre_effacements_en_attente` — un échec arrête les suivants, contrairement à sa docstring** (« un nouvel échec est noté, alerté, et n'arrête pas les autres »).
   - Seul `EffacementIncomplet` est intercepté. `reprendre()` lève `LookupError` si `user_id` est NULL (cas rendu possible par `ondelete="SET NULL"` du modèle) ; la boucle s'interrompt et la CLI `--reprendre` aussi.
   - Preuve (sonde `test_sonde_c_effacement_sans_user_bloque_les_suivants`, `testeur-A-sonde.log`) : un effacement orphelin `partiel` + un effacement `en_cours` valide :
     ```
     [SONDE-C orphelin] LEVE LookupError Effacement 1 : compte None introuvable | statut du second : en_cours
     ```
   - Attendu : traiter chaque échec (dont `LookupError`) par élément — noter, alerter, continuer — et un test.

3. **[mineure] `app/api/routes/documents.py::delete_document` — valeur devinée `doc.collection_name or "technical"` (nouvelle dans ce diff).**
   - Au parent : `delete_project_document_chunks(doc.collection_name, document_id)` (lu : `git show 388299a:backend/app/api/routes/documents.py`, l. 266). Le correctif ajoute un repli sur `"technical"`. Si `collection_name` est NULL et que les chunks sont ailleurs, la purge rend 0, la ligne est supprimée, les chunks deviennent orphelins sans bruit. Lu, non exécuté (la colonne a `default="technical"`, le cas est rare). Côté effacement de compte, la seconde passe par projet dans les cinq collections couvre ce cas ; pas côté route de document.
   - Attendu : purger par `document_id` dans les cinq collections (ou refuser une collection inconnue), sans deviner.

4. **[mineure] `tests/test_lot_c_injection_commandes.py::test_documents_upload_assaini_par_lot_b` — une assertion négative héritée est devenue vide.**
   - Le correctif renomme la variable `file` → `fichier`. L'assertion conservée `assert "file_path = project_dir / file.filename" not in src` ne peut plus jamais échouer :
     ```
     $ grep -n "file.filename\|fichier.filename" app/api/routes/documents.py
     305:    safe_filename = Path(fichier.filename or "").name
     ```
   - Attendu : viser `fichier.filename` (ou un motif indépendant du nom de variable). Le reste de la modification est justifié (voir tableau B).

### Points non vérifiés (pas des reprises, à garder ouverts)

- **Vidage du corps par `BaseHTTPMiddleware`.** L'application lit 0 octet (prouvé, voir point a), mais le `receive` brut est vidé en entier. Dans ma sonde ASGI, ce vidage a lieu **avant** `http.response.start`, même pour 200 Mio annoncés (`testeur-A-sonde2.log`) :
  ```
  [SONDE-A2] corps=25165824 statut=413 octets_tires_du_serveur_avant_response.start=25165824 delai_start=0.15s pic=1026648
  [SONDE-A2] corps=209715200 statut=413 octets_tires_du_serveur_avant_response.start=209715200 delai_start=0.05s pic=444880
  ```
  Ma sonde a un `receive` qui ne bloque jamais, donc l'ordre observé peut venir d'elle. Sous uvicorn, `receive` attend le réseau et rend `http.disconnect` une fois la réponse terminée (lu, non exécuté). Le rapport dit « pendant qu'il transmet la réponse » : je n'ai pu ni le confirmer ni l'infirmer. La mémoire reste plate dans tous les cas. Il faudrait une mesure sous un vrai uvicorn (`--lifespan off`, pour ne pas lancer la sonde vers 18084).
- Interaction avec la file B (lu, non exécuté) : `claude/vague2-b` ajoute `app/services/sonde_rag.py`, qui s'appuie sur `rag_service.rag_health_check()` (comptage). Après fusion, la sonde dira « ok » alors que chaque requête RAG sera refusée tant que le corpus de production n'est pas classé. C'est cohérent avec la proposition du rapport (§6) d'y exposer le nombre de chunks non classés.

---

## 1. Suite complète (mesurée)

```
$ cd /root/workspace/wt-vague2-a/backend && nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurA_suite_head; ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' > /root/.dh_orch_vague2/testeur-A-suite-head.log 2>&1 &
...
31 failed, 1081 passed, 2 skipped, 7 xfailed, 1619 warnings in 843.12s (0:14:03)
PYTEST_EXIT=1
```

Comparaison avec la référence de l'orchestrateur (`reference_tests.log` : `31 failed, 1052 passed, 2 skipped, 7 xfailed ... in 573.41s (0:09:33)`) :

```
$ grep "^FAILED" testeur-A-suite-head.log | sed 's/ - .*//' | sort > testeur-A-suite-head-failed.txt
$ grep "^FAILED" reference_tests.log | sed 's/ - .*//' | sort > testeur-A-reference-failed.txt
$ diff testeur-A-reference-failed.txt testeur-A-suite-head-failed.txt && echo "MEMES ECHECS QUE LA REFERENCE"
MEMES ECHECS QUE LA REFERENCE
$ sed 's/::.*//' testeur-A-suite-head-failed.txt | sort | uniq -c
      3 FAILED tests/test_auth.py
      1 FAILED tests/test_emma_phase3.py
     27 FAILED tests/test_lot_c_injection_commandes.py
```

- **+29 passés** (1052 → 1081) = 8 SEC-04 + 13 PROD-09 + 8 RGPD-03 (décompte confirmé par les listes rouges du §2). Échecs identiques, `skipped`/`xfailed` inchangés (2/7). Aucun `skip`/`xfail` ajouté (`git diff ... | grep -E "pytest.mark.(skip|xfail)|pytest.skip|xfail"` : seule occurrence dans le rapport).
- Ciblé, à HEAD, avec `-s` (`testeur-A-vert-ajoutes.log`) : 3 nouveaux fichiers + a5 + gl10 + les deux tests lot_b/lot_c modifiés → `45 passed, 153 warnings in 94.63s`, `PYTEST_EXIT=0`.
- Après tout cela : `git status --short` vide, `git rev-parse HEAD` = `d5a7567d8e17883895f10a7af66892be01159dee`.

## 2. Rouge au parent, correctif par correctif (mesuré)

**Méthode, et écart par rapport à la méthode conseillée.** La suite complète tournait dans le worktree pendant ces mesures, et `test_lot_c` lit le source de `documents.py` à l'exécution : je n'ai donc pas fait `git checkout X^ -- …` dans le worktree. J'ai exporté HEAD (`git archive HEAD backend`) dans `/root/.dh_orch_vague2/testeur-A-parent/<scénario>/`, puis remplacé **uniquement les fichiers de code** du commit par leur version `X^` (`git show X^:backend/<f>`). Les fichiers créés par le commit sont retirés, les tests restent ceux de HEAD. Le venv est celui du worktree. Script : `testeur-A-prep.sh` (contrôle `cmp` : seuls les fichiers de code visés diffèrent de HEAD). Exécution : `testeur-A-rouge.sh`. Le worktree n'a pas été touché.

| Scénario | Fichiers remis à `X^` | Résultat | Journal |
|---|---|---|---|
| SEC-04 `7375a2d` | `rag_service.py` ; `rag_visibilite.py` retiré | `10 failed, 12 passed` | `testeur-A-rouge-sec04.log` |
| PROD-09 `8511943` | `documents.py`, `rag_service.py` | `12 failed, 2 passed` | `testeur-A-rouge-prod09.log` |
| RGPD-03 `98598b1` | `account.py`, `documents.py`, `project_routes.py`, `models/__init__.py`, `account_service.py`, `rag_service.py` ; `effacement_compte.py` et `023a_…` retirés | `8 failed` | `testeur-A-rouge-rgpd03.log` |
| `63f4715` (garde lot_c) | `documents.py` à `8511943^` | `1 failed` | `testeur-A-rouge-lotc.log` |

### A. Tests ajoutés : assertion lue → prouve ? → rouge au parent ?

| Test | Ce que l'assertion prouve (lu) | Rouge au parent (cause relevée dans le journal) |
|---|---|---|
| sec04 `test_le_document_prive_de_a_ne_sort_ni_pour_b_ni_en_recherche_globale` | **Prouve** : sentinelle de A absente pour B et sans projet, 5 collections × 4 niveaux d'appel ; contrôle négatif : la sentinelle sort pour A (le test ne passe pas à vide) | **oui** — `le document privé de A sort ailleurs que pour A : ['query_collection(technical, project_id=global)', 'query_rag(agent=default, …global)', …]` |
| sec04 `test_le_corpus_public_reste_visible_avec_et_sans_projet` | **Prouve** : public rendu pour A, B et sans projet | **oui** — `le corpus public n'est pas rendu pour A` |
| sec04 `test_ingestion_privee_sans_projet_ou_sans_document_refusee` | **Prouve** : `ValueError` et `count` inchangé | **oui** — `DID NOT RAISE <class 'ValueError'>` |
| sec04 `test_ingestion_privee_marque_chaque_chunk_prive_et_rattache` | **Prouve** : `visibility == private`, `project_id` posé | **oui** — `KeyError: 'visibility'` |
| sec04 `test_une_collection_non_classee_est_signalee_pas_servie_en_silence` | **Prouve** à la **première** requête du processus : rien servi, signalement « technical » ; contrôle négatif sur `operations`. **Ne couvre pas** un chunk ajouté après vérification (reprise 1) | **oui** — `'ANCIEN-CHUNK-SANS-VISIBILITE' is contained here` |
| sec04 `test_classement_a_blanc_ne_modifie_rien_et_compte` | **Prouve** : comptes à blanc, aucune métadonnée écrite | oui, mais par `ImportError` (module nouveau) : rouge structurel, pas comportemental. Inévitable pour un outil nouveau |
| sec04 `test_classement_ne_rend_pas_public_un_chunk_sans_metadonnee_sans_decision` | **Prouve** : privés marqués, chunk sans trace laissé non classé, collection toujours signalée | idem (`ImportError`) |
| sec04 `test_classement_public_explicite_puis_idempotent` | **Prouve** : 3 modifiés puis 0 ; publics visibles, privés seulement pour le projet 5 | idem (`ImportError`) |
| prod09 `test_upload_au_dela_du_plafond_refuse_avant_lecture_du_corps` | **Prouve** que l'application ne lit pas le corps : compteur sur `Request.stream()` = 0, pic < 2 Mio, aucun fichier (voir point a) | **oui** — échoue d'abord sur `assert 400 == 413` ; la mesure imprimée au parent montre que le compteur discrimine : `statut=400 octets_lus_par_l_application=25165962 pic_tracemalloc=25936246` |
| prod09 `test_upload_sans_longueur_annoncee_coupe_au_plafond` | **Prouve** : lecture ≤ plafond + marge + 64 Kio, pic < 4 Mio, aucune ligne | **oui** — `assert 400 == 413` ; mesure au parent `octets_lus_par_l_application=29360266 pic_tracemalloc=29619269` |
| prod09 `test_fichier_d_un_octet_de_trop_refuse_meme_sous_la_marge_multipart` | **Prouve** : 413 et aucune ligne pour un fichier de plafond+1 | **oui** — `assert 400 == 413` (au parent, refus en 400 après lecture) |
| prod09 `test_controle_negatif_un_petit_fichier_passe` | Contrôle négatif : 200, `ready`, chunks = `chunk_count` | non (vert au parent, **attendu et déclaré** au rapport) |
| prod09 `test_deux_uploads_de_meme_nom_ne_partagent_pas_le_fichier` | **Prouve** : chemins distincts ; supprimer l'un laisse l'autre intact | **oui** — `deux documents pointent le même fichier disque` |
| prod09 `test_pdf_lu_par_un_vrai_parseur_pas_comme_du_binaire` | **Prouve** : sentinelle dans les chunks, ni `%PDF` ni `endobj` | **oui** — `binaire PDF ingéré comme texte : '%PDF-1.4…` |
| prod09 `test_parseur_pdf_absent_refus_explicite_rien_ingere` | **Prouve** : `fitz`, `PyPDF2`, `pypdf` bloqués → 503, 0 chunk, 0 ligne, 0 fichier | **oui** — `assert 200 == 503` (`"status":"ready"`) |
| prod09 `test_docx_dont_le_contenu_decompresse_depasse_la_borne_refuse` | **Prouve** : 422, aucune ligne | **oui** — `assert 200 == 422` (au parent : ligne créée en `error`) |
| prod09 `test_texte_extrait_au_dela_de_la_borne_refuse_sans_aucun_embedding` | **Prouve** : 422, 0 embedding, 0 ligne | **oui** — `"chunk_count":2501,"status":"ready"` |
| prod09 `test_ingestion_par_lots_bornes` | **Prouve** : somme des `upsert` = n, max ≤ 100 | **oui** — `upsert de 638 chunks d'un coup` |
| prod09 `test_ingestion_en_echec_au_milieu_ne_laisse_aucun_chunk` | Protège le retrait des lots partiels | non (vert au parent, **déclaré** : il protège un comportement introduit par les lots) |
| prod09 `test_quota_d_octets_du_projet_refuse_l_upload_suivant` | **Prouve** : 413 « quota », 1 seule ligne | **oui** — `assert 200 == 413` |
| prod09 `test_quota_de_documents_du_projet` | **Prouve** : 413 au 51ᵉ | **oui** — `assert 200 == 413` |
| rgpd03 `test_effacement_interrompu_par_une_panne_chroma_puis_repris_idempotent` | **Prouve** : `EffacementIncomplet` ; compte inactif non anonymisé ; 2 lignes `project_documents` gardées ; seuls les chunks du document en panne restent ; tâche `partiel` + erreur ; alerte ; Bob intact ; reprise complète (chunks, fichiers dont le snapshot SDS, projet, anonymisation, `termine`, chemins purgés du périmètre) ; rejouer `reprendre` + `supprimer` sans effet (1 seule tâche) | **oui** — `effacement déclaré réussi malgré la panne Chroma` |
| rgpd03 `test_effacement_interrompu_pendant_l_etape_base_puis_repris` | **Prouve** : rollback (projet présent), `partiel`, `reprendre_effacements_en_attente` → `[id]` puis `[]` | **oui** — `RuntimeError('base indisponible (panne injectee)')` brute |
| rgpd03 `test_route_effacement_en_echec_repond_503_puis_reprise_par_le_meme_jeton` | **Prouve** : 503, compte inactif, puis 200 avec le même jeton, 0 chunk | **oui** (journal, 3ᵉ FAILED) |
| rgpd03 `test_echec_de_purge_chroma_n_est_pas_compte_zero` | **Prouve** : l'erreur se propage. Assertion large (`pytest.raises(Exception)`), suffisante ici | **oui** — `DID NOT RAISE <class 'Exception'>` |
| rgpd03 `test_suppression_document_en_echec_chroma_conserve_ligne_et_fichier` | **Prouve** : 502, ligne et fichier gardés, puis 200 et chunks purgés | **oui** — `"chunks_removed":0 … assert 200 == 502` |
| rgpd03 `test_suppression_d_un_document_en_erreur_purge_ses_chunks_partiels` | **Prouve** : chunks d'un document `error` purgés | **oui** — `assert not True` (chunks restants) |
| rgpd03 `test_suppression_d_un_projet_par_le_crud_purge_chroma_et_fichiers` | **Prouve** : 0 chunk, 0 fichier, Bob intact | **oui** — `chunks orphelins après suppression du projet` |
| rgpd03 `test_suppression_d_un_projet_en_echec_chroma_conserve_le_projet` | **Prouve** : 502, projet et 2 documents gardés | **oui** — `assert 204 == 502` |

### B. Tests existants modifiés

| Test | Rouge au parent avec la version HEAD | Jugement |
|---|---|---|
| `test_vague_a_a5…::test_controle_negatif_le_rag_du_projet_999_sort_bien_son_chunk` (renommé) | **oui** — `SEC-04 : la recherche globale sort le chunk prive du projet 999` | **Justifié, renforcé.** L'ancienne version affirmait la fuite (primitive SEC-04). La nouvelle garde le rôle de contrôle négatif (sortie pour 999, absence pour 7) et ajoute l'absence sans projet. La fixture marquée `private` correspond à ce que pose `ingest_document`. |
| `test_vague_a_a5…::test_controle_negatif_get_salesforce_context_du_projet_999_sort_la_sentinelle` (renommé) | **oui** (journal sec04, 10ᵉ FAILED) | **Justifié, renforcé**, même raisonnement. |
| `test_vague1_c_gl10…::test_sans_panne_rien_n_est_signale` | non (vert au parent et à HEAD) | **Justifié, non affaibli.** Il fallait adapter la fausse collection à la nouvelle API (`id`, `count`, `get` → collection entièrement classée). L'assertion « aucun signalement sans panne » est inchangée. |
| `test_lot_b…::test_documents_nom_de_fichier_traversant` | **oui** — `'..' is contained here: evasion.txt and 'evasion.txt' != 'evasion.txt'` | **Justifié.** Les gardes de traversée sont conservées (rien hors du répertoire du projet, un seul fichier) ; nom disque généré ; nom affiché assaini vérifié dans la réponse. |
| `test_lot_c…::test_documents_upload_assaini_par_lot_b` | **oui** — `assert 'file_path =...afe_filename' not in …` | **Justifié sur le fond**, mais **une ligne héritée est devenue vide** (reprise 4). C'est un garde textuel : la preuve de comportement est portée par le test lot_b. |

## 3. Points d'attention propres à A

**(a) « octets lus = 0, pic 0,7 Mo ».** L'instrument compte les octets rendus par `Request.stream()`. C'est la voie de `Request.body()`, de `Request.form()` (analyse FastAPI de `UploadFile`, utilisée au parent) et du `MultiPartParser` de la route (lu dans Starlette, cohérent avec les mesures). Il discrimine : 25 165 962 au parent, 0 à HEAD (tableau A). Ma propre sonde à HEAD (`testeur-A-sonde.log`) compte en plus les appels à `documents.MultiPartParser.parse` :
```
[SONDE-A] {'total': 25165955, 'statut': 413, 'lus_stream': 0, 'brut_avant_start': 25165955, 'brut_total': 25165955, 'parse': 0, 'pic': 706310}
[SONDE-A menteuse] {'total': 25165955, 'statut': 413, 'lus_stream': 21037165, ..., 'parse': 1, 'pic': 1377225}   # Content-Length annonce 1 Kio, corps de 24 Mio : coupé au plafond
```
Le test mesure donc bien la lecture du corps par l'application, et non autre chose. Le pic varie d'une exécution à l'autre : 706 310 octets dans ma sonde, **126 408** dans le test à HEAD (`testeur-A-vert-ajoutes.log` : `[MESURE PROD-09 longueur annoncee] corps=25165962 statut=413 octets_lus_par_l_application=0 pic_tracemalloc=126408`). Il reste toujours sous la borne de 2 Mio ; le « 0,7 Mo » du rapport est une valeur parmi d'autres. Limite : `tracemalloc` ne verrait pas un corps lu puis jeté (morceaux pré-alloués dans le test). C'est le compteur `Request.stream()` qui porte la preuve. Le vidage brut par le middleware est traité dans les points non vérifiés.

**(b) Tests existants modifiés** : voir §2 B. Deux renforcés, deux adaptés sans affaiblissement, une ligne devenue vide (reprise 4).

**(c) Reprise idempotente.** Re-vérifiée par les deux tests rgpd03 (verts à HEAD, rouges au parent). J'ai ajouté une panne **non couverte par les tests** : `PermissionError` sur l'effacement d'un fichier (sonde `test_sonde_c_panne_fichier_puis_reprise`) :
```
[SONDE-C apres panne] partiel dict_keys(['chroma']) [{'tentative': 1, ..., 'cause': 'EchecPurgeHorsBase: purge fichiers : 1 échec(s) — /tmp/dh-test-testeura_sonde-.../uploads/project_documents/1/b37de3ecb2c044f1b6c19e27fe9e17c4.txt : EACCES injecte'}] docs= 2 fichier0 existe= False fichier1 existe= True
[SONDE-C reprise] compte supprimé 2 True termine compte-supprime-1@anonymised.invalid
```
État cohérent (lignes gardées, `partiel`, cause datée), reprise complète, second `reprendre` → `deja_termine=True`. Défaut de la boucle de reprise : reprise 2.

**(d) Migration `023a`.** Base jetable `digital_humans_test_testeura_mig023a`, créée avec le rôle de `TEST_DATABASE_URL` puis détruite. Script `testeur-A-migration.py`, journal `testeur-A-migration.log`. Garde préalable : la base vue par `app.config` dans le sous-processus est bien la base jetable.
```
base vue par app.config : digital_humans_test_testeura_mig023a
$ alembic heads -> rc=0
023a_rgpd03_effacements_comptes (head)
$ alembic stamp 022_sec12_chat_logs_reclamation -> rc=0
table avant upgrade : False
$ alembic upgrade head -> rc=0      Running upgrade 022_sec12_chat_logs_reclamation -> 023a_rgpd03_effacements_comptes
table apres upgrade : True
  fk [{... 'referred_table': 'users', ... 'options': {'ondelete': 'SET NULL'} ...}]
  index ['ix_effacements_comptes_id', 'ix_effacements_comptes_statut', 'ix_effacements_comptes_user_id']
colonnes modele == base : True | nullabilite identique : True
$ alembic upgrade head -> rc=0      (rejoué : sans effet)
$ alembic downgrade 022_sec12_chat_logs_reclamation -> rc=0
table apres downgrade : False
$ alembic upgrade head -> rc=0
table apres re-upgrade : True
MIGRATION_OK
base jetable restante : 0
EXIT=0
```
Le schéma de départ est fait par `create_all` (toutes les tables du modèle sauf `effacements_comptes`) puis `stamp 022`, comme l'implémenteur. La chaîne 001→022 n'est pas rejouée : seule 023a est vérifiée. **Deux têtes à la fusion, mesuré** : `claude/vague2-c` (c37e6aa) contient `023c_consentement_opus.py` avec `down_revision = "022_sec12_chat_logs_reclamation"`. Une révision de fusion sera nécessaire.

**(e) « Collection non classée = panne RAG signalée ».** À la première requête du processus, ce n'est pas un repli silencieux : chemin réel `signaler_rag_indisponible` → `alerter_admin` (capturé, rien envoyé), sonde `test_sonde_e_alerte_reelle_capturee` :
```
[SONDE-E alerte] docs= [] alertes= [('RAG indisponible', "La collection RAG 'technical' est injoignable — hors execution (...).\nCause : CollectionNonClassee: collection technical : 1/1 chunk(s) sans metadonnee 'visibility' — ... Classer avec `python -m app.services.rag_visibilite` (SEC-04).\n...", {'cle_deduplication': 'rag_unavailable:technical:None', 'execution_id': None, 'categorie': 'rag'})]
```
Comportement conforme à l'annonce : rien n'est servi, alerte, `degraded` en exécution (chemin GL-10 couvert par ses tests, verts). Remarque de forme : le texte d'alerte dit « injoignable », ce qui est inexact pour ce motif ; la cause est en revanche exacte. **Après la première vérification réussie, l'exclusion devient silencieuse** : reprise 1. Conséquence de déploiement, honnêtement signalée au rapport §4.1 : sans classement du corpus, toutes les collections seront refusées.

**(f)** Non refait, comme demandé. Les affirmations sur la production (Chroma, `fitz` absent du venv de production) restent celles de l'implémenteur : **non re-vérifiées par moi**.

## 4. Affirmations du rapport : contrôlées / non contrôlées

- Suite avant/après, mêmes 31 échecs, +29 : **re-mesuré, exact** (§1).
- Rouges des trois correctifs et de la garde lot_c : **re-mesurés, exacts** ; les deux tests non discriminants sont bien ceux déclarés.
- Migration réversible : **re-mesuré, exact**.
- « bruyant, pas silencieux » (§3, scripts d'ingestion externes) : **faux tant que le processus vit** (reprise 1).
- « Aucun skip/xfail ajouté » : **exact** (grep + compteurs inchangés).
- `rag_service.py` : `rag_health_check`, cache de santé et `get_openai_embedding` non touchés : **exact** (diff lu).
- `app/main.py`, `app/config.py`, `requirements.txt`, `admin_alert_service.py`, `tests/conftest.py` non modifiés : **exact** (`git diff --stat`).
- Mesures de production (91 866 chunks, `fitz` absent) et contrat frontend : **non re-vérifiés** (consigne f ; lu seulement).

## 5. Fichiers hors zone et recouvrements (mesuré sur les branches actuelles)

Hors zone A (`services/rag*`, `routes/documents*`) : `account_service.py`, `routes/account.py`, `orchestrator/project_routes.py`, `models/effacement_compte.py`, `models/__init__.py`, `alembic/versions/023a_…`, les trois tests existants. **Justifiés** : RGPD-03 exige l'effacement de compte et de projet, et les tests adaptés suivent un changement de contrat. Tous sont déclarés au §6 du rapport.

Intersection réelle avec les autres branches :
```
$ git diff --name-only origin/claude/vague-c-20260906...HEAD | sort > a.txt
$ for b in claude/vague2-b claude/vague2-c; do git diff --name-only origin/claude/vague-c-20260906...$b | sort > x.txt; comm -12 a.txt x.txt; git ls-tree -r --name-only $b backend/alembic/versions | grep -E "/02[3-9]"; done
== claude/vague2-b c74a817      (aucun fichier commun)
== claude/vague2-c c37e6aa
backend/app/models/__init__.py
backend/alembic/versions/023c_consentement_opus.py   (seconde tête depuis 022)
```
- C : conflit textuel probable en fin de `models/__init__.py` (deux imports ajoutés au même endroit) et deux têtes Alembic.
- B : pas de fichier commun. B modifie `admin_alert_service.py` (A ne fait que l'appeler) et ajoute `sonde_rag.py`, fondé sur `rag_health_check` (interaction sémantique, voir points non vérifiés).

## 6. Ce que j'ai écrit hors du worktree

Journaux, scripts et copies sous `/root/.dh_orch_vague2/` uniquement :
- `testeur-A-*.log` ;
- `testeur-A-prep.sh`, `testeur-A-rouge.sh`, `testeur-A-migration.py` ;
- copies d'export `testeur-A-parent/`, `testeur-A-sonde/`, avec mes deux fichiers de sonde `tests/test_zz_sonde*_testeur_a.py`, jamais commités.

Aucun appel réseau vers un modèle, aucune alerte réelle (`alerter_admin` capturé), aucune commande dans le répertoire de production.
