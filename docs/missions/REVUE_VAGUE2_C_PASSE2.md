# Revue indépendante, passe 2 — Vague 2 / File C — Produit Pro

Testeur : testeur-C2 (Claude Code), sans participation à l'implémentation ni à la revue 1.
Worktree `/root/workspace/wt-vague2-c`, branche `claude/vague2-c`, HEAD revu
`aced48a72bdec5553ad774d74d18159c81fe8d49` (base `origin/claude/vague-c-20260906` = `388299a`,
51 fichiers). Objet : les 5 reprises de `REVUE_VAGUE2_C.md` (`efb48e4`).
Discipline : « vérifié » = exécuté par moi, sortie citée ; sinon « lu, non exécuté ».
Aucun appel à un modèle payant, aucune génération vers le Spark (le seul trafic vers
`127.0.0.1:18084` est la sonde de démarrage `GET /v1/models` du routeur, déjà présente dans
la suite de référence), aucune lecture de `digital_humans_db`. Base de test hermétique
(`/root/.dh_test_db.env`, `DH_ENV_FILE=backend/.env.test`). Journaux : `/root/.dh_orch_vague2/testeur-C2*`.

## Verdict : **À REPRENDRE** (un défaut ouvert, introduit par la reprise R1)

Les cinq reprises sont faites et prouvées : chaque test ajouté est rouge avec le code
d'avant la reprise et vert à HEAD, la suite ne régresse pas. Mais la reprise R1 a
**rétréci la règle « métadonnée » au point de rouvrir l'autre moitié de CAL-08** : un
rapport, une file, un tableau de bord **nommés** (`Sales Report`, `Support Queue`,
`Sales Dashboard`, `Welcome Email Template`, `Lead Assignment Rule`…) sont de nouveau
classés **objets manquants** (9/9 sur mon jeu ; 0/9 avant la reprise). La mission dit :
« ne jamais classer un Flow/Report/Queue comme objet manquant ». Aucun test ne couvre ce
cas (les 10 métadonnées testées sont des noms génériques ou finissent par `Flow`). Détail D1.

