# Revue indépendante — Vague 2 / File C — Produit Pro (consentement Opus, qualité agents)

Testeur : testeur-C (Claude Code), sans participation à l'implémentation.
Worktree `/root/workspace/wt-vague2-c`, branche `claude/vague2-c`, HEAD revu
`c37e6aa5fdbbf70257105c0b63ec6827a5de24f4` (8 commits depuis
`origin/claude/vague-c-20260906` = `388299a`, 45 fichiers).
Discipline : « vérifié » = exécuté par moi, sortie citée ; sinon « lu, non exécuté ».
Aucun appel à un modèle payant, aucune génération vers le Spark, aucune
lecture de `digital_humans_db` ; base de test hermétique (`/root/.dh_test_db.env`,
`DH_ENV_FILE=backend/.env.test`). Journaux sous `/root/.dh_orch_vague2/testeur-C*`.

## Verdict : **À REPRENDRE**

La suite ne régresse pas, chaque correctif a un test rouge sans lui, GL-22 n'a
aucun chemin qui serve Opus sans consentement, GL-12 et GL-26 sont confirmés
par exécution. Mais :

- **CAL-08 introduit le défaut inverse** de celui qu'il corrige : des objets
  réellement absents de la conception sont désormais classés « renommés » et
  comptés couverts. Sur un jeu de 6 vrais manques construit par moi : 6/6
  retenus au parent, **0/6 après**, score objets 0 → 100 (R1). Les contrôles
  négatifs du lot ne couvrent pas ce cas.
- Un test frontend GL-22 annonce « la version affichée est celle que le
  backend trace » mais compare la constante à un littéral du test (R3).

Liste des reprises au §6.

## 1. Suites mesurées par moi

### Backend (HEAD `c37e6aa`)

    cd backend; set -a; . /root/.dh_test_db.env; set +a
    export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=testeurC_head1
    ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE
    → 31 failed, 1132 passed, 2 skipped, 7 xfailed, 1490 warnings in 843.21s (0:14:03)
    (journal /root/.dh_orch_vague2/testeur-C-suite-head.log)

Référence (orchestrateur, `388299a`) : `31 failed, 1052 passed, 2 skipped, 7 xfailed`.
Comparaison nom par nom :

    grep "^FAILED" testeur-C-suite-head.log | sed 's/ - .*//' | sort > testeur-C/echecs-head.txt
    grep "^FAILED" reference_tests.log      | sed 's/ - .*//' | sort > testeur-C/echecs-ref.txt
    diff testeur-C/echecs-ref.txt testeur-C/echecs-head.txt && echo IDENTIQUES
    → IDENTIQUES
    27 test_lot_c_injection_commandes.py, 3 test_auth.py, 1 test_emma_phase3.py

+80 passés = 17 (GL-22) + 19 (langue/persona) + 23 (CAL-08) + 21 (GL-12), comptés
dans les fichiers. Aucun `skip`/`xfail` ajouté :

    git diff origin/claude/vague-c-20260906...HEAD -- backend/tests | grep -nE "^\+.*(pytest\.mark\.(skip|xfail)|pytest\.skip|xfail)"
    → (rien)

