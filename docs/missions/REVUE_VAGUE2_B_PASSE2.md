# Revue indépendante, passe 2 — Vague 2 / File B — Exploitation, sondes, dépendances

**Testeur :** testeur-B2 (Claude Code). Je n'ai pas vu le travail se faire. Worktree `/root/workspace/wt-vague2-b`, branche `claude/vague2-b`, HEAD revu **`ffc2501ba9c0e281eb41033f2712a3352add3425`**.
**Date :** 24/10/2026. Je n'ai rien corrigé. Aucun `git checkout` dans le worktree : chaque scénario est une copie `git archive HEAD` sous `/root/.dh_orch_vague2/testeur-B2-<scenario>/`, où seuls les fichiers de code sont remis à `X^` par `git show X^:<f> > <f>` ; les tests restent ceux de HEAD ; venv du worktree (`/root/workspace/wt-vague2-b/backend/venv`) partout.
Conventions : « vérifié » = exécuté par moi, sortie constatée ; « lu » = lu, non exécuté. Journaux : `/root/.dh_orch_vague2/testeur-B2-*`, scripts : `/root/.dh_orch_vague2/testeur-B2-scripts/`.

---

## Verdict : **CONFORME**

Les 7 reprises de la revue 1 sont corrigées. Pour les reprises 2, 3, 4 et 5, le test ajouté est **rouge à `X^`** et vert à HEAD, pour la raison du constat. Les reprises 1 et 6 ne portent pas de comportement : aucun rouge n'est possible ; j'ai fait un contrôle négatif pour la 1. Pour la 7, le vrai mot de passe du rôle de test ne figure dans **aucun** fichier de `/root/.dh_orch_vague2/` (vérifié). Le grep demandé trouve pourtant des fichiers : ce sont des gabarits (`<…>`) et des valeurs d'exemple, voir §2.7.
La suite complète est identique à la référence pour les échecs : mêmes 31. Elle compte +108 passés, soit exactement les 108 tests `test_vague2_b_*`. Aucun xfail n'a été ajouté. Il y a 5 skips conditionnels, désormais déclarés au rapport.
Il reste 6 défauts **mineurs** (§4), consignés comme ouverts. Aucun ne contredit une reprise.

---

## 1. Suite backend complète à HEAD (venv du worktree)

Commande, depuis `/root/workspace/wt-vague2-b/backend` :
```
nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurb2_head; /root/workspace/wt-vague2-b/backend/venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' > /root/.dh_orch_vague2/testeur-B2-suite-head.log 2>&1 &
```
Sortie brute (`testeur-B2-suite-head.log`) :
```
31 failed, 1160 passed, 2 skipped, 7 xfailed, 979 warnings in 517.66s (0:08:37)
PYTEST_EXIT=1
```
Référence de l'orchestrateur (`reference_tests.log`, `388299a`) : `31 failed, 1052 passed, 2 skipped, 7 xfailed`.
```
$ grep -E "^FAILED" <journal> | sed -E 's/ - .*//' | sort   (pour les deux journaux)
$ diff testeur-B2-reference-failed.txt testeur-B2-suite-head-failed.txt && echo IDENTIQUES
IDENTIQUES
      3 FAILED tests/test_auth.py
      1 FAILED tests/test_emma_phase3.py
     27 FAILED tests/test_lot_c_injection_commandes.py
```
- **Même liste d'échecs.** Il y a **+108 passés**. Collecte (`testeur-B2-collecte.log`) : `gl25 30, ops01 13, ops02 8, ops08 17, sec17 27, sec18 13` → `108 tests collected`. Les 89 tests initiaux et les 19 des reprises font exactement 108 (13 GL-25, 4 SEC-17, 1 SEC-18, 1 OPS-08), conformément au rapport §9.
- **Skips et xfail.** `2 skipped` et `7 xfailed` des deux côtés. Les skips ajoutés au diff sont les 4 `skipif(os.geteuid() != 0)` et 1 `pytest.skip` conditionnel :
  ```
  $ git diff origin/claude/vague-c-20260906...HEAD -- backend/tests | grep -nE "^\+.*(skip|xfail)"
  1560/1573/1582/1591:+@pytest.mark.skipif(os.geteuid() != 0, reason="le script exige root (il le verifie)")
  1656:+        pytest.skip("hors du VPS de reference : les tests de rotation y sont ignores (non root)")
  ```
  Aucun ne se déclenche sur le VPS. Ma passe ciblée en `-rs` (`testeur-B2-vert-head.log`) donne `112 passed`, sans aucune ligne `SKIPPED`.