| Reprise | Corrigée | Rouge à `X^` (mesuré) | Vert à HEAD |
|---|---|---|---|
| R1 CAL-08 voisins/enfants | **oui** pour les vrais manques ; **régression** sur les métadonnées nommées (D1) | oui — 10 failed, 25 passed | oui — 35 passed |
| R2 `renamed`/`non_objects` sans lecteur | oui | oui — 2 failed, 22 passed | oui — 24 passed |
| R3 version du texte | oui | oui — backend 2 failed, 21 passed ; frontend `not ok 4` | oui — 23 passed ; frontend 7/7 |
| R4 repli non dit (chat projet, chat d'exécution) | oui | oui — 2 failed, 21 passed ; frontend `not ok 7` | oui |
| R5 montant refusé non tracé | oui | oui — 6 failed, 17 passed | oui ; migration 023c montée/descente/remontée OK |

## 1. Suites mesurées par moi

### Backend, HEAD `aced48a`

    cd /root/workspace/wt-vague2-c/backend
    nohup bash -c 'set -a; . /root/.dh_test_db.env; set +a; export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurC2_head; \
      /root/workspace/wt-vague2-c/backend/venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE; echo "PYTEST_EXIT=$?"' \
      > /root/.dh_orch_vague2/testeur-C2-backend-head.log 2>&1 &
    → 31 failed, 1153 passed, 2 skipped, 7 xfailed, 1495 warnings in 643.99s (0:10:43)
      PYTEST_EXIT=1

Référence (`reference_tests.log`, `388299a`) : `31 failed, 1052 passed, 2 skipped, 7 xfailed`.

    grep "^FAILED" testeur-C2-backend-head.log | sed 's/ - .*//' | sort > testeur-C2/echecs-head.txt
    grep "^FAILED" reference_tests.log         | sed 's/ - .*//' | sort > testeur-C2/echecs-ref.txt
    diff testeur-C2/echecs-ref.txt testeur-C2/echecs-head.txt && echo IDENTIQUES
    → IDENTIQUES
      27 tests/test_lot_c_injection_commandes.py, 3 tests/test_auth.py, 1 tests/test_emma_phase3.py

+101 passés sur la référence : +80 (travail initial, compté par la revue 1) +21 (reprises).
Les 21, comptés sur mes exécutions des fichiers à HEAD : CAL-08 23 → 35 (+12, R1) ;
GL-12 21 → 24 (+3, R2) ; GL-22 17 → 23 (+6 : R3 +3, R4 +3). Aucun skip/xfail ajouté :

    git diff efb48e4 HEAD -- backend/tests frontend/tests | grep -cE "^\+.*(pytest\.mark\.(skip|xfail)|pytest\.skip|xfail|test\.skip|\.only\()"
    → 0

### Frontend

    cd frontend; node --experimental-strip-types --test tests/*.test.ts; ./node_modules/.bin/tsc -b
    → # tests 68 / # pass 68 / # fail 0 / NODE_TEST_EXIT=0 / TSC_EXIT=0
    (journal /root/.dh_orch_vague2/testeur-C2-front-head.log)

68 = 67 de la revue 1 + 1 (R4). État du worktree après les suites : `git status --short` vide.

## 2. Méthode des rouges

Script `/root/.dh_orch_vague2/testeur-C2-prepare.sh <scénario> <X>` : `git archive HEAD` extrait
sous `/root/.dh_orch_vague2/testeur-C2-<scénario>/`, puis **chaque fichier de code** touché
par X remis à `X^` (`git show X^:<f>`), fichiers de `backend/tests`, `frontend/tests` et
`docs/missions` gardés à HEAD, `node_modules` du worktree en lien. Une copie HEAD intacte
(`testeur-C2-head`) sert de témoin. Aucun `git checkout` dans le worktree. Lancement :
`/root/.dh_orch_vague2/testeur-C2-rouges.sh` (venv du worktree, `DH_TEST_RUN_ID` unique par
scénario), journal `testeur-C2-rouges.log` ; frontend : `testeur-C2-front-rouges.log`.
Les fichiers de code backend des reprises ne se recouvrent pas ; seul
`frontend/src/lib/opusConsent.ts` est touché par R3 et R4 (voir R3).

## 3. Reprises, une par une

### R1 — un objet voisin ou enfant ne couvre plus l'objet demandé (`1ec18a0`)

**Correctif lu** (`app/services/rapprochement_objets.py`) : `_concepts_compatibles` n'accepte
plus que l'égalité des concepts, ou une inclusion dont **tous** les mots en plus sont des
qualifiants (`ecommerce, online, web, digital, sf, salesforce, dh, data, info, information`) ;
`_SUFFIXES_METADONNEE = ("flow",)`, le reste sur liste exacte `_METADONNEES`.

**Tests lus.** `VOISINS` (7 cas, dont les 4 de la revue 1 et `Contact`↔`Emergency_Contact__c`) :
`_manques(...) == [reference.lower()]` — prouve qu'un voisin ne couvre pas.
`test_controle_negatif_un_objet_cpq_n_est_pas_une_metadonnee` : `missing == [nom]` et
`non_objects == []` — prouve. `test_jeu_du_testeur_six_vrais_manques_restent_six` : `missing`
= les 6, `renamed == []`, `score == 0` — prouve. Les deux variantes positives remplacées
(`Point_Transaction__c`, `Maintenance_Record__c`) sont dites dans le rapport ; les deux
anciennes passent en `RENOMMAGES_REFUSES` (manques attendus).

**Rouge / vert (exécuté).**

    testeur-C2-r1 (rapprochement_objets.py à 1ec18a0^, tests HEAD) :
      AssertionError: assert [] == ['loyalty_program__c'] / ['credit_note_line__c'] / ['servicecontract'] /
        ['opportunity'] / ['contact'] / ['price rule'] / ['quote template'] / ['mouvement_points__c'] / ['maintenance__c']
      10 failed, 25 passed
    testeur-C2-head : 35 passed

Écart avec le rapport (§7 : « au efb48e4 : 8 failed, 25 passed ») : j'obtiens **10** échecs —
les deux `test_un_mot_de_plus_non_qualifiant_n_est_pas_un_renommage` en plus ; le chiffre du
rapport ne porte pas sur le fichier de test final. Sans effet sur la conclusion.

**Recompte avec le script de la revue 1** (`testeur-C/compte_cal08_testeur.py`, exécuté depuis
la copie HEAD, `testeur-C2-r1-recompte.log`) — chiffres du rapport confirmés :

    [implementeur] apres: manques=7 faux_positifs=2 vrais_retenus=5/5 score=40.0 renommes=['actif__c->asset', 'ligne_retour_ecommerce__c->return_line__c']
    [testeur-negatifs] apres: manques=6 faux_positifs=0 vrais_retenus=6/6 score=0.0 renommes=[]

**Mon jeu de contrôles** (`/root/.dh_orch_vague2/testeur-C2-r1/controles_r1.py`, module
extrait par `git show 1ec18a0^:` et `git show HEAD:`, `classer_references([ref], objets)`
avec un seul objet de conception ; journal `testeur-C2-r1-controles.log`) :

    A. vrais manques, voisin/enfant présent (attendu MANQUANT)            avant_R1        HEAD
      Invoice            vs Invoice_Line__c           MANQUANT              MANQUANT
      Invoice__c         vs Invoice_Payment__c        RENOMME->invoice_payment__c  MANQUANT
      Account            vs Account_Team__c           MANQUANT              MANQUANT
      Facture__c         vs Invoice_Line__c           MANQUANT              MANQUANT
      Contrat__c         vs Contract_Line_Item__c     MANQUANT              MANQUANT
      Campaign_Member__c vs Campaign__c               MANQUANT              MANQUANT
      Order_Item__c      vs Order__c                  MANQUANT              MANQUANT
      Quote_Line__c      vs Quote__c                  MANQUANT              MANQUANT
      Case               vs Case_Comment__c           MANQUANT              MANQUANT
      Loyalty_Tier__c    vs Loyalty_Program__c        MANQUANT              MANQUANT
      Product            vs Product_Price__c          RENOMME->product_price__c    MANQUANT
      Shipment__c        vs Shipment_Item__c          MANQUANT              MANQUANT
      Work_Order__c      vs Work_Order_Line_Item__c   RENOMME->work_order_line_item__c MANQUANT
      Asset              vs Asset_Relationship__c     MANQUANT              MANQUANT
      Subscription__c    vs Subscription_Line__c      MANQUANT              MANQUANT
      Payment__c         vs Payment_Schedule__c       MANQUANT              MANQUANT
    BILAN A-vrai-manque: 16/16 conformes a HEAD   (3 masqués avant R1)

    B. vrais renommages (attendu RENOMME, jamais MANQUANT)
      credit_note__c vs Avoir__c ; Avoir__c vs Credit_Note__c ; Avoir vs credit_note__c ;
      Ecommerce_Order__c vs Order__c ; E_Commerce_Order__c vs Order__c ; Order vs Ecommerce_Order__c ;
      ligne_retour_ecommerce__c vs Return_Line__c ; Commande_Client__c vs Customer_Order__c ;
      Facture__c vs Invoice__c ; Programme_Fidelite__c vs Loyalty_Program__c ;
      Online_Store__c vs Boutique__c ; Reclamation__c vs Claim__c ; Fournisseur__c vs Vendor__c
      → tous RENOMME->… (sens) avant et après
    BILAN B-renommage: 13/13 conformes a HEAD

    D. objets CPQ (attendu MANQUANT, pas métadonnée)
      Price Rule  NON_OBJET -> MANQUANT ; Quote Template NON_OBJET -> MANQUANT ; Product Rule NON_OBJET -> MANQUANT ;
      SBQQ__PriceRule__c, SBQQ__QuoteTemplate__c MANQUANT -> MANQUANT
    BILAN D-objet-cpq: 5/5 conformes a HEAD

    C. métadonnées (attendu NON_OBJET)
      Flow, Flows, Case_Escalation_Flow, Record-Triggered Flow, Report, Reports, Queue, Queues,
      Report Type, Dashboard, Email Template, Approval Process, List View  → NON_OBJET avant et après
      'Sales Report'            avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Monthly_Pipeline_Report' avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Support Queue'           avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Escalation_Queue'        avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Case Queue'              avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Sales Dashboard'         avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Welcome Email Template'  avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Lead Assignment Rule'    avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
      'Case Escalation Rule'    avant_R1=NON_OBJET  HEAD=MANQUANT  ECART
    BILAN C-metadonnee: 13/22 conformes a HEAD

Conclusion R1 : la règle n'est **plus trop large** (16/16 vrais manques retenus, dont 3 que
la version d'avant masquait encore) ni **trop étroite pour les renommages** (13/13, dont
`credit_note__c` et les variantes `ecommerce`). `Price Rule` et `Quote Template` ne sont plus
des métadonnées. **Mais** les Flow sont seuls protégés par suffixe : Report, Queue, Dashboard,
Email Template, Assignment/Escalation Rule nommés deviennent des objets manquants. Bout en
bout (`testeur-C2-r1/integration_r1.py`, `calculate_coverage_score` à HEAD,
`testeur-C2-r1-integration.log`) :

    missing= ['escalation_queue', 'lead assignment rule', 'sales dashboard', 'sales report', 'support queue']
    non_objects= ['case_escalation_flow', 'queue', 'report']
    score= 16.7

Chaque élément de `missing` devient un `critical_gap` `element_type: object`, `severity: high`
(`generate_coverage_report_programmatic`, lu) et part dans les `fix_instructions` d'Emma —
exactement le motif CAL-08 (« classait "Flow" en objet manquant »). → **D1**.

### R2 — renommages et non-objets rendus dans le SDS (`e820382`)

**Correctif lu** : `partials/coverage_report.html.j2` lit `coverage.by_category.data_model.renamed`
et `.non_objects`, rend un tableau (nom cité / objet de la conception / « même sens » ou
« même nom, autre graphie ») et la liste des non-objets ; 9 clés ajoutées au catalogue FR.
Chaîne de transmission lue : `ResearchAnalystAgent` (mode validate) met `by_category` dans
`content` du livrable ; `collect_sds.collect_coverage` rend `content.get("by_category", {})`.

**Test lu** : rend le gabarit FR et EN avec un `data_model` injecté et exige le titre, la
paire `credit_note__c`/`avoir__c`, la méthode et `case_escalation_flow` dans le texte
visible ; contrôle négatif : sans rapprochement, aucune section. Il ne passe pas par
`calculate_coverage_score` ; je l'ai fait (ci-dessous).

**Rouge / vert (exécuté)** :

    testeur-C2-r2 (gabarit + sds_i18n.py à e820382^) :
      AssertionError: assert 'Objets rapprochés sous un autre nom' in 'SDS · Projet témoin #7 …
      AssertionError: assert 'Objects matched under another name' in 'SDS · Projet témoin #7 …
      2 failed, 22 passed   (le contrôle négatif est vert, attendu)
    testeur-C2-head : 24 passed

**Bout en bout (exécuté)**, sortie réelle de `calculate_coverage_score` rendue par le gabarit
(`testeur-C2-r2-e2e.py`, `testeur-C2-r2-e2e.log`) :

    dm.renamed = [{'reference': 'actif__c', 'objet': 'asset', 'methode': 'sens'}, {'reference': 'credit_note__c', …}, {'reference': 'ecommerce_order__c', 'objet': 'order__c', …}]
    --- fr : Objets rapprochés sous un autre nom Comptés comme couverts : … À vérifier. Nom cité par les cas d'usage
        Objet de la conception Rapprochement actif__c asset même sens credit_note__c avoir__c même sens
        ecommerce_order__c order__c même sens Non comptés comme objets (métadonnées Salesforce citées par les cas d'usage) : report
    --- en : Objects matched under another name Counted as covered: … actif__c asset same meaning … Not counted as objects …: report

`grep` montre maintenant un lecteur. **Corrigée.**

### R3 — la version du texte affiché est envoyée, vérifiée, tracée (`88e0249`)

**Correctif lu** : `buildStartBody` ajoute `texte_version_opus` à toute décision ;
`ExecutionCreate.texte_version_opus` ; `start_execution`, quand une décision est requise,
lève 409 `consentement_opus_texte_perime` si la version reçue diffère de `TEXTE_VERSION`
(absente comprise), **avant** `_prepare_execution`. L'assertion trompeuse du test frontend
est retirée ; un test backend lit la constante dans `frontend/src/lib/opusConsent.ts` et
l'égale à celle du serveur.

**Tests lus** : `test_une_decision_sans_la_version_du_texte_affiche_est_refusee[absente/autre]`
(accepte au bon montant, version absente ou autre) : 409, code `consentement_opus_texte_perime`,
`Execution` du projet = 0 — prouve. Le test d'acceptation exige `trace.texte_version == VERSION_TEXTE`.
Frontend : le corps attendu contient `texte_version_opus` pour accepter **et** refuser.

**Rouge / vert (exécuté)** :

    testeur-C2-r3 backend : …test_vague2_c_gl22_consentement_opus.py:527: AssertionError:
      {"execution_id":1,"status":"started",…}   ×2 → 2 failed, 21 passed
    testeur-C2-r3 frontend : not ok 4 - accepter envoie le montant affiché, … les deux envoient la version du texte
      (not ok 7 aussi : opusConsent.ts à 88e0249^ précède R4, `withFallbackNotice` absent — attendu)
    testeur-C2-head : 23 passed ; frontend 7/7

**Ma sonde** (refus non couvert par les tests ; fichier `testeur-C2-sonde_r3.py` copié
**dans les copies** `testeur-C2-r3` et `testeur-C2-head`, jamais dans le worktree ;
`testeur-C2-sonde-r3.log`) : 4 cas {refuse, accepte} × {version absente, `gl22-v0-ancien`},
exigeant 409 `texte_perime`, 0 `Execution`, **0 `ConsentementOpus`**, **`pool == []`** (rien
enfilé) ; contrôle négatif : refus avec la bonne version → 202, une trace, un enfilage.

    ===== r3  : SONDE refuse None 202 None / refuse gl22-v0-ancien 202 / accepte None 202 / accepte gl22-v0-ancien 202
                4 failed, 1 passed
    ===== head: SONDE refuse None 409 consentement_opus_texte_perime / refuse gl22-v0-ancien 409 … / accepte None 409 … / accepte gl22-v0-ancien 409 …
                SONDE trace refuse 0 6720 gl22-v1-20261024
                5 passed

**Corrigée.** Limite (lu) : la version n'est liée au texte que par discipline (« toute
modification change `OPUS_CONSENT_TEXT_VERSION` ») ; aucun test ne fait échouer un texte
modifié sans changement de version. Côté client, ce 409 n'ouvre pas l'écran
(`readOpusConsentRequest` ne connaît que `requis` et `montant_perime`) : il affiche
`detail.message`, en français seulement (lu dans `apiContracts.ts:87`, non exécuté).

### R4 — repli Opus → Sonnet dit au client (chat projet Team, chat d'exécution) (`439a66a`)

**Correctif lu** : `SophieChatService.chat` rend `avis_repli` ; `SophieResponse` et
`ChatResponse` (HITL) le portent ; `ProjectDetailPage`, `ChatSidebar`, `ChatSidebarStudio`
l'ajoutent au message affiché (`withFallbackNotice`). Le journal du routeur dit désormais
`repli — … (avis_repli rendu a l'appelant[, marque degraded posee])` : la marque n'est
annoncée que si `execution_id` existe, ce qui est exact (lu, `llm_router_service.py:1218-1226`).

**Tests lus** : chat projet Team → transport `['anthropic/claude-sonnet']` et `avis_repli`
contenant `claude-opus-5` et `claude-sonnet-5` ; chat d'exécution Marcus Pro → idem ; contrôle
négatif Pro (Sophie sur Sonnet par palier) → `avis_repli is None`. Prouvent la réponse HTTP.
Le test frontend ne prouve que l'aide `withFallbackNotice`, pas son branchement dans les
trois composants (lu ; `tsc -b` passe).

**Rouge / vert (exécuté)** :

    testeur-C2-r4 : …:550: AssertionError: {'context_used': ['project'], 'message': 'ok', 'tokens_used': 2000}
                    …:565: AssertionError: {'agent_id': 'marcus', 'agent_name': 'Marcus', 'change_request': None, 'response': 'ok'}
                    2 failed, 21 passed   (contrôle négatif vert)
    frontend r4   : not ok 7 - reprise R4 : l’avis de repli renvoyé par un chat est ajouté à la réponse affichée (rouge trivial : fonction absente)
    testeur-C2-head : 23 passed ; frontend 7/7

**Corrigée.** Remarque D3 sur la langue et le contenu de l'avis.

### R5 — le montant présenté est tracé, aussi sur un refus (`6927eb0`)

**Correctif lu** : colonne `opus_consents.credits_presentes` (NOT NULL, CHECK ≥ 0) au modèle
et dans la migration 023c modifiée sur place ; `enregistrer_decision` y écrit
`estimation.credits_estimes` quelle que soit la décision ; `credits_estimes` reste le
plafond accepté (0 sur un refus). 023c n'existe pas dans le code de production
(`ls /root/workspace/digital-humans-production/backend/alembic/versions/ | grep -E "^02[2-9]"`
→ `022_sec12_chat_logs_reclamation.py` seulement) : la modification sur place ne touche
aucune base migrée connue.

**Tests lus** : acceptation → `credits_presentes == montant` ; refus →
`trace.credits_presentes == estimation > 0` (comparaison chaînée : égalité **et** > 0) et
`credits_estimes == 0`. Prouvent.

**Rouge / vert (exécuté)** :

    testeur-C2-r5 : …:368: AttributeError: 'ConsentementOpus' object has no attribute 'credits_presentes'
                    …:404: AttributeError: … (test du refus)
                    + 4 × TypeError: 'credits_presentes' is an invalid keyword argument (aide _consentir des tests routeur)
                    6 failed, 17 passed
    testeur-C2-head : 23 passed

Rouges attendus pour un ajout de colonne (attribut absent) ; le rapport annonce « 2 failed,
18 passed » au commit précédent — il ne compte pas les 4 échecs de l'aide `_consentir`
modifiée dans le même commit. Sans effet sur la conclusion.

**Migration 023c, Alembic réel sur base jetable** (`testeur-C2-mig/migration_023c_c2.py`,
base `digital_humans_test_testeurc2_mig023c` dérivée de `TEST_DATABASE_URL`, rôle du
gabarit de test, garde `hermetic.assert_not_production_database`, base détruite à la fin ;
schéma posé par `create_all` **sans** `opus_consents`, Opus à `requires_opt_in=false` ;
journal `testeur-C2-migration.log`) :

    [avant upgrade (etat 016 : opt-in false)] table opus_consents=False requires_opt_in(claude-opus-5)=False
    $ alembic upgrade head -> rc=0 … Running upgrade 022_sec12_chat_logs_reclamation -> 023c_consentement_opus
    [apres upgrade head] table opus_consents=True requires_opt_in(claude-opus-5)=True
       colonnes [… ('credits_estimes', 'INTEGER', False), ('credits_presentes', 'INTEGER', False), ('texte_version', 'VARCHAR(32)', False), …]
       checks [ck_opus_consents_credits 'credits_estimes >= 0', ck_opus_consents_decision …, ck_opus_consents_presentes 'credits_presentes >= 0']
    $ alembic upgrade head -> rc=0                        (rejeu : no-op)
    $ alembic downgrade 022_sec12_chat_logs_reclamation -> rc=0
    [apres downgrade 022] table opus_consents=False requires_opt_in(claude-opus-5)=False
    $ alembic upgrade head -> rc=0
    [apres re-upgrade] table opus_consents=True requires_opt_in(claude-opus-5)=True   (mêmes colonnes et contraintes)
    INSERT credits_presentes absent : REFUSE IntegrityError (psycopg2.errors.NotNullViolation) null value in column "credits_presentes" …
    INSERT credits_presentes=-1 : REFUSE IntegrityError (psycopg2.errors.CheckViolation) … "ck_opus_consents_presentes"
    INSERT decision=peut-etre : REFUSE IntegrityError (psycopg2.errors.CheckViolation) … "ck_opus_consents_decision"
    INSERT refus valide 6720 : ACCEPTE
    lignes : [('refuse', 0, 6720, 'gl22-v1-20261024')]
    base jetable detruite : digital_humans_test_testeurc2_mig023c
    EXIT=0

**Corrigée.** Limite (lu) : sur un refus, le client n'envoie aucun montant ; `credits_presentes`
est l'estimation du serveur **au moment du lancement**, pas un montant reçu du client (à
l'inverse de l'acceptation, contrôlée par 409 `montant_perime`, et de la version, R3). Si
l'estimation change entre l'affichage et le refus, la trace diffère de l'écran. Remarque D4.

## 4. Pas de nouveau repli silencieux, pas d'Opus sans consentement

    git diff efb48e4 HEAD --stat -- app agents
    → hitl_routes.py 3, execution_routes.py 15, project_chat.py 3, models/consentement_opus.py 10,
      schemas/execution.py 3, schemas/project_conversation.py 2, consentement_opus_service.py 2,
      llm_router_service.py 12, rapprochement_objets.py 51, sophie_chat_service.py 4
    git diff efb48e4 HEAD -- app/services/llm_router_service.py | grep -E "^[+-]" | grep -v "^[+-]\s*#"
    → seul le message du logger.warning change (« repli annonce » → « repli … avis_repli rendu a l'appelant »)

Aucune reprise ne touche `_select_provider`, `_appliquer_consentement_opus` (hors journal),
la réservation, les chaînes de repli ni `sans_compte`. Appelants (lu) :

    grep -rnE "\.complete\(|complete_sync\(|generate_llm_response(_async)?\(|\.generate_async\(|generate_json_response\(" app agents
    → agents/base.py, agents/roles/* (13 fichiers), hitl_routes.py, studio_chat.py, agent_test_logger.py,
      change_request_service.py (2), llm_router_service.py (6), llm_service.py (7), sds_section_writer.py,
      sophie_chat_service.py, sophie_concierge_service.py
    grep -n "_appliquer_consentement_opus\|async def complete" app/services/llm_router_service.py
    → 1103: async def complete / 1112: provider_str, opt_in, avis_repli = self._appliquer_consentement_opus(

Même ensemble d'appelants qu'à la revue 1, tous via `complete()` où le contrôle précède la
réservation. Exécuté à HEAD : les 23 tests GL-22 passent, dont `test_sans_consentement_marcus_passe_sur_sonnet_et_le_repli_est_annonce`,
`test_consentement_d_une_autre_execution_ne_vaut_pas`, `test_plafond_consenti_atteint_le_reste_passe_sur_sonnet_annonce`.
R3 ajoute un refus (409), jamais un passage par défaut ; R4 ajoute une annonce là où le
repli était seulement journalisé. **Aucun nouveau repli silencieux, aucun chemin Opus rouvert.**

## 5. Défauts restants

**D1 — CAL-08 : un Report, une Queue, un Dashboard nommés sont de nouveau des « objets
manquants » (régression introduite par `1ec18a0`, non testée). Ouvert.**
Fichier : `backend/app/services/rapprochement_objets.py` (`_SUFFIXES_METADONNEE = ("flow",)`).
Cause : pour sortir `Price Rule` / `Quote Template` des métadonnées, la reprise a retiré
**tous** les suffixes sauf `flow` ; seuls les noms génériques exacts de `_METADONNEES`
restent protégés. Preuve : §3 R1, jeu C (9/9 noms propres de métadonnées : NON_OBJET avant
la reprise, MANQUANT à HEAD) et bout en bout `missing= ['escalation_queue', 'lead assignment rule',
'sales dashboard', 'sales report', 'support queue']` → `critical_gaps` de sévérité `high`.
La mission dit « ne jamais classer un Flow/Report/Queue comme objet manquant ». Piste (non
appliquée, choix pour Sam) : remettre `report`, `queue`, `dashboard`, `email template`,
`assignment rule`, `escalation rule`, `list view` comme suffixes pour un nom **sans** `__c`,
en gardant `rule`/`template` seuls hors liste (CPQ) ; tests rouges d'abord avec les 9 noms ci-dessus.

**D2 — CAL-08 : les objets d'infrastructure restent dans `missing` (préexistant, cause citée
au rapport mais ni corrigée ni déclarée ouverte).** Le rapport §2 écrit « `SF_INFRA_OBJECTS`
n'était appliqué qu'au score, jamais à la liste des manques » ; c'est toujours le cas.
Exécuté (`testeur-C2-infra.py`, copie HEAD) : UC citant `Case, User, Group, BusinessHours, Contract`,
conception `Case` → `missing= ['businesshours', 'contract', 'group', 'user'] score= 100.0` :
quatre `critical_gaps` « object/high » pour un score de 100 %. Même comportement au parent
`388299a` (`"missing": list(uc_objects - sd_objects)`, lu). Non introduit par la branche ;
à déclarer ouvert.

**D3 — GL-22 / langue : l'avis de repli montré au client est en français seulement et
expose des identifiants internes (lu, non exécuté en anglais).** Texte construit par le
routeur : `f"{tarif.model_name} non servi ({motif}) : {request.agent_type or 'agent'} est servi par {modele_repli}."`
(ex. du test frontend : `claude-opus-5 non servi (aucune exécution) : pm est servi par claude-sonnet-5.`).
R4 l'ajoute désormais à la bulle de chat pour tout compte Team (Sophie routée sur Opus, sans
consentement possible dans le chat : un avis à **chaque** message). Le 409
`consentement_opus_texte_perime` est aussi en français seulement. Contraire à l'esprit de la
ligne « chaque agent parle dans sa langue » ; non bloquant pour Pro (Sophie y est sur Sonnet
par palier, contrôle négatif vert).

**D4 — GL-22 : sur un refus, `credits_presentes` est l'estimation serveur, pas le montant
affiché reçu du client** (lu ; §3 R5). Écart possible seulement si le tarif change entre
l'affichage et le refus. À trancher par Sam (accepter, ou faire envoyer et vérifier le
montant aussi sur un refus, comme la version en R3).

### Remarques (non bloquantes)

- R1 change deux cas du jeu initial : `mouvement_points__c` ↔ `Loyalty_Point_Transaction__c`
  redevient un manque. C'est un exemple réel du backlog (exécutions 172-175) ; sans rejeu du
  brief 117 (non fait, coût), on ne sait pas si ce faux positif réel revient. Le rapport le dit.
- Écarts de comptage du rapport §7 sur les rouges de R1 (8 au lieu de 10) et de R5 (2 au
  lieu de 6) : les deux chiffres ont été mesurés sur un état de test antérieur au commit ;
  la conclusion « rouge avant, vert après » tient.
- Les remarques de la revue 1 (`ON DELETE CASCADE` sur la trace, plafond non atomique,
  `sans_compte` qui court-circuite le contrôle, consentement par exécution et non par agent)
  sont inchangées (lu).

## 6. État final du worktree

Avant le commit de cette revue :

    git status --short   → (vide)
    git rev-parse HEAD   → aced48a72bdec5553ad774d74d18159c81fe8d49

Seul fichier commité : `docs/missions/REVUE_VAGUE2_C_PASSE2.md`, avec
`git -c core.hooksPath=/dev/null commit`, non poussé. Copies de travail et sondes :
`/root/.dh_orch_vague2/testeur-C2-{r1,r2,r3,r4,r5,head}/`, scripts et journaux `testeur-C2*`.
