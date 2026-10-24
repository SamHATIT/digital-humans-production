# Rapport — Vague 2 / File A — RAG et données (AS-06)

**Branche :** `claude/vague2-a` (depuis `origin/claude/vague-c-20260906`, `388299a`) · **Worktree :** `/root/workspace/wt-vague2-a` · **Rédigé le 24/10/2026** par impl-A.
**Mission :** `docs/missions/VAGUE2_A_RAG_DONNEES.md` — SEC-04, PROD-09, RGPD-03.

Conventions : « mesuré » / « exécuté » = commande lancée et sortie constatée, journal cité. « Lu, non exécuté » = lecture de code ou de configuration seulement. Tous les journaux sont sous `/root/.dh_orch_vague2/` (préfixe `impl-A-`).

Embeddings en test : **fonction bouchon déterministe** `tests/vague2_a_outils.py::embedding_bouchon` (empreinte SHA-256 du texte → 8 flottants), substituée à `get_openai_embedding` et `get_nomic_embedding`. Reranker neutralisé. Chroma : `PersistentClient` sur un répertoire `tmp_path`. Aucun appel OpenAI, aucun modèle chargé. Les nouveaux tests construisent leur `TestClient` **sans** `with` (pas de cycle de vie, donc pas de sonde `GET /v1/models` vers 127.0.0.1:18084) ; aucun test ajouté n'envoie de requête vers 18084 ou 18110.

---

## 1. Suite complète avant / après (mesurée)

Commande (depuis `backend/`, venv `./venv`, environnement hermétique) :

```
nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=<id>; ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' > /root/.dh_orch_vague2/<journal> 2>&1 &
```

| Mesure | Commit | Journal | Résultat brut |
|---|---|---|---|
| Avant | `388299a` | `impl-A-avant.log` (`DH_TEST_RUN_ID=impla_avant`) | `31 failed, 1052 passed, 2 skipped, 7 xfailed, 1462 warnings in 727.72s (0:12:07)` |
| Après 1 | `98598b1` | `impl-A-apres.log` (`DH_TEST_RUN_ID=impla_apres`) | `32 failed, 1080 passed, 2 skipped, 7 xfailed, 1617 warnings in 686.89s (0:11:26)` |
| Après 2 (final) | `63f4715` | `impl-A-apres2.log` (`DH_TEST_RUN_ID=impla_apres2`) | `31 failed, 1081 passed, 2 skipped, 7 xfailed, 1619 warnings in 735.14s (0:12:15)` |

Avant : identique à la référence de l'orchestrateur (31 / 1052 / 2 / 7). Répartition des 31 échecs, mesurée (`grep "^FAILED" | sed 's/::.*//' | sort | uniq -c`) : 27 `test_lot_c_injection_commandes.py`, 3 `test_auth.py`, 1 `test_emma_phase3.py`.

Écart avant → après final : **+29 tests passés** (1052 → 1081), soit exactement les 29 tests ajoutés (8 SEC-04 + 13 PROD-09 + 8 RGPD-03) ; **mêmes 31 échecs** qu'avant, liste identique :

```
$ grep "^FAILED" impl-A-avant.log  | sed 's/ - .*//' | sort > impl-A-avant-failed.txt
$ grep "^FAILED" impl-A-apres2.log | sed 's/ - .*//' | sort > impl-A-apres2-failed.txt
$ diff impl-A-avant-failed.txt impl-A-apres2-failed.txt && echo "MEMES 31 ECHECS QU'AVANT"
MEMES 31 ECHECS QU'AVANT
```

« Après 1 » avait un 32ᵉ échec, **introduit par moi** (`8511943`) : `tests/test_lot_c_injection_commandes.py::test_documents_upload_assaini_par_lot_b` (diff des listes : `> FAILED tests/test_lot_c_injection_commandes.py::test_documents_upload_assaini_par_lot_b`). Corrigé par `63f4715`, voir §2 PROD-09.