### Frontend

    cd frontend; node --experimental-strip-types --test tests/*.test.ts → # tests 67 / # pass 67 / # fail 0
    ./node_modules/.bin/tsc -b                                         → TSC_EXIT=0
    (journal /root/.dh_orch_vague2/testeur-C-front-head.log)

Parent `388299a` (src + tests exportés par `git archive` dans
`testeur-C/front-parent`, `node_modules` du worktree en lien) :
`# tests 61 / # pass 61 / # fail 0` — la déduction « 61 = 67 − 6 » du rapport est confirmée.

## 2. Tests ajoutés : assertion lue, rouge au parent

Méthode (script `/root/.dh_orch_vague2/testeur-C/rouge.sh`, journal
`testeur-C-rouge.log`) : tests de HEAD, fichiers de code du commit X remis à
`X^` (`git checkout X^ -- …`), fichiers neufs de X mis de côté, pytest, puis
`git checkout HEAD -- …`. État final vérifié : `git status --short` vide,
`git rev-parse HEAD` = `c37e6aa…`.

| Groupe (commit) | Assertion lue | Rouge sans le correctif (mesuré) |
|---|---|---|
| GL-22 routeur, 7 tests (`640f938`) | prouve : fournisseur réellement appelé (transport capturé), modèle débité, marque `degraded`. Le test plafond exige `[opus, sonnet]` ; autre exécution → Sonnet. **Non couvert : consentement donné par un autre compte** (testé par moi, §3, comportement correct). | oui — `14 failed, 3 passed` sur le fichier ; les 3 verts sont les contrôles négatifs. Motifs (`--tb=line`, `testeur-C-rouge-gl22-motifs.log`) : `ModelNotAllowedError … exige un opt-in explicite` (Marcus Pro sans consentement), `ModuleNotFoundError app.models.consentement_opus` (4 tests qui posent une ligne de consentement : rouge trivial, la fonction n'existe pas au parent) |
| GL-22 route de lancement, 6 tests | prouve : 409 sans décision et **rien créé ni enfilé** (`count()==0`, `pool==[]`), trace (utilisateur, décision, montant, modèle, `created_at`, version), montant périmé refusé, refus tracé + marque | oui — `{"detail":"Not Found"}` (estimation), `202 … started` là où 409 attendu, `KeyError: 'requis'` |
| GL-22 migration, 2 tests | prouve l'upgrade/downgrade de la colonne ; **la branche `create_table` n'est jamais exercée** (la table existe déjà par `create_all` du `db_session`) — couvert par mon passage Alembic réel (§3.4) | oui (fichier absent : trivial) |
| GL-22 dialogue Studio, 2 tests (`a8d06ff`) | prouve `avis_repli` contenant Opus et Sonnet ; contrôle négatif sans avis | oui — studio_chat.py à `a8d06ff^` : `1 failed, 1 passed` (contrôle vert) |
| Langue, 6 tests (`b14086f`) | prouve la consigne envoyée au modèle (bouchon) — pas la réponse d'un modèle réel, et le rapport le dit | oui — `6 failed, 13 passed`. Motif : `'Réponds en français' is contained here: … Réponds en français, de manière concise et professionnelle.` |
| GL-26 prompt par agent, 11 tests | prouve `Tu es <Nom>,` sans identité d'un autre agent, bon `agent_type` | **verts au parent (11/11)** — c'est voulu : ils infirment l'hypothèse du backlog (§4) |
| GL-26 historique, 2 tests | prouve l'étiquette de l'agent réel / « Autre agent du studio » | oui — prompt d'Olivia au parent : `Olivia: En tant que Project Manager senior, je cadre le projet.` (`testeur-C-rouge-langue-motifs.log`) |
| CAL-08, 23 tests (`a4d43f0`) | prouve les 6 variantes du backlog, les 10 métadonnées, 5 contrôles négatifs. **Ne prouve pas qu'un vrai manque reste un manque en général** : aucun contrôle sur l'inclusion à deux mots ou plus (R1) | oui — `18 failed, 9 passed` (5 contrôles négatifs + 4 CAL-09 verts) |
| Sommaire latéral, 1 test (`e6f939f`) | prouve l'absence de compteurs `(\d+…)` dans le sommaire latéral et de « derived from the 11 agent artifacts » | oui — shell à `e6f939f^` : `1 failed` |
| GL-12, 20 tests (`6b8c22a`) | prouve : 0 texte en dur hors `_()` (13 fichiers), chaque clé traduite, phrase d'excuse absente, rendu FR sans texte fixe long en anglais **avec contrôle que le rendu EN en fait apparaître ≥ 200**, rendu EN intact, `TraductionManquante` levée | oui — `20 failed, 1 passed` (le vert : sommaire, déjà corrigé au parent) ; 5 de ces rouges sont triviaux (`sds_i18n.py` absent) |
| GL-19 modifié (`test_vague1_d_gl19_mentions_ia.py`) | diff = 6 lignes d'installation de l'i18n (`installer_i18n(env, "en")`) avant le rendu ; **aucune assertion modifiée** (lu dans le diff) | version HEAD contre gabarits du parent : `1 failed, 9 passed` ; version parent : `10 passed` |
| Frontend `opusConsent.test.ts`, 6 tests (`47a5f87`) | prouve la lecture des 409, le corps de lancement, le texte FR/EN. **L'assertion de version ne prouve pas ce que dit son commentaire** (R3) | oui — `ERR_MODULE_NOT_FOUND … src/lib/opusConsent.ts` (`# tests 1 / # fail 1`) ; trivial |

## 3. GL-22 — chemins d'appel Opus

### 3.1 Recherche des appelants (lu)

    grep -rnE "generate_llm_response(_async)?\(|\.complete\(|\.generate_async\(|generate_json_response\(" app agents
    → agents/roles/* (13 fichiers), agents/base.py, hitl_routes.py, studio_chat.py, agent_test_logger.py,
      change_request_service.py, sds_section_writer.py, sophie_chat_service.py, sophie_concierge_service.py,
      llm_service.py, llm_router_service.py

Tous convergent vers `LLMRouterService.complete()` (`generate` → `complete_sync`
→ `complete`), où `_appliquer_consentement_opus` est appelé avant la réservation.
Seconde barrière : la réservation BILL-08 (`_tier_and_pricing`) refuse un
modèle `requires_opt_in` sans `opt_in=True`, et `opt_in=True` n'est transmis que
sur consentement accepté. Les chaînes de repli (`fallback_chain`) ne mènent à
Opus dans aucun profil (lu dans `llm_routing.yaml`) ; un repli vers Opus serait
de toute façon refusé à la réservation.

    grep -rnE "^\s*(from anthropic|import anthropic)" app agents
    → llm_router_service.py:32, salesforce_solution_architect.py:796, salesforce_research_analyst.py:890

Les deux derniers sont un repli préexistant (SDK direct si l'import de
`llm_service` échoue), modèle `ANTHROPIC_FALLBACK_MODEL`, Sonnet 4.5 par défaut :
hors routeur, donc hors consentement **et** hors crédits. Non modifié par le lot ;
je n'ai pas lu le `.env` de production (interdit), donc la valeur réelle de
cette variable n'est pas vérifiée.

### 3.2 Tableau

| Chemin | Protégé ? | Preuve |
|---|---|---|
| Worker / orchestrateur → agents → `generate_llm_response(agent_type="architect", execution_id=…)` | **protégé** ; sans consentement : Sonnet + `avis_repli` + `degraded` ; avec : Opus | **exécuté** (sonde S3) : `S3[None] transport ['anthropic/claude-sonnet'] … avis claude-opus-5 non servi (aucun consentement enregistré pour cette exécution) : architect est servi par claude-sonnet-5. \| degraded ['opus_repli_sonnet']` ; `S3[accepte] transport ['anthropic/claude-opus'] … degraded []` |
| Palier Pro, routeur direct | protégé | tests GL-22 §1 (verts à HEAD, rouges au parent) |
| Consentement d'un **autre compte** sur la même exécution | protégé | **exécuté** (S4) : `S4 transport ['anthropic/claude-sonnet'] \| degraded ['opus_repli_sonnet']` — pas de test dans la branche |
| Reprise / retry d'exécution | protégé (même `execution_id`, cumul des charges Opus compté) | lu : seules deux créations d'`Execution(` existent (`execution_routes.py:148`, `agent_executor.py:281`) ; reprise et retry réutilisent l'exécution |
| Palier Team | protégé ; le plafond calculé pour Marcus est consommé par tout agent routé sur Opus | lu ; dit par le rapport §3.2 |
| Dialogue Studio (`/api/studio/chat`) | protégé, repli **annoncé** au client (`avis_repli`) | tests a8d06ff |
| Chat d'exécution HITL (`/api/pm-orchestrator/executions/{id}/chat`) + classification de demande de changement | protégé (jamais Opus) mais repli **seulement journalisé** : ni `avis_repli`, ni `degraded` (la route ne passe pas `execution_id`) | **exécuté** (S2, Pro avec consentement accepté) : `S2[marcus] status 200 \| transport ['anthropic/claude-sonnet', 'anthropic/claude-sonnet'] \| degraded [] \| cles reponse ['agent_id', 'agent_name', 'change_request', 'response']` ; journal `[CONSENTEMENT-OPUS] repli annonce — execution=None user=1 : … architect est servi par claude-sonnet-5`. **Déclaré ouvert par le rapport §4.** |
| Chat projet (`SophieChatService`), palier Team | protégé, repli seulement journalisé | **exécuté** (S5) : `S5 transport ['anthropic/claude-sonnet'] \| cles ['context_used', 'message', 'model_used', 'success', 'tokens_used']`. **Non mentionné par le rapport** (R4). Pro : Sophie est sur Sonnet par palier, pas de repli. |
| `sds_section_writer` (asynchrone, sans `execution_id`) | protégé (repli `sans_execution`) ; pour Team, repli non marqué sur l'exécution | lu |
| Agent-tester | routes non montées (`main.py:153` commenté) ; s'il l'était, `agent_executor` crée une exécution sans consentement → repli | lu |
| Concierge public (`sans_compte=True`) | `_appliquer_consentement_opus` **sort tout de suite** pour `sans_compte` (et la réservation aussi) ; aujourd'hui sans risque car `force_provider="anthropic/claude-sonnet"` | lu (`llm_router_service.py:1177`, `sophie_concierge_service.py:52`) — remarque, pas un utilisateur Pro |

Sondes : fichier temporaire non suivi `backend/tests/test_zz_testeurc_sonde_temporaire.py`
(copie conservée dans `/root/.dh_orch_vague2/testeur-C/sonde_temporaire.py`),
`7 passed`, supprimé ensuite ; journal `testeur-C-sondes.log`.

Conclusion GL-22 : **aucun chemin ne sert Opus à un Pro sans consentement
accepté pour cette exécution, ce compte, ce montant** (exécuté sur les chemins
routeur, agents/worker, Studio, HITL, chat projet). Condition : la migration
023c doit être appliquée — à `requires_opt_in = false` le contrôle négatif
`test_controle_negatif_opus_sans_opt_in_en_base_reste_servi` montre qu'Opus est
servi sans écran (choix assumé, dit au rapport §3.5).

### 3.3 Trace

Colonnes : `user_id`, `execution_id`, `created_at` (date), `decision`,
`credits_estimes`, `texte_version`, `model_name` (lu dans le modèle, vérifié à
l'inspecteur §3.4). Deux écarts : sur un **refus**, `credits_estimes` vaut 0 —
le montant affiché et refusé n'est pas tracé (`enregistrer_decision` :
`credits_estimes=estimation.credits_estimes if decision == DECISION_ACCEPTE else 0`) (R5) ;
`texte_version` est la constante du serveur, pas la version reçue du client (R3).

### 3.4 Migration 023c — Alembic réel sur base jetable

Script `/root/.dh_orch_vague2/testeur-C/migration_023c.py` (base
`digital_humans_test_testeurc_mig023c` dérivée de `TEST_DATABASE_URL`, rôle du
gabarit, garde `hermetic.assert_not_production_database`, détruite à la fin) ;
schéma posé par `create_all` **sans** `opus_consents`, ligne `claude-opus-5`
à `requires_opt_in=false` (état 016). Journal `testeur-C-migration.log` :

    base vue par app.config : digital_humans_test_testeurc_mig023c
    $ alembic heads -> rc=0
    023c_consentement_opus (head)
    [avant upgrade (etat 016 : opt-in false)] table opus_consents=False requires_opt_in(claude-opus-5)=False
    $ alembic upgrade head -> rc=0 … Running upgrade 022_sec12_chat_logs_reclamation -> 023c_consentement_opus
    [apres upgrade head] table opus_consents=True requires_opt_in(claude-opus-5)=True
       fk [(['execution_id'], 'executions', {'ondelete': 'CASCADE'}), (['user_id'], 'users', {'ondelete': 'CASCADE'})]
       uniques [{'column_names': ['execution_id', 'model_name'], 'name': 'uq_opus_consents_execution_modele', …}]
       checks [… 'credits_estimes >= 0' …, … decision … ANY (ARRAY['accepte'…, 'refuse'…]) …]
    $ alembic upgrade head -> rc=0            (rejeu : no-op)
    $ alembic downgrade 022_sec12_chat_logs_reclamation -> rc=0
    [apres downgrade 022] table opus_consents=False requires_opt_in(claude-opus-5)=False
    $ alembic upgrade head -> rc=0
    [apres re-upgrade] table opus_consents=True requires_opt_in(claude-opus-5)=True
    base jetable detruite : digital_humans_test_testeurc_mig023c
    EXIT=0

Mon insertion de contrôle d'une décision invalide n'a pas abouti pour une
raison de préparation (`users.is_active` NOT NULL) : la contrainte CHECK est
constatée à l'inspecteur, pas par un refus d'insertion. Non vérifié :
`alembic upgrade head` depuis une base vide (non demandé ; le rapport le dit aussi).

### 3.5 Écran de consentement (frontend)

Pas de navigateur. **Rendu serveur exécuté** du vrai composant
(`OpusConsentDialog` + `LangProvider` du worktree, bundle esbuild, `react-dom/server`,
script `testeur-C/rendu-dialog/entree.tsx`) :

    --- fr stale=false role=dialog:true boutons=3
     | Marcus avec Opus ? | … au prix de 6 720 crédits au plus pour cette exécution (7 appels au plus, 960 crédits chacun au plus). Ce montant est un plafond … Votre accord ne vaut que pour cette exécution. | Accepter Opus — 6 720 crédits au plus | Refuser — Marcus utilisera Sonnet | Avec Sonnet : 1 344 crédits au plus. … | Annuler |
    --- fr stale=true … | L’estimation a changé depuis l’affichage : voici le nouveau montant. | …
    --- en stale=false role=dialog:true boutons=3
     | Marcus on Opus? | … for at most 6,720 credits for this run … | Accept Opus — up to 6,720 credits | Decline — Marcus will use Sonnet | …

Le rendu et le texte sont vérifiés ; **les interactions (clics, enchaînement
409 → écran → relance) ne le sont pas** (lu dans `ExecutionPage.tsx` et
`ProjectWizard.tsx`). Le rapport dit « non vérifié en navigateur » : exact.

## 4. Points d'attention (b) à (f)

**(b) Langue.** Le rapport classe bien la réponse d'un modèle réel en « attend
une décision de Sam » et dit que seule la consigne est prouvée. Tests EN
(`test_question_en_anglais…`, chat projet EN) et FR existent, plus le contrôle
négatif « question FR, interface EN → français ». L'affirmation « consigne
ajoutée … exécution/HITL » n'a pas de test dans la branche ; **je l'ai exécutée**
(S1) : `S1 status 200 | consigne EN: True | FR impose: False`.

**(c) GL-26.** Les deux affirmations sont vérifiées par exécution : (1)
hypothèse du backlog infirmée — les 11 `test_chaque_agent_recoit_son_prompt_systeme[...]`
passent avec le code du parent `b14086f^` ; (2) cause dans l'historique de
`/api/studio/chat` — au parent, le prompt d'Olivia contient
`Olivia: En tant que Project Manager senior, je cadre le projet.` Le chat HITL
filtre l'historique par agent (`hitl_routes.py`, lu) : pas le même défaut. Le
lien avec la mesure du 17/09 reste non prouvé, et le rapport le dit.

**(d) GL-12.** Mesuré avec l'extracteur du test, sur chaque révision (`git show`) :

    e6f939f textes en dur = 575 {… solution_design 124, sds_shell 105, data_migration 57, test_strategy 57 …}
    6b8c22a^ textes en dur = 575
    HEAD textes en dur = 0 {}
    HEAD : appels _() = 574 ; cles distinctes = 479
    CATALOGUE_FR entrees = 479

(« 479 textes fixes » du rapport = clés distinctes.) Catalogue strict : `_`
lève `TraductionManquante` hors catalogue (test vert, rouge sans le module).
Phrase « false positives » : absente des gabarits à HEAD ; seule occurrence
restante dans le dépôt hors docs = `docs/sds/templates/_reference_logifleet_146.html`,
référence figée non servie (lu : `docs/sds/STATUS.md:453`). Rendu SDS
**anglais** exécuté : `<html lang="en">`, « Contents », « Project Overview »,
« October 2026 » présents, aucune chaîne française hors nom du projet témoin.
Rendu français : 1 600 mots visibles, aucun mot-outil anglais résiduel
significatif (comptage `testeur-C/rendu_gl12.py`). `build_sds` lit
`project.language` (`collect_sds.py:145`), stocké en code (`fr` par défaut,
`models/project.py:56`). Remarque : une langue de projet hors fr/en (ex. `de`)
est rendue en anglais avec un WARNING au journal seulement.
`e6f939f` (sommaire latéral) : **justifié** — 23 compteurs de l'exécution 146
affichés pour toute exécution, même fichier que GL-12, commit séparé, test rouge
au parent (vérifié).

**(e) CAL-08.** Le jeu de l'implémenteur, rejoué par moi
(`testeur-C/compte_cal08_testeur.py`, code du parent extrait par `git show 388299a:`) :

    [implementeur] avant: manques=19 faux_positifs=14 vrais_retenus=5/5 score=11.8
    [implementeur] apres: manques=5 faux_positifs=0 vrais_retenus=5/5 score=60.0

Chiffres confirmés. Mais le jeu est taillé sur les exemples du backlog (chaque
variante a son entrée de lexique) et ses contrôles négatifs ne couvrent pas
l'inclusion d'ensembles de mots. Jeu de contrôles négatifs **réels** construit
par moi (objet parent/enfant ou voisin présent, objet demandé absent) :

    [testeur-negatifs] avant: manques=6 faux_positifs=0 vrais_retenus=6/6 score=0.0
    [testeur-negatifs] apres: manques=0 faux_positifs=0 vrais_retenus=0/6 score=100.0
      renommes=['credit_note_line__c->avoir__c', 'loyalty_program__c->loyalty_program_member__c',
                'opportunity->opportunity_product__c', 'servicecontract->contract']

et `Price Rule`, `Quote Template` (objets CPQ cités sans `__c`) classés
métadonnées (`NON_OBJET`, sonde `testeur-C/sonde_cal08.py`). Flow/Report/Queue
ne sont jamais classés « objet manquant » : vérifié (10 tests paramétrés, rouges
au parent). Les renommages (`data_model.renamed`) ne sont lus par aucun
gabarit ni par `collect_sds.py` :

    grep -rn "renamed\|non_objects" docs/sds/templates tools/lib/collect_sds.py backend/app backend/agents
    → backend/agents/roles/salesforce_research_analyst.py:313, :314 (écriture seulement)

**(f)** `test_vague1_d_gl19_mentions_ia.py` : assertions inchangées (diff = 6
lignes d'installation de l'i18n). Vérifié aussi par exécution (§2).

## 5. Fichiers hors zone et recouvrements

Hors des zones C (`services/llm*`, `agents/*`, prompts, `frontend/src/*`), tous
justifiés par une ligne de la mission et listés au §5 du rapport :
`api/routes/orchestrator/execution_routes.py`, `api/routes/studio_chat.py`,
`api/routes/hitl_routes.py`, `services/sophie_chat_service.py`,
`models/__init__.py`, `models/consentement_opus.py`, `alembic/versions/023c_…`,
`schemas/execution.py`, `services/consentement_opus_service.py`,
`services/langue_reponse.py`, `services/rapprochement_objets.py`,
`tools/build_sds.py`, `tools/lib/sds_i18n.py`, `docs/sds/templates/**`,
`tests/test_vague1_d_gl19_mentions_ia.py`. Non touchés (vérifié dans
`git diff --stat`) : `main.py`, `config.py`, `requirements.txt`,
`credit_service.py`, `tests/conftest.py`, `frontend/package.json`.

Recouvrements réels avec les branches poussées (`git diff --name-only 388299a origin/claude/vague2-{a,b}`,
puis `git merge-tree --write-tree`) :

    C ∩ A (c9373fc) : backend/app/models/__init__.py → CONFLICT (content): Merge conflict in backend/app/models/__init__.py
    C ∩ B (c74a817) : execution_routes.py, studio_chat.py → fusion textuelle sans conflit
    A : backend/alembic/versions/023a_rgpd03_effacements_comptes.py ; C : 023c_consentement_opus.py
        → deux têtes Alembic depuis 022 : migration de fusion nécessaire

Hook de déploiement (rapport §6.1) vérifié en lecture seule :
`find /var/www/digital-humans.fr/docs/refonte -newermt '2026-10-24 12:00'` → rien ;
`index.html` daté `2026-04-28 11:18:42` ; `/tmp/dh_post_commit_build.log` :
`lib.collect.BuildError: backend/.env introuvable : /root/workspace/wt-vague2-c/backend/.env`.

## 6. Reprises

**R1 — CAL-08 masque de vrais manques (bloquante).**
Fichier : `backend/app/services/rapprochement_objets.py` (`_concepts_compatibles`, `est_metadonnee`).
Défaut : l'inclusion est acceptée sans condition dès que le plus petit ensemble
a deux mots, et pour un mot dès que le mot en plus n'est pas un « marqueur
enfant ». Un objet enfant ou voisin présent fait passer l'objet demandé pour
« renommé », donc couvert. Le principe écrit dans la docstring (« `Order`
n'est pas `Order_Line__c` ») n'est pas tenu pour `Credit_Note_Line__c` ↔ `Avoir__c`.
Preuve : `[testeur-negatifs] avant … vrais_retenus=6/6 score=0.0` → `apres … vrais_retenus=0/6 score=100.0`
(§4 e). Le suffixe « rule »/« template » classe aussi `Price Rule` et
`Quote Template` (objets CPQ) en métadonnées.
Attendu : ajouter ces six cas aux contrôles négatifs (rouges d'abord), puis
appliquer les marqueurs enfant aussi à l'inclusion de deux mots ou plus (ou
n'accepter que l'égalité des concepts, nom d'API ou libellé), et ne classer en
métadonnée par suffixe que des types connus. Remesurer les deux jeux.

**R2 — CAL-08 : « renommages restitués … pour être relus » sans lecteur.**
Fichiers : `agents/roles/salesforce_research_analyst.py:313`, gabarits SDS, `tools/lib/collect_sds.py`.
Défaut : `renamed` et `non_objects` sont écrits dans le JSON de couverture mais
rien ne les affiche ni ne les transmet à Emma : pour le lecteur du SDS, un
rapprochement (juste ou faux, cf. R1) est invisible. Preuve : le `grep` du §4 e
ne trouve que l'écriture. Attendu : rendre les renommages dans la section
couverture (ou corriger l'affirmation du rapport).

**R3 — GL-22 : le test de version du texte ne prouve pas ce qu'il annonce.**
Fichiers : `frontend/tests/opusConsent.test.ts` (dernier test « texte »),
`backend/app/services/consentement_opus_service.py` (`TEXTE_VERSION`),
`execution_routes.py` / `schemas/execution.py`.
Défaut : commentaire « La version affichée est celle que le backend trace » ;
assertion `assert.equal(OPUS_CONSENT_TEXT_VERSION, estimation.texte_version)` où
`estimation` est un littéral du test (`texte_version: 'gl22-v1-20261024'`). Le
client n'envoie pas la version qu'il a affichée ; le serveur trace sa propre
constante. Un changement du texte frontend sans changement backend passe tous
les tests et la trace ment sur « ce qui a été lu ». Preuve : lecture des deux
fichiers et du corps construit par `buildStartBody` (pas de champ de version,
test « accepter envoie le montant affiché »).
Attendu : le client envoie `texte_version` avec la décision ; le serveur
refuse (409) une version différente de la sienne, ou trace celle reçue ; test
rouge d'abord.

**R4 — GL-22 : repli seulement journalisé sur le chat projet, non déclaré.**
Fichiers : `backend/app/services/sophie_chat_service.py` (retour de `chat`),
`docs/missions/RAPPORT_VAGUE2_C.md` §4.
Défaut : pour un compte Team, Sophie (routée sur Opus) passe sur Sonnet sans
`avis_repli` dans la réponse ni marque. Preuve S5 (§3.2). Le cas HITL,
identique, est déclaré ouvert ; celui-ci ne l'est pas. Le message de journal dit
`repli annonce` alors que rien n'est montré au client.
Attendu : au minimum l'ajouter au rapport (ouvert, avec le HITL) ; idéalement
rendre `avis_repli` sur les deux routes.

**R5 — GL-22 : le montant refusé n'est pas tracé.**
Fichier : `backend/app/services/consentement_opus_service.py` (`enregistrer_decision`).
Défaut : la mission demande la trace « utilisateur, exécution, date, montant » ;
pour un refus, `credits_estimes = 0` (la colonne sert de plafond). On ne sait
plus quel montant a été présenté et refusé. Preuve : lecture ; le test
`test_lancement_refuse_trace_et_annonce_le_repli` ne vérifie pas de montant.
Attendu : une colonne « montant affiché » distincte du plafond (ou décision de
Sam consignée au rapport).

### Remarques (non bloquantes, à arbitrer)

- `opus_consents` en `ON DELETE CASCADE` sur l'utilisateur **et** sur
  l'exécution (vérifié §3.4) : supprimer une exécution efface la preuve du
  consentement alors que les transactions de crédits restent. Choix à confirmer par Sam.
- Le contrôle de plafond (`verifier_pour_appel`) et la réservation ne sont pas
  atomiques : deux appels Opus parallèles d'une même exécution peuvent dépasser
  le montant accepté d'un appel (lu, non exécuté).
- `sans_compte=True` court-circuite le contrôle de consentement ; sans risque
  aujourd'hui (concierge forcé sur Sonnet), mais aucune garde ne l'empêche si un
  futur appelant `sans_compte` route sur Opus.
- Le consentement est par (exécution, modèle), pas par agent : en cas d'échec
  de résolution du palier (`_resolve_tier_for_execution` rend `None`), Sophie,
  Olivia et Emma seraient routées sur Opus et consommeraient le plafond accepté
  pour « Marcus » (lu).

## 7. État final du worktree

Avant le commit de cette revue :

    git status --short   → (vide)
    git rev-parse HEAD   → c37e6aa5fdbbf70257105c0b63ec6827a5de24f4

Seul fichier commité : `docs/missions/REVUE_VAGUE2_C.md` (commit fait avec
`git -c core.hooksPath=/dev/null commit`, non poussé).