- Requêtes vers le tunnel Spark pendant la suite : `grep -c 18084` donne **59** à HEAD et **59** dans la référence. C'est la sonde de démarrage préexistante, aucune génération.

## 2. Reprises, une par une

Script commun : `testeur-B2-scripts/scenario.sh <nom> <X|HEAD> "<fichiers à remettre à X^>" "<tests>"`. Il archive HEAD, remet les fichiers à `X^`, puis lance pytest dans la copie, sur une base de test propre à l'exécution.

### Reprise 1 — « aucun skip ajouté » faux → **corrigée**
- Rapport §7 (lu) : la phrase dit maintenant les 4 `skipif`, pourquoi, et qu'ils tournent en root sur le VPS. Elle dit aussi que le test de garde est ignoré hors VPS. Exact d'après le diff ci-dessus.
- Test `test_les_tests_de_rotation_tournent_sur_le_vps` (lu). Il fait `assert os.geteuid() == 0` quand `/root/workspace/digital-humans-production` existe. Cette assertion porte exactement la condition des 4 `skipif` : elle prouve donc qu'ils ne sont pas ignorés ici.
- Rouge à `X^` : **sans objet**. Le commit ne change aucun code. **Contrôle négatif à moi** (`testeur-B2-r1-negatif.log`), `os.geteuid` forcé à 1000 :
  ```
  [testeurB2] garde non-root -> sur le VPS, les tests de rotation seraient ignores
  [testeurB2] tests a skipif: 4 conditions: [False]
  2 passed
  ```
  La garde échoue bien si la suite tournait sans root. Les 4 marques sont évaluées à `False` ici.
- Vert à HEAD : oui (17 tests OPS-08 dans `testeur-B2-vert-head.log`, aucun skip).

### Reprise 2 — alerte refusée jamais retentée → **corrigée**
- Tests `test_panne_refusee_par_telegram_est_retentee` et `test_retour_refuse_par_telegram_est_retente` (lus). Ils comptent les tentatives d'envoi sous une horloge simulée. La première alerte est refusée (`ok:false`). Il n'y a pas de nouvel essai immédiat, puis un nouvel essai après 61 s, puis plus aucun doublon une fois l'envoi accepté. Même schéma pour le retour. Les assertions prouvent la reprise.
- **Rouge à `bcca12c^`** (`testeur-B2-r23-rouge.log`, `7 failed, 23 passed`) :
  ```
  E       AssertionError: l'alerte refusee n'a jamais ete retentee
  E       assert 1 == 2
  E       AssertionError: le retour refuse n'a jamais ete retente
  E       assert 2 == 3
  ```
- **Vérification à moi, trois formes de refus** (`testeur-B2-scripts/test_testeurb2_r2.py`). Les trois formes sont `ok:false`, `HTTPError 500` et `URLError` réseau, pour la panne puis pour le retour. Tentatives cumulées :
  ```
  HEAD (testeur-B2-r2-head.log)          bcca12c^ (testeur-B2-r2-rouge.log)
  ok_false [1, 1, 2, 3, 3, 4, 4, 5, 6, 6]  ok_false [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
  http500  [1, 1, 2, 3, 3, 4, 4, 5, 6, 6]  http500  [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
  reseau   [1, 1, 2, 3, 3, 4, 4, 5, 6, 6]  reseau   [1, 1, 1, 1, 1, 2, 2, 2, 2, 2]
  3 passed                                 3 failed
  ```
  Le refus est retenté (au plus une fois par 60 s), puis plus rien après l'acceptation. Le retour refusé est retenté au succès suivant.