---

## 2. Constats de la mission

### SEC-04 — le RAG « global » incluait les documents privés — **fait**

**Défaut confirmé, mesuré.** Test rouge sur `388299a` (`impl-A-sec04-rouge.log`, `8 failed`) : le tenant A ingère `cahier_a.txt` par la vraie route `POST /api/projects/{A}/documents` ; puis

```
AssertionError: le document privé de A sort ailleurs que pour A : ['query_collection(technical, project_id=global)', 'query_rag(agent=default, project_id=global)', 'query_rag(agent=pm, project_id=global)', 'query_rag(agent=developer_apex, project_id=global)', 'get_salesforce_context(project_id=global)']
```

Précision mesurée : la recherche **du projet de B** ne sortait pas le fragment de A (le filtre `project_id` fonctionnait) ; la fuite était la recherche **sans projet**. Second défaut confirmé par le même jeu : avec un projet, le corpus public n'était pas rendu (`AssertionError: le corpus public n'est pas rendu pour A`).

**Correctif** (`7375a2d`, `app/services/rag_service.py`, `app/services/rag_visibilite.py`) :
- métadonnée `visibility` = `public` | `private` sur chaque chunk ; `filtre_visibilite(project_id)` : sans projet → `{"visibility": "public"}` ; avec projet → `public` OU (`private` ET ce `project_id`). Le filtre n'est plus jamais `None` ;
- `ingest_document` refuse (`ValueError`) toute ingestion sans `project_id` **et** `document_id` et marque ses chunks `private` (la métadonnée de l'appelant ne peut pas l'écraser) ;
- un chunk sans `visibility` n'est servi à personne ; une collection qui en contient lève `CollectionNonClassee`, traitée par le chemin GL-10 existant (`signaler_rag_indisponible` : alerte admin + exécution `degraded`). Vérification par collection une fois par processus (cache clé = nom + id Chroma), re-vérification au plus toutes les 5 min si non classée ;
- `python -m app.services.rag_visibilite` : classement des chunks existants, **à blanc par défaut** ; privé si `project_id`/`document_id` ou id `proj<P>_doc<D>_<i>` ; **public seulement avec `--public-sans-projet`** (Astra : « backfill prudent »).

**Preuve après correctif :** `impl-A-sec04-vert.log` → `8 passed` ; voisins (a5, gl10, b4, lot_b, b6, a6, lot_e) → `78 passed, 1 xfailed` (`impl-A-sec04-voisins2.log`). Contrôle négatif dans le test principal : la recherche du projet de A rend bien son fragment.

**Mesure en production, lecture seule** (SQLite de Chroma ouvert en `mode=ro&immutable=1`, aucune écriture) :

```
$ sqlite3 "file:/opt/digital-humans/rag/chromadb_data/chroma.sqlite3?mode=ro&immutable=1" "select c.name, count(*) ... group by c.name;"
apex_collection|1645
business_collection|16292
china_collection|25
lwc_collection|6032
operations_collection|27977
technical_collection|39895
$ ... "select key, count(distinct id) from embedding_metadata where key in ('project_id','document_id','visibility','source','chroma:document') group by key;"
chroma:document|91866
source|91866
$ ... "select count(*) from embeddings where embedding_id like 'proj%';"
0
```

Soit 91 866 chunks, **aucun** ne porte `project_id`, `document_id` ni `visibility`, aucun id `proj…`. Conséquence : aucun document client n'a été ingéré dans ce Chroma à ce jour ; et **dès le déploiement de ce correctif, les cinq collections seront « non classées »** → chaque requête RAG lèvera `CollectionNonClassee`, alertera l'exploitant et marquera l'exécution `degraded`, jusqu'au classement (voir §4, décision de Sam).

Tests existants modifiés (assertions qui constataient la fuite) — dit ici platement :
- `tests/test_vague_a_a5_concierge_cloisonnement.py` : `test_controle_negatif_le_rag_global_sort_bien_le_chunk_du_projet_999` et `test_controle_negatif_get_salesforce_context_sans_projet_sort_la_sentinelle` **affirmaient** que la recherche sans projet sortait le chunk du projet 999 (c'était la primitive SEC-04, documentée comme risque). Renommés `…_du_projet_999_sort_bien_son_chunk` / `…_du_projet_999_sort_la_sentinelle` : ils vérifient la sortie pour 999 (rôle de contrôle négatif conservé) et l'absence sans projet. Fixture : chunk marqué `visibility: private`. Docstring du module mise à jour ;
- `tests/test_vague1_c_gl10_rag_degrade.py::test_sans_panne_rien_n_est_signale` : la fausse collection expose `id`, `count()`, `get()` et un chunk `public`.

### PROD-09 — upload non borné avant lecture, collisions, ingestion disproportionnée — **fait** (sauf limite de temps, §3)

**Défauts confirmés, mesurés** sur le code parent avec l'instrument final (`impl-A-prod09-rouge3.log`, `11 failed, 2 passed`) :

```
[MESURE PROD-09 longueur annoncee] corps=25165962 statut=400 octets_lus_par_l_application=25165962 pic_tracemalloc=25932378
[MESURE PROD-09 flux sans longueur] corps=29360266 statut=400 octets_lus_par_l_application=29360266 pic_tracemalloc=29607690
AssertionError: deux documents pointent le même fichier disque
AssertionError: binaire PDF ingéré comme texte : '%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj ...
AssertionError: {"id":1,"filename":"long.txt","file_size":2000001,"collection_name":"technical","chunk_count":2501,"status":"ready"}
AssertionError: upsert de 638 chunks d'un coup
```

Parseur PDF, vérifié par exécution : `fitz` (PyMuPDF), seul parseur essayé, est absent **du venv de production** (`/root/workspace/digital-humans-production/backend/venv/bin/python -c "import fitz"` → `ModuleNotFoundError: No module named 'fitz'` ; ce venv est celui de `ExecStart` dans `systemctl cat digital-humans-backend`) et du venv de test. En production, tout PDF téléversé est donc lu comme texte brut et ingéré. `PyPDF2 3.0.1` est présent dans les deux (`prod PyPDF2 3.0.1`) et déclaré dans `requirements.txt`.

**Instrument de mesure** (dans `tests/test_vague2_a_prod09_upload_borne.py`) : appel ASGI direct ; `octets_lus_par_l_application` compte les octets rendus par `Request.stream()`, seule voie par laquelle FastAPI ou la route lisent le corps ; pic de `tracemalloc` pendant la requête. Écart d'instrument constaté et corrigé en cours de route : un premier compteur au niveau du `receive` brut donnait le corps entier même après correctif — `BaseHTTPMiddleware` (Starlette 0.27, trois middlewares dans `app.main`) appelle `receive` pour écouter la déconnexion pendant qu'il transmet la réponse et vide le reste du corps sans le conserver. Ce compteur est conservé en information (`octets_recus_avant_reponse`) et n'est pas asserté.

**Correctif** (`8511943`, `app/api/routes/documents.py`, `app/services/rag_service.py`) :
- la route ne déclare plus `UploadFile = File(...)` (qui faisait analyser tout le corps avant l'appel) ; elle lit le corps elle-même, après authentification, porte `upload_documents`, propriété du projet, collection et quota : `Content-Length` > 20 Mio + 64 Kio → **413 sans lire un octet** ; sans `Content-Length`, la lecture s'arrête au plafond ; la taille exacte du fichier est revérifiée ; le fichier est copié sur disque par morceaux (jamais chargé entier) ;
- nom disque `uuid4().hex + extension` ; le nom client (dernier segment) reste le nom affiché ;
- PDF par `PyPDF2` ; absent → **503** explicite, ni ligne, ni fichier, ni chunk ; PDF > 500 pages → 422 ; DOCX : `python-docx` absent → 503, archive > 100 Mio décompressés → 422 ;
- extraction **avant** tout enregistrement ; texte > 2 000 000 caractères → 422, aucun embedding ;
- `ingest_document` par lots de 100 (`TAILLE_LOT_INGESTION`) ; un échec au milieu retire les lots déjà écrits (le document passe `error`) ;
- quota par projet : 50 documents, 200 Mio ;
- contrat frontend inchangé : `multipart/form-data`, champ `file`, `?collection_name=` (lu dans `frontend/src/services/api.ts:566-595`, non exécuté) ; les messages d'erreur sont des chaînes dans `detail`.

**Preuve après correctif** (`impl-A-prod09-vert3.log`, avec les voisins sec04, lot_b, bill05, b4, a5, gl10 : `72 passed, 1 xfailed`) :

```
[MESURE PROD-09 longueur annoncee] corps=25165962 statut=413 octets_lus_par_l_application=0 pic_tracemalloc=708529
[MESURE PROD-09 flux sans longueur] corps=29360266 statut=413 octets_lus_par_l_application=21037170 pic_tracemalloc=1392535
```

Contrôles négatifs : un petit fichier passe (`200`, `ready`, chunks présents) ; un vrai PDF est lu par PyPDF2 (le texte `SENTINELLE PDF PROD09` est dans le chunk, `%PDF`/`endobj` n'y sont pas). Deux tests ne discriminent pas (verts aussi sur le parent, attendu) : `test_controle_negatif_un_petit_fichier_passe` et `test_ingestion_en_echec_au_milieu_ne_laisse_aucun_chunk` (avant correctif, l'unique `upsert` final n'était jamais atteint ; le test protège le comportement introduit par les lots).

Tests existants modifiés :
- `tests/test_lot_b_cloisonnement.py::test_documents_nom_de_fichier_traversant` attendait `evasion.txt` comme **nom disque** ; il vérifie maintenant un seul fichier dans le répertoire du projet, nom généré sans `..`, et `filename == "evasion.txt"` dans la réponse ;
- `tests/test_lot_c_injection_commandes.py::test_documents_upload_assaini_par_lot_b` — **défaut que j'ai introduit** avec `8511943` et que je n'avais pas vu : ce garde textuel exigeait la ligne `file_path = project_dir / safe_filename`. La première suite complète « après » (`impl-A-apres.log`) l'a trouvé : `32 failed` dont ce test, nouveau. Corrigé par `63f4715` : le garde exige désormais l'absence de tout nom disque dérivé du nom client et la présence du nom généré (`impl-A-lotc.log` : `1 passed`).

### RGPD-03 — un effacement partiel devenait définitif — **fait** (périmètre ci-dessous ; Stripe et tâches en cours : §3)

**Défauts confirmés, mesurés** (`impl-A-rgpd03-rouge2.log`, `8 failed`) :

```
AssertionError: effacement déclaré réussi malgré la panne Chroma : {'statut': 'compte supprimé', ... }
AssertionError: RuntimeError('base indisponible (panne injectee)')   (exception brute, compte actif, aucune trace)
AssertionError: {"statut":"compte supprimé", ...}  assert 200 == 503
Failed: DID NOT RAISE <class 'Exception'>          (delete_project_document_chunks rend 0 sur erreur)
AssertionError: {"deleted":true,"filename":"doc0.txt","chunks_removed":0}  assert 200 == 502
AssertionError: chunks orphelins après suppression du projet  assert ['proj1_doc1_...proj1_doc2_1'] == []
```

**Correctif** (`98598b1`) :
- table `effacements_comptes` (modèle `app/models/effacement_compte.py`, migration **`023a_rgpd03_effacements_comptes`**, `down_revision = 022_sec12_chat_logs_reclamation`) : périmètre (projets, exécutions, documents + collection, fichiers), étapes, erreurs, tentatives, statut `en_cours` / `partiel` / `termine` ;
- `AccountService.supprimer` : (0) compte désactivé **et** périmètre enregistrés dans une transaction ; (1) purge Chroma (par document, puis par projet dans les cinq collections) puis fichiers — tous les éléments sont tentés, tout échec lève `EchecPurgeHorsBase` ; (2) base + passage à `termine` dans **une** transaction ; le périmètre est alors réduit à des compteurs. Échec : `partiel`, erreur datée, alerte admin, `EffacementIncomplet`, **aucune ligne SQL détruite** ;
- reprise : `AccountService.reprendre(id)`, `reprendre_effacements_en_attente(db)`, `python -m app.services.account_service --reprendre` ; étapes idempotentes ;
- `DELETE /api/account` : 503 si incomplet ; le titulaire d'un compte bloqué **par son propre effacement en attente** peut relancer (sinon 403) ;
- `rag_service.delete_project_document_chunks` propage les erreurs ; seule une collection **inexistante** compte 0 (WARNING) ; nouveau `delete_project_chunks(project_id)` ;
- `DELETE /projects/{p}/documents/{d}` : purge toujours tentée (même document `error`), 502 et document conservé si elle échoue ;
- `DELETE /pm-orchestrator/projects/{p}` : purge Chroma + fichiers d'abord, 502 et projet conservé si elle échoue.

**Preuve après correctif** (`impl-A-rgpd03-vert2.log` : rgpd03 + b4 + prod09 + sec04 + lot_b → `49 passed, 1 xfailed`). Le test principal injecte une panne Chroma sur le 2ᵉ document d'Alice : exception `EffacementIncomplet` ; compte inactif, non anonymisé ; 2 lignes `project_documents` toujours là ; seuls les chunks du document en panne restent ; tâche `partiel` avec l'erreur ; alerte émise ; Bob intact. Reprise : zéro chunk, fichiers (documents + snapshot SDS sous `OUTPUT_DIR/projects/<id>/`) effacés, projet supprimé, compte anonymisé, tâche `termine`, chemins absents du périmètre. Rejouer `reprendre` puis `supprimer` : aucune exception, une seule tâche, Bob intact. Second test : panne injectée dans l'étape base → rollback complet (projet présent), compte inactif, `partiel`, puis `reprendre_effacements_en_attente` → `[id]`, puis `[]`.

**Migration vérifiée** (`impl-A-migration-023a.log`, script `impl-A-patches/verif_migration_023a.py`, base jetable `digital_humans_test_impla_mig023a` dérivée du gabarit de test, détruite à la fin) : `stamp 022` → `upgrade head` (table créée, 10 colonnes) → `downgrade 022` (table absente) → `upgrade head` (recréée), tous `rc=0`. `alembic heads` sur la branche : `023a_rgpd03_effacements_comptes (head)`.

Appelants (lu, non exécuté) : aucun appel à `DELETE /api/account` trouvé dans `frontend/src` (`grep -rn "api/account" frontend/src --include=*.ts*` et `grep -rn "'/account\|\"/account\|/account'" frontend/src` → aucune ligne) ; le 503 n'a pas de consommateur d'interface aujourd'hui.

**Infirmé :** « les snapshots sont écrits dans `<repo>/outputs` alors que la racine de l'effacement est `<repo>/backend/outputs` ». Lu : `app/api/routes/sds_versions.py:33-38` écrit sous `settings.OUTPUT_DIR` depuis SEC-06 (`4b08a2a`, vague 0), et `OUTPUT_DIR` est une racine de `_racines_de_fichiers()`. Exécuté : le test principal crée un snapshot sous `settings.OUTPUT_DIR/projects/<id>/` référencé par `SDSVersion` et constate son effacement.

---

## 3. Reste ouvert / pas fait

### Reste ouvert (reliquat, non traité faute de temps ou hors périmètre mesurable ici)
- **Coût de la vérification de classement à l'échelle de la production** (`_verifier_classement`) : un `count()` + un `get(where=visibility ∈ {public, private}, include=[])` par collection, une fois par processus. Mesuré seulement sur des collections de test ; sur `technical_collection` (39 895 chunks) le coût n'est **pas mesuré** (je suppose de l'ordre de la seconde, sans preuve).
- Ordre dans `query_collection` : la vérification de classement est faite **après** le calcul de l'embedding de la requête (pour que la cause d'une panne d'embedding — 429 — reste celle rapportée, test GL-10 existant). Conséquence : tant que le corpus n'est pas classé, chaque requête paie encore un embedding OpenAI avant d'être refusée.
- **Ingestions externes au dépôt** : le corpus public est ingéré par des scripts de `/opt/digital-humans/rag/` (`ingest_all_docs.py`, `complete_ingestion.py`, … — listés, non lus). Ils ne posent pas `visibility`. Toute ingestion future par ces scripts créerait des chunks non classés → collection signalée en panne (bruyant, pas silencieux). À adapter (`visibility: "public"`) hors de ce dépôt.
- `china_collection` (25 chunks) existe dans le Chroma de production mais pas dans `rag_service.COLLECTIONS` : jamais interrogée, non classée par l'outil.
- **Limite de temps** d'extraction/ingestion (Astra PROD-09) : non faite. L'ingestion reste synchrone dans la requête, un appel d'embedding par chunk (jusqu'à ~2 500 pour un texte à la borne). L'API OpenAI accepte des lots d'entrées ; ne pas l'avoir branché est un choix de périmètre (toucher `get_openai_embedding`, fonction aussi utilisée par les requêtes).
- Un PDF à flux compressés peut produire beaucoup de texte sur une page avant que la borne de caractères ne coupe (`extract_text` page par page) ; borné par 500 pages et 2 M caractères cumulés, pas par page.
- **Deux `DELETE /api/account` simultanés** pourraient ouvrir deux tâches d'effacement (pas de verrou sur la ligne `users`). Non traité.
- Nettoyage rétroactif de chunks orphelins de projets supprimés avant ce correctif : pas d'outil. Mesure de production ci-dessus : **0** chunk porteur de `project_id` → aucun orphelin aujourd'hui.
- Fichiers temporaires SDS et journaux d'agents (Astra RGPD-03) : non couverts par l'effacement.
- Cohérence des plafonds d'upload, **lu, non exécuté** : `client_max_body_size 10M` dans `/etc/nginx/sites-enabled/app.digital-humans.fr:42` ; `settings.MAX_FILE_SIZE = 10485760` (`app/config.py:48`, aucun lecteur — `grep -rn MAX_FILE_SIZE app` ne trouve que `config.py` et `documents.py`) ; `documents.MAX_FILE_SIZE = 20 Mio`. Par le domaine public, nginx refuse donc au-delà de 10 Mo avant l'application. Le backend écoute sur `0.0.0.0:8002` (`ExecStart`) : si ce port est joignable de l'extérieur, la borne nginx se contourne — **non vérifié** (pare-feu non consulté).

### Pas fait, et pourquoi (choix)
- **Résiliation de l'abonnement Stripe et instructions aux sous-traitants** à l'effacement (Astra RGPD-03) : demande des appels Stripe réels et une règle métier (résiliation immédiate ou fin de période, remboursement) → §4.
- **Suspension des tâches en cours** à l'effacement : la désactivation du compte bloque toute nouvelle requête authentifiée, mais une exécution déjà enfilée dans le worker ARQ continue. L'annuler touche `workers/*` (file B) ; non fait.
- Aucun `skip`/`xfail` ajouté. Aucun échec préexistant corrigé ni masqué.

## 4. Attend une décision de Sam
1. **Classement du corpus de production avant (ou au moment du) déploiement.** Les 91 866 chunks n'ont aucune trace de projet. Commande à blanc d'abord, puis, si Sam confirme que ce corpus est entièrement de la documentation publique : `python -m app.services.rag_visibilite --appliquer --public-sans-projet` (sur le Chroma de `settings.CHROMA_PATH`, donc la production). **Sans ce classement, le RAG est indisponible (alerte + `degraded`) pour toutes les exécutions dès le déploiement.** Je ne l'ai pas lancé : c'est une écriture en production.
2. **Effet sur les agents** : avec un projet, `get_salesforce_context` rendait jusqu'ici **uniquement** les documents du projet (donc rien du corpus expert pour un projet sans document) ; il rend désormais corpus public + documents du projet (correctif prescrit par Astra). Plus de contexte dans les prompts des agents (coût, comportement) — à valider.
3. **Valeurs des bornes** (nommées dans `documents.py`, choisies par moi) : texte extrait 2 000 000 caractères, 500 pages PDF, 100 Mio décompressés pour un DOCX, quota 50 documents / 200 Mio par projet ; et **un plafond unique** d'upload entre nginx (10 Mo), `config.MAX_FILE_SIZE` (10 Mo, inutilisé) et la route (20 Mo).
4. **Stripe à l'effacement** : résilier l'abonnement à l'effacement du compte ? immédiatement ou en fin de période ? (non implémenté).

## 5. Commits

```
63f4715 test(PROD-09) : le garde textuel SEC-03 de lot_c exige desormais un nom disque genere
98598b1 fix(RGPD-03) : effacement de compte complet ou rejouable, jamais partiel et definitif
8511943 fix(PROD-09) : upload borne avant lecture du corps, nom disque genere, parseur absent refuse, ingestion bornee par lots
7375a2d fix(SEC-04) : le RAG global ne rend plus les documents prives, visibilite explicite par chunk
```
(+ le commit de ce rapport, `git log --oneline origin/claude/vague-c-20260906..HEAD` le montre en tête.)

## 6. Fichiers touchés hors des zones propres, et fichiers en recouvrement

Zones de la file A : `services/rag*`, `api/routes/documents*`. Fichiers créés : `app/services/rag_visibilite.py`, `app/models/effacement_compte.py`, `alembic/versions/023a_rgpd03_effacements_comptes.py`, `tests/vague2_a_outils.py`, `tests/test_vague2_a_{sec04_rag_cloisonnement,prod09_upload_borne,rgpd03_effacement_rejouable}.py`.

| Fichier | Liste de recouvrement | Ce que j'y ai changé |
|---|---|---|
| `app/services/rag_service.py` | oui (A propriétaire ; B OPS-01/GL-25) | `filtre_visibilite`, `CollectionNonClassee`, `_verifier_classement` appelée dans `query_collection` **après** le calcul d'embedding ; `ingest_document` (refus sans projet/document, `visibility`, lots de 100 via `_ingerer_lot`) ; `delete_project_document_chunks` propage les erreurs ; `_collection_si_existe`, `delete_project_chunks`. **`rag_health_check`, le cache de santé et `get_openai_embedding` non touchés.** |
| `app/models/__init__.py` | oui | 2 lignes ajoutées **en fin de fichier** (import `EffacementCompte`). |
| `alembic/versions/` | oui | `023a_rgpd03_effacements_comptes.py`, tête `022_sec12_chat_logs_reclamation`. **Si C ajoute `023c_…` depuis la même tête : deux têtes à la fusion → révision de fusion nécessaire.** |
| `app/services/account_service.py` | non (zone de personne) | `supprimer` réécrit autour de la tâche durable ; `_purger_chroma`/`_purger_fichiers` refondues, `_chemins_de_fichiers` extraite ; ajout `reprendre`, `purger_hors_base_projet`, `EffacementIncomplet`, `EchecPurgeHorsBase`, `reprendre_effacements_en_attente`, `main`. Les étapes SQL 2 à 8 sont reprises telles quelles dans `_effacer_en_base`. Réécriture large, pas de reformatage du reste. |
| `app/api/routes/account.py` | non | dépendance `titulaire_pour_effacement` ; `DELETE /api/account` → 503 sur `EffacementIncomplet`. |
| `app/api/routes/orchestrator/project_routes.py` | non | `import logging` + `logger` ; `delete_project` : purge hors base d'abord, 502 sinon. |
| `tests/test_vague_a_a5_concierge_cloisonnement.py`, `tests/test_vague1_c_gl10_rag_degrade.py`, `tests/test_lot_b_cloisonnement.py` | non | assertions existantes modifiées, détaillées au §2. |
| `app/services/admin_alert_service.py` | oui | **non modifié** (appelé seulement, via l'attribut du module). |
| `app/main.py`, `app/config.py`, `requirements.txt` | oui (B) | **non modifiés** : la borne d'upload est dans la route, pas en middleware ; PyPDF2 est déjà déclaré. |
| `tests/conftest.py` | oui | **non modifié** (fixtures dans mes fichiers de test et `tests/vague2_a_outils.py`). |

### Diffs proposés hors de ma file (non commités)

**Pour B — `app/config.py`** : `MAX_FILE_SIZE` (10 Mo) n'a aucun lecteur et contredit la route (20 Mo). Une fois la valeur décidée par Sam (§4.3), soit le supprimer, soit en faire la source unique :

```diff
--- a/backend/app/config.py
+++ b/backend/app/config.py
@@
-    MAX_FILE_SIZE: int = 10485760  # 10MB
+    # PROD-09 (vague 2 / file A) : plafond d'upload des documents projet, lu
+    # par app/api/routes/documents.py. A aligner sur client_max_body_size (nginx).
+    MAX_FILE_SIZE: int = 20 * 1024 * 1024
```
et, côté A, `MAX_FILE_SIZE = settings.MAX_FILE_SIZE` dans `documents.py` (je ne l'ai pas fait pour ne pas dépendre d'un fichier de B).

**Pour B — sonde RAG (OPS-01)** : `rag_health_check` compte les chunks mais ignore leur classement ; une collection entièrement non classée paraît « OK » au démarrage alors que toute requête sera refusée. Proposition : exposer dans la sonde le nombre de chunks sans `visibility` (même requête que `rag_service._verifier_classement`).

## 7. Écarts aux règles et points gris, dits platement
- Pour mesurer le rouge sur le code parent avec les tests finaux, j'ai fait deux fois `git checkout HEAD -- <fichiers>` **dans mon worktree**, puis restauré mes versions depuis des copies (`/root/.dh_orch_vague2/impl-A-patches/sauvegarde-*`). Aucune commande git hors de mon worktree.
- Lectures hors worktree, sans écriture : SQLite du Chroma de production en `mode=ro&immutable=1` (comptages de métadonnées, aucun contenu de chunk lu) ; `python -c "import fitz"` et `import PyPDF2, docx` **exécutés avec l'interpréteur du venv de production** (aucun fichier écrit, aucun service touché) ; `systemctl cat digital-humans-backend` ; configuration nginx (`grep`).
- Vérification de migration : base jetable créée et détruite avec le rôle du gabarit de test (`/root/.dh_test_db.env`, sourcé, non affiché). Le processus parent du script a importé `app.config` sans `DH_ENV_FILE` ; il n'existe pas de `backend/.env` dans le worktree (`ls` → absent), `DATABASE_URL` pointait la base jetable.
- Scripts d'édition et copies de sauvegarde écrits sous `/root/.dh_orch_vague2/impl-A-patches/` (au-delà des seuls journaux).
- `documents.py` et `account_service.py` : blocs entiers réécrits (fonctions extraites). Inévitable pour ces correctifs, mais ce sont de futurs conflits si une autre file y touche.
- Messages de commit sans accents (ASCII), en français.