- **Telegram non configuré : est-ce dit ?** Oui, c'est journalisé, pas silencieux. Scénario à moi, jeton et destinataire retirés (`testeur-B2-e2e.log`) :
  ```
  [testeurB2] telegram_configure() = False
  [testeurB2] ERROR app.services.admin_alert_service: [ALERTE ADMIN] Fournisseur LLM gpu_nemotron : injoignable — Constate par testeurB2.
  [testeurB2] ERROR app.services.admin_alert_service: [ALERTE ADMIN] Telegram non configuré (TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID) ou envoi refusé par Telegram : cette alerte n'existe que dans le journal et le tableau de bord.
  [testeurB2] ERROR ... Fournisseur LLM gpu_nemotron : rétabli — ...
  [testeurB2] ERROR ... Telegram non configuré ... ou envoi refusé par Telegram ...
  ```
  Chaque alerte est écrite en ERROR avec la mention que Telegram n'est pas parti. Dans ce cas, `_alerter` tient la panne pour alertée : il n'y a rien à retenter, et le test `test_telegram_non_configure_pas_de_rafale` le confirme. Réserve mineure : le libellé ne distingue pas « non configuré » de « refusé », alors que `telegram_configure()` le permet désormais, et rien n'est dit au démarrage (§4.4).
- Vert à HEAD : oui (`testeur-B2-vert-head.log`).

### Reprise 3 — classement sur chaînes fabriquées ; Spark figé sans alerte ; fournisseur « inconnu » → **corrigée**
- Tests (lus) :
  - `test_vraie_panne_de_transport_locale_classee_injoignable[port_ferme|serveur_muet|connexion_coupee]` passe par le **vrai** `_call_gpu_local`, contre des serveurs en boucle locale.
  - `test_exceptions_httpx_…` utilise de vraies classes httpx.
  - `test_spark_fige_derriere_un_tunnel_ouvert_alerte_par_le_chemin_d_appel` va de bout en bout, du studio au serveur muet.
  - `test_exception_hors_fournisseur_n_annonce_pas_une_panne_llm` couvre la branche `except`.
  - Contrôle : `test_erreur_vide_d_un_fournisseur_cloud_n_est_pas_une_panne`.

  Les assertions portent sur la cause classée et sur le texte de l'alerte : elles prouvent la reprise.
- **Rouge à `bcca12c^`** (`testeur-B2-r23-rouge.log`) :
  ```
  FAILED ...test_vraie_panne_de_transport_locale_classee_injoignable[serveur_muet]   assert None == 'injoignable'  (error='')
  FAILED ...test_exceptions_httpx_d_un_fournisseur_local_classees_injoignable[exc1|exc2]  None = _classer('', 'gpu_nemotron')
  FAILED ...test_spark_fige_derriere_un_tunnel_ouvert_alerte_par_le_chemin_d_appel  assert 0 == 1
  FAILED ...test_exception_hors_fournisseur_n_annonce_pas_une_panne_llm  ['Fournisseur LLM inconnu : injoignable ...']
  ```
- **Scénario de bout en bout à moi** (`testeur-B2-scripts/test_testeurb2_e2e.py`, `testeur-B2-e2e.log`). Le serveur HTTP local écoute sur `127.0.0.1:<port libre>`, ici 36139 et 40741 ; le test vérifie `port not in (18084, 18110)`. Telegram est bouchonné. Studio → routeur → vrai `_call_gpu_local`, palier Free :
  ```
  [testeurB2] appel 1 (muet): 503 {'detail': 'Le service est momentanément indisponible. Notre équipe a été prévenue ; merci de réessayer dans quelques minutes.'}
  [testeurB2] appel 2 (muet): 503
  [testeurB2] envois apres 2 appels muets: ['Fournisseur LLM gpu_nemotron : injoignable']
  [testeurB2] requetes recues par le serveur muet: 2
  [testeurB2] appel 3 (repond): 200 Bonjour du faux Spark
  [testeurB2] envois apres retour: ['Fournisseur LLM gpu_nemotron : injoignable', 'Fournisseur LLM gpu_nemotron : rétabli']
  [testeurB2] repli vers un autre fournisseur ? lignes 'anthropic' au journal : 0
  ```
  Résultat : une alerte à la panne, aucun doublon, une alerte au retour, un 503 explicite, aucun repli.
- **Fournisseur cloud.**
  - Vrai client `AsyncAnthropic` dirigé vers le serveur muet local (`max_retries=0`, délai 0,5 s) : `503`, journal `[Studio chat] anthropic/claude-sonnet en echec : Request timed out or interrupted…`, alerte `Fournisseur LLM anthropic : injoignable`. La vraie erreur est classée.
  - **Erreur vide forgée** : `503` explicite, `envois: [] etat: {}`, journal `ERROR app.api.routes.studio_chat: [Studio chat] anthropic/claude-sonnet en echec : reponse vide`. Elle n'est **pas classée** (aucune alerte, aucun état de panne). Elle n'est **pas masquée** : le client reçoit un refus explicite et le journal une ligne ERROR. Le libellé « reponse vide » est cependant inexact, et ce libellé est préexistant (§4.2).
- Observation : le cas `connexion_coupee` est **non déterministe**. Sur 20 essais réels à HEAD (`testeur-B2-r3-coupee.log`) :
  ```
  connexion coupee x5:  error=''  -> HEAD(local)=injoignable ; sans fournisseur=None
  connexion coupee x15: error='Server disconnected without sending a response.' -> injoignable ; injoignable
  ```
  À HEAD, il est vert dans les deux cas. À `bcca12c^`, il n'est rouge qu'une fois sur quatre environ : l'implémenteur l'a vu rouge (`8 failed`), moi vert (`7 failed`). Le rapport §9 (« connexion coupée → `error=''` ») ne décrit donc qu'un des deux cas (§4.5).
- Vert à HEAD : oui.

### Reprise 4 — fragment de `SECRET_KEY` au journal en cas de refus SEC-17 → **corrigée**
- Test `test_refus_de_demarrage_ne_divulgue_aucun_fragment` (lu). Il compte les fragments de 8 caractères des valeurs factices dans `str(exc)` et n'imprime que le nombre : l'assertion prouve la reprise.
- **Rouge à `d2146a4^`** (`testeur-B2-r47-rouge.log`, `3 failed, 24 passed`) :
  ```
  E       AssertionError: 5 fragment(s) de valeur dans le message d'erreur
  E       AssertionError: 15 fragment(s) de valeur dans le message d'erreur
  E       AssertionError: 15 fragment(s) de valeur dans le message d'erreur
  ```
  Le cas « clé courte » du test est vert des deux côtés : il ne discrimine pas. Le message de commit le dit. Ma vérification ci-dessous couvre ce cas.
- **Vérification à moi, chaque cas de refus, au démarrage réel** (`testeur-B2-scripts/r4_refus.py`). `import app.config` est lancé dans un sous-processus avec des variables d'environnement factices. La sortie analysée est la sortie d'erreur complète (traceback), c'est-à-dire ce qu'écrirait systemd. On y compte les fragments de **6** caractères de toutes les valeurs factices : `SECRET_KEY`, clé Fernet, mot de passe de `DATABASE_URL`, `OPENAI_API_KEY`, `SF_INSTANCE_URL`. Copie HEAD (`testeur-B2-r4-head.log`) :
  ```
  controle_valide      code=0 input_value=False fragments_6car_trouves=0 | DEMARRAGE_OK
  jwt_gabarit          code=1 input_value=False fragments_6car_trouves=1   (fragment = 'secret', voir ci-dessous)
  jwt_courte           code=1 input_value=False fragments_6car_trouves=0 | Value error, SECRET_KEY trop courte (16 caracteres, 32 minimum hors DEBUG) ...
  jwt_absente_prod     code=1 input_value=False fragments_6car_trouves=0 | Value error, SECRET_KEY is required in production mode (DEBUG=False) ...
  fernet_mal_formee    code=1 input_value=False fragments_6car_trouves=0 | ... CREDENTIALS_ENCRYPTION_KEY n'est pas une cle Fernet valide ...
  fernet_absente_prod  code=1 input_value=False fragments_6car_trouves=0 | ... CREDENTIALS_ENCRYPTION_KEY is required ...
  cors_etoile_json     code=1 input_value=False fragments_6car_trouves=0 | Value error, BACKEND_CORS_ORIGINS contient "*" hors DEBUG : refuse ...
  cors_etoile_brut     code=1 input_value=False fragments_6car_trouves=0 | ... SettingsError: error parsing value for field "BACKEND_CORS_ORIGINS" ...
  cors_virgules        code=1 input_value=False fragments_6car_trouves=0 | ... SettingsError ...
  debug_invalide       code=1 input_value=False fragments_6car_trouves=0 | DEBUG  Input should be a valid boolean ...
  entier_invalide      code=1 input_value=False fragments_6car_trouves=0 | ACCESS_TOKEN_EXPIRE_MINUTES  Input should be a valid integ...
  ```
  Le seul fragment trouvé, dans `jwt_gabarit` (`TB2_DEBUG_FRAG=1` → `fragments: ['secret']`), est le mot `secrets` de la consigne « Generer : python -c "import secrets; …" ». Ce n'est pas un fragment de valeur. Même script sur la copie à `d2146a4^` (`testeur-B2-r4-rouge.log`) : `input_value=True` et **17 à 24 fragments** dans chaque refus de validateur, 21 pour l'entier invalide. **Corrigé pour chaque cas de refus.**
- Vert à HEAD : oui.

### Reprise 5 — `chemins_montes` ignorait les websockets → **corrigée**
- Test `test_chemins_montes_voit_les_websockets` (lu). Il vérifie la vraie route `/api/pm-orchestrator/ws/{execution_id}` et une websocket incluse sur deux niveaux de préfixe.
- **Rouge à `868740b^`** (`tests/routes_montees.py` remis) (`testeur-B2-r5-rouge.log`, `1 failed, 33 passed`) :
  ```
  E       AssertionError: assert '/api/pm-orchestrator/ws/{execution_id}' in {'', '/', '/api/account', ...}
  ```
- Comparaison avec la liste plate FastAPI 0.104 de la revue 1 (`testeur-B-routes-parentvenv.json`) (`testeur-B2-r5-routes.log`) :
  ```
  [tb2] chemins_montes(HEAD): 148 | liste plate fastapi 0.104 (revue 1): 147
  [tb2] seulement plat: []
  [tb2] seulement deplie: ['']
  ```
  Plus rien ne manque. `''` est un chemin parasite sans effet sur les tests « démonté » (§4.6).
- Vert à HEAD : oui (34 passés avec les trois fichiers utilisateurs).

### Reprise 6 — contrôle A6 trompeur, fixture morte → **corrigée**
- Lu : la docstring du module et celle de `test_controle_negatif_le_comptage_synchrone_bloque_bien_la_boucle` disent que le contrôle est vrai pour un faux qui relâche le GIL, mais faux pour chromadb. Elles renvoient vers deux tests qui **existent** :
  ```
  tests/test_vague2_b_ops01_sonde_rag.py:138:def test_controle_un_appel_qui_tient_le_gil_bloque_la_boucle_meme_en_to_thread():
  tests/test_vague2_b_ops01_sonde_rag.py:164:def test_le_demarrage_ne_compte_pas_chroma_dans_le_processus(...)
  ```
  La fixture `chroma_lent` et `_attendre_tache_rag` sont retirées de ce fichier. `_ClientChromaLent` reste utilisé (ligne 252).
- Rouge : **sans objet** (commentaires et retrait de code mort). Vert à HEAD : les 4 tests passent (`testeur-B2-vert-head.log`).
- Il reste le même genre de code mort ailleurs (§4.3).

### Reprise 7 — mot de passe du rôle de test dans un journal → **corrigée (le vrai mot de passe n'est nulle part)**
- Assertions SEC-17 (lu) : les valeurs sont extraites avant l'`assert`, et pytest n'imprime plus le `repr` de `Settings`.
- Grep demandé :
  ```
  $ grep -rlE 'dh_test:[^*@ ]+@' /root/.dh_orch_vague2/ --exclude-dir=venv --exclude-dir=node_modules
  ```
  Ce grep **trouve des fichiers**. Je n'en cite que les noms :
  - `/root/.dh_orch_vague2/testeur-B-rouge-sec17.log`, journal du **premier testeur**, pas de l'implémenteur ;
  - des copies de fichiers suivis par git (`backend/tests/hermetic.py`, `backend/tests/README.md`, `docs/missions/RAPPORT_VAGUE0_AS02.md`, et `hermetic.cpython-312.pyc`) dans les répertoires de scénarios des testeurs (`testeur-A-*`, `testeur-A2/*`, `testeur-C2-*`, et mes `testeur-B2-*`) ; les mêmes fichiers suivis existent aussi dans le worktree.

  Ce que sont ces correspondances, montré sans afficher de valeur :
  ```
  $ grep -oE 'dh_test:[^*@ ]+@' testeur-B-rouge-sec17.log | sed -E 's/(dh_test:)(.{0,3})[^@]*@/\1\2…@/' | sort | uniq -c
        3 dh_test:<ma…@                       (gabarit de masquage du testeur 1, pas de « * »)
  $ grep -oE ... testeur-B2-r5-rouge/backend/tests/hermetic.py | sed ...
  dh_test:cha…@                               (valeur d'exemple d'un fichier suivi, commit fbc5f60)
  ```
  Contrôle décisif : chercher le **vrai** mot de passe, extrait de `TEST_DATABASE_URL` sans l'afficher (longueur 32) :
  ```
  $ grep -rlF --exclude-dir=venv --exclude-dir=node_modules -- "$MDP" /root/.dh_orch_vague2 ; echo "GREP_VRAI_MDP_EXIT=$?"
  GREP_VRAI_MDP_EXIT=1 (1 = aucun fichier)
  $ grep -rslE 'dh_test:[^*@ ]+@' impl-b-* implb* ; echo EXIT=$?
  EXIT=1
  $ grep -c MASQUE impl-b-sec17-rouge.log
  3
  ```
  Le critère littéral « le grep ne trouve rien » **n'est pas tenu**. Les correspondances sont toutes des gabarits ou des valeurs d'exemple, et aucune ne vient de l'implémenteur. Aucun fichier ne contient le mot de passe réel.

## 3. Nouveaux replis silencieux ? Affirmations de §9 sans preuve ?

- **Aucun nouveau repli silencieux constaté** (vérifié par les scénarios du §2).
  - Telegram absent : ligne ERROR à chaque alerte.
  - Erreur cloud vide : 503 et ligne ERROR.
  - Exception hors fournisseur : 503 et ligne ERROR `[Studio chat] appel LLM en echec (<Type>) : …`. Il n'y a plus d'alerte fausse, mais plus d'alerte du tout non plus. Les exceptions possibles à cet endroit sont internes : crédits, tarif, base (lu dans `llm_router_service.py` ; `_call_anthropic`, `_call_openai` et `_call_gpu_local` rattrapent tout et rendent `success=False`).
  - Aucun repli vers un autre fournisseur : 0 ligne `anthropic` dans le scénario Free.
- Affirmations de §9 contrôlées :
  - R1 : « `17 passed`, aucun `skipped` ». **Vérifié.**
  - R2 : rouges `assert 1 == 2` et `assert 2 == 3`. **Vérifié.** « Au plus une fois par 60 s ». **Vérifié** (mon test, trois formes de refus).
  - R3 : « avant `assert 0 == 1`, après une alerte ». **Vérifié.** « Connexion coupée → `error=''` ». **Vrai 5 fois sur 20 seulement** (§4.5).
  - R4 : « `3 failed` (5 / 15 / 15) ». **Vérifié à l'identique.** « Vérifié à la main : clé courte ». **Vérifié et étendu** à 11 cas.
  - R5 : « 147 chemins ; seul `''` des contextes HTTP n'y est pas ». **Inexact dans la forme** : je mesure 148 chemins, dont `''`. Il ne manque rien par rapport à la liste plate.
  - R6 : « `4 passed` ». **Vérifié.**
  - R7 : « `grep -lE … impl-b-* implb*` → aucun fichier ». **Vérifié** (avec `-r`). Le grep de l'orchestrateur sur tout le répertoire trouve en revanche les fichiers du §2.7.
  - Suite après les reprises : « `31 failed, 1160 passed, 2 skipped, 7 xfailed` ». **Vérifié à l'identique** (§1).

## 4. Défauts restants (tous mineurs, ouverts pour Sam)

1. **Grep de la reprise 7 non vide** (§2.7). Ce n'est pas une fuite : le mot de passe réel n'est dans aucun fichier. Mais le critère littéral ne tient pas, à cause du journal `testeur-B-rouge-sec17.log` du testeur 1 (masque `<ma…>`) et des valeurs d'exemple de fichiers suivis. Il faudrait réécrire le motif de contrôle, par exemple chercher la valeur réelle comme au §2.7, plutôt qu'un motif qui ignore seulement `*`.
2. **Libellé « reponse vide » pour une erreur vide** (`studio_chat.py`, `motif = reponse.get("error") or "reponse vide"`, préexistant à `388299a`). Pour `success=False, error=''`, le journal annonce une réponse vide, alors qu'il s'agit d'un échec sans message. Ce n'est pas masqué (ERROR + 503), mais c'est trompeur pour le diagnostic. Cela touche aussi un fournisseur cloud dont l'erreur serait vide : aucune alerte admin, par choix assumé (§3 du rapport).
3. **Code mort laissé par OPS-01** (même nature que la reprise 6). `main.py` (`shutdown_event`) annule encore `app.state.rag_health_task`, que plus personne ne crée (`grep -n rag_health_task app/main.py` → seule la ligne 380). `tests/test_vague_b_b6_health_cache.py` garde `_attendre_tache_rag` (ligne 145), sans aucun appelant (`grep` : seule la définition).
4. **Telegram non configuré : libellé ambigu, rien au démarrage.** `alerter_admin` écrit « non configuré … ou envoi refusé » alors que `telegram_configure()` distingue désormais les deux cas. Aucun message de démarrage ne dit que les alertes n'iront qu'au journal. Ce n'est pas silencieux (§2.2), mais c'est imprécis. Ce module appartient à GL-10 ; le libellé est préexistant.
5. **Test `connexion_coupee` non déterministe à `bcca12c^`** : rouge environ une fois sur quatre (§2.3). À HEAD, il est vert dans les deux cas. La phrase de §9 sur ce cas est donc à nuancer.
6. **Rapport §5.4 / CORS : précision.** En variable d'environnement, `BACKEND_CORS_ORIGINS` doit être du JSON. Une valeur brute `*` ou des origines séparées par des virgules font échouer le démarrage avec `SettingsError: error parsing value for field "BACKEND_CORS_ORIGINS"`, déjà à `388299a` (pydantic-settings 2.1.0, venv parent) comme à HEAD (2.16.1). Ce n'est pas le message SEC-17 ; voir `cors_etoile_brut` et `cors_virgules` au §2.4 et le contrôle à `388299a`. Le validateur `assemble_cors_origins` (découpage par virgules) n'est donc jamais atteint depuis l'environnement. Comme la production démarre aujourd'hui, sa `.env` ne contient pas de valeur brute de ce genre (je suppose, non lu). Le risque du §5.4 se limite donc à `["*"]` en JSON. Cela mériterait une ligne au rapport.

Lu, non exécuté, non classé : `signaler_panne` relâche le verrou pendant l'envoi. Un `signaler_retablissement` concurrent peut retirer la panne avant que `alertee` soit posé, et l'annonce du retour dirait alors à tort « l'alerte de panne n'avait pas pu partir ». Fenêtre étroite, effet limité au texte.

## 5. Ce que je n'ai pas fait
- Pas de mesure de démarrage uvicorn, pas d'audit de dépendances, pas de tests frontend. La revue 1 les a faits et les reprises n'y touchent pas.
- Aucune lecture de `backend/.env` de production, aucune commande git dans le répertoire de production, aucune requête vers 18084 ou 18110 hors la sonde de démarrage préexistante de la fixture `client` (59 comme la référence), aucun envoi Telegram réel.

## 6. État du worktree
```
$ git -C /root/workspace/wt-vague2-b status --short     (vide avant ce commit)
$ git -C /root/workspace/wt-vague2-b rev-parse HEAD
ffc2501ba9c0e281eb41033f2712a3352add3425
```
