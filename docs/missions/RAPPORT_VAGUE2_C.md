# Rapport — Vague 2 / File C — Produit Pro (consentement Opus, qualité agents)

Implémenteur : impl-C (Claude Code) · Worktree `/root/workspace/wt-vague2-c` ·
branche `claude/vague2-c`, partie de `origin/claude/vague-c-20260906` (`388299a`) ·
rédigé le 24/10/2026.

Discipline : « vérifié » = exécuté et sortie constatée ; sinon « lu, non exécuté ».
Aucun appel à un modèle payant, aucune requête de génération vers le Spark
(`127.0.0.1:18084`) ni `18110`, aucune alerte réelle, aucune lecture de
`digital_humans_db`. Toutes les preuves backend tournent sur la base de test
hermétique (`TEST_DATABASE_URL` de `/root/.dh_test_db.env`, `DH_ENV_FILE=backend/.env.test`).

## 0. Suite de tests — avant / après (mesurées dans ce worktree)

Commande (depuis `backend/`, venv du worktree, Python 3.12.3) :

    set -a; . /root/.dh_test_db.env; set +a
    export DH_ENV_FILE=$PWD/.env.test DH_TEST_RUN_ID=<id>
    ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider -rfE

| Mesure | Commit | Journal | Résultat |
|---|---|---|---|
| Avant | `388299a` | `/root/.dh_orch_vague2/impl-c-avant.log` | `31 failed, 1052 passed, 2 skipped, 7 xfailed, 1464 warnings in 744.08s` |
| Après | ``6b8c22a` (arbre identique à `f3e42de`, message seul amendé pendant la mesure)` | `/root/.dh_orch_vague2/impl-c-apres.log` | `31 failed, 1132 passed, 2 skipped, 7 xfailed, 1490 warnings in 807.60s (0:13:27)` |

Avant = référence de l'orchestrateur (31 échecs : 27 `test_lot_c_injection_commandes.py`,
3 `test_auth.py`, 1 `test_emma_phase3.py::TestWBSAfterValidation::test_wbs_requires_validation_success`),
re-mesurée ici à l'identique. Après : **les mêmes 31 échecs**, nom par nom
(`diff` des listes `FAILED` avant/après : identiques — fichiers
`/root/.dh_orch_vague2/implc/echecs-avant.txt` et `echecs-apres.txt`). +80
passés = les 80 tests ajoutés par ce lot (GL-22 17, langue/persona 19, CAL-08
23, GL-12 21). Aucun `skip`/`xfail` ajouté.

Frontend (`frontend/`, `npm ci` dans le worktree, `package.json` non modifié) :

    node --experimental-strip-types --test tests/*.test.ts   →  # tests 67 / # pass 67 / # fail 0
    ./node_modules/.bin/tsc -b                               →  code de sortie 0

Journal : `/root/.dh_orch_vague2/impl-c-front.log`. Suite frontend complète non
relancée au commit parent : 61 = 67 − 6 tests ajoutés (`tests/opusConsent.test.ts`)
est une déduction, aucun autre fichier de test frontend n'ayant été modifié.

## 1. Commits (`git log --oneline origin/claude/vague-c-20260906..HEAD`)

    6b8c22a GL-12 : gabarit SDS bilingue selon la langue du projet, excuse interne retirée
    e6f939f SDS : le sommaire latéral n'affiche plus les compteurs figés de l'exécution 146
    a4d43f0 CAL-08 : Emma rapproche les objets par sens avant de déclarer un manque ; une métadonnée n'est jamais un objet manquant
    a8d06ff GL-22 : hors exécution, le repli Opus → Sonnet est dit au client du dialogue Studio
    b14086f Langue des agents et GL-26 : la réponse suit la langue de la question, l'historique dit qui a parlé
    47a5f87 GL-22 : écran de consentement Opus avant le lancement, repli affiché sur le suivi
    640f938 GL-22 : consentement Opus par exécution, au montant affiché, repli annoncé sur Sonnet

(+ le commit de ce rapport.) Branche poussée : `git push -u origin claude/vague2-c` → `* [new branch] claude/vague2-c -> claude/vague2-c`.

## 2. Constats de la mission

### GL-22 — consentement Opus — **fait** (choix à confirmer par Sam, §5)

Constat re-mesuré (lu, puis exécuté) : `model_pricing.requires_opt_in` de
`claude-opus-5` posé à `false` par la migration 016 « faute de mécanisme de
recueil » ; `CreditService._tier_and_pricing` sait refuser sans opt-in, mais
`LLMRouterService._credit_reserve` ne transmettait jamais `opt_in`. Au commit
parent, avec la colonne à `true`, Marcus Pro levait :

    E   app.services.credit_service.ModelNotAllowedError: Model 'claude-opus-5' not allowed for tier 'pro' (user 1) : le modèle 'claude-opus-5' exige un opt-in explicite (model_pricing.requires_opt_in) ; il n'a pas été donné pour cet appel

Livré :
- trace `opus_consents` (migration **`023c_consentement_opus`**, depuis la tête
  `022_sec12_chat_logs_reclamation`) : utilisateur, exécution, date
  (`created_at`), décision `accepte`/`refuse` (CHECK), montant affiché en
  crédits, version du texte de l'écran ; unicité (exécution, modèle) ; la
  migration remet `requires_opt_in = true` pour `claude-opus-5` ;
- `GET /api/pm-orchestrator/execute/opus-estimate` : coût estimé en crédits ;
- `POST /api/pm-orchestrator/execute` : 409 `consentement_opus_requis` sans
  décision, 409 `consentement_opus_montant_perime` si le montant accepté n'est
  plus l'estimation ; rien n'est créé ni enfilé ; la décision est écrite dans
  la même transaction que l'exécution ;
- routeur : avant chaque appel vers un modèle `requires_opt_in`, consentement
  accepté pour **cette** exécution, par **ce** compte, et cumul mesuré
  (charges + réservations Opus de l'exécution) + estimation de l'appel ≤
  montant accepté ; sinon repli sur `repli_sans_consentement` du profil
  (`anthropic/claude-opus` → `anthropic/claude-sonnet`), **annoncé** :
  marque `executions.degraded` (motif `opus_repli_sonnet`, rendue par
  `/progress`), WARNING au journal, `avis_repli` sur la réponse ; sans repli
  déclaré : refus (`ConsentementOpusConfigError`) ;
- écran (`frontend/src/components/OpusConsentDialog.tsx`, texte dans
  `src/lib/opusConsent.ts`) : avant le lancement depuis `ExecutionPage`, et sur
  le 409 du `ProjectWizard` ; bandeau du repli sur la page de suivi ;
  `avis_repli` affiché dans le dialogue Studio (Marcus Pro hors exécution).

Preuves exécutées :
- `tests/test_vague2_c_gl22_consentement_opus.py` au parent `388299a` :
  `13 failed, 2 passed` (les 2 verts = contrôles négatifs) — journal
  `/root/.dh_orch_vague2/implc/gl22-rouge-388299a.log` ; après `640f938` :
  `15 passed` ; non-régression ciblée crédits/BILL-01/08/09/10/11/B1/enfilage/
  BILL-06 : `111 passed` (`impl-c-cibles1.log`) ;
- avis dans le dialogue Studio : au parent `b14086f`
  `test_dialogue_studio_avec_marcus_pro_repli_sonnet_dit_au_client` échoue
  (`assert (None)`), contrôle négatif vert ; après `a8d06ff` : `46 passed`
  (GL-22 + langue + BILL-06) ;
- frontend : `tests/opusConsent.test.ts` avant le module : `ERR_MODULE_NOT_FOUND`
  (1 test, 1 fail, `implc/front-opus-rouge.log`) ; après : 6 pass ;
- migration 023c : exécutée sur la base de test via `alembic.operations`
  (upgrade → `requires_opt_in` true ; downgrade → false), test
  `test_migration_023c_pose_l_opt_in_sur_opus_et_se_defait`.

Non vérifié : rendu de l'écran dans un navigateur (pas de passage Chromium) ;
`alembic upgrade head` complet sur une base vierge (seule la migration 023c
est exécutée, isolément).

### Langue des agents — **fait** (consigne envoyée prouvée ; obéissance du modèle non prouvée)

Cause lue : les 11 prompts de chat de `config/agents_registry.yaml` finissaient
par « Réponds en français », de même que le prompt du chat projet
(`sophie_chat_service._build_system_prompt`). Correctif : langue de la
question (mots-outils, accents ; `app/services/langue_reponse.py`), à défaut
celle de l'interface (`lang` envoyé par `StudioChatPage`), sinon consigne
« langue du dernier message du client » ; consigne ajoutée au prompt système
des trois chats (Studio, projet, exécution/HITL).

Preuve (client LLM bouchonné qui capture prompt système et prompt) :
`tests/test_vague2_c_langue_persona_agents.py` au parent `47a5f87` :
`6 failed, 13 passed` (`implc/langue-rouge-parent.log`) ; après `b14086f` :
`29 passed` avec BILL-06 ; HITL/PROD-01/PROD-06/rétention/GL-19 : `33 passed`.
Tests EN (« Reply in English », pas « Réponds en français ») et FR, langue de
l'interface quand la question est illisible, contrôle négatif (question FR,
interface EN → français), chat projet EN/FR.

**Attend une décision de Sam** : prouver qu'un modèle réel répond en anglais
demande un appel réel (Nemotron sur le Spark pour le Free, ou Anthropic) —
non fait, conformément aux consignes.

### GL-26 — persona — **fait** ; hypothèse du backlog **infirmée**

L'hypothèse « le prompt système chargé ne correspond pas à l'agent demandé »
est infirmée : les 11 tests `test_chaque_agent_recoit_son_prompt_systeme[...]`
passent **au commit parent** (chaque agent reçoit « Tu es <Nom>, … », sans
l'identité d'un autre, avec son `agent_type`).

Cause trouvée (lue, puis reproduite dans le prompt construit) :
`/api/studio/chat` étiquetait **tous** les tours « assistant » de l'historique
du nom de l'agent courant. Après un échange avec Sophie, le prompt d'Olivia
contenait « Olivia: En tant que Project Manager senior… ». Le frontend
affichait de même chaque réponse sous le nom de l'agent courant. Correctif :
`StudioChatTurn.agent_id`, étiquette de l'agent réel, « Autre agent du
studio » si inconnu (ancien client) — jamais l'agent courant ;
`StudioChatPage` envoie et affiche l'agent de chaque tour. Preuve : tests
`test_l_historique_attribue_chaque_reponse_a_l_agent_qui_l_a_donnee` et
contrôle négatif, rouges au parent, verts après.

Reste : que la cause trouvée soit **celle** de la mesure du 17/09 n'est pas
prouvé (transcription réelle non disponible ; il faudrait rejouer le parcours
avec un modèle réel).

### GL-12 — gabarit SDS en français — **fait**

Re-mesure : le gabarit chargé est `docs/sds/templates/sds_shell.html.j2` +
`docs/sds/templates/partials/*.j2` (`TEMPLATES_DIR` de `tools/build_sds.py`,
appelé par Emma phase 5, `/execute/{id}/sds-html` et `sds_versions`) ;
`tools/templates/sds_shell.html.j2` (cité par le backlog) n'existe pas. La
phrase « The DATA_MODEL gaps are likely false positives… » était dans
`partials/coverage_report.html.j2`.

Livré : 479 textes fixes passent par `{{ _("…") }}` ; catalogue français
strict dans `tools/lib/sds_i18n.py` (`TraductionManquante` si une phrase n'a
pas sa traduction), valeurs de données (verdict, catégories, sévérité) via
`_v`, mois en français, sommaire/statut/héros du contexte traduits ;
`build_sds` installe la langue du projet ; phrase d'excuse supprimée.
Trois affirmations fausses du gabarit corrigées au passage : « This is a
greenfield project » écrit pour tout projet ; « Threshold for APPROVED is
typically 80% » alors que le code approuve à 95 % ; « persisted in
PostgreSQL » (outil interne). Défaut distinct trouvé et corrigé dans un
commit séparé (`e6f939f`) : le sommaire latéral affichait 23 compteurs figés
de l'exécution 146 (« (25 BRs) », « (17) », « (83) »…) pour toute exécution.

Preuves : au parent `e6f939f` (gabarits, `build_sds` et test GL-19 du parent,
sans `sds_i18n.py`) : `20 failed, 11 passed`, **575 textes en dur** comptés
(shell 105, solution_design 124, data_migration 57, test_strategy 57, cicd 48,
training 42, gap 35, coverage 24, uc_digest 23, BR 20, overview 15, use_cases
15, as_is 10) et « false positives » présent (`implc/gl12-rouge-e6f939f.log`) ;
après : `31 passed`. Rendu réel du shell + 12 partials (données vides
parcourables) : en français, aucun des 256 textes fixes longs en anglais ; le
même rendu en anglais en fait apparaître ≥ 200 (contrôle que le rendu exerce
les partials). Sommaire latéral : rouge au parent `a4d43f0` (23 compteurs),
vert après.

Écart à signaler : `tests/test_vague1_d_gl19_mentions_ia.py` (test existant)
est modifié — il installe la même i18n que `build_sds` avant de rendre le vrai
shell ; ses assertions sont inchangées.

Reste ouvert : rendu d'un SDS réel depuis une base (la base de test n'a pas
de livrables) ; les nombres ne sont pas localisés (« 92.5 » en français) ; la
mention IA française de référence (`ai_disclosure.MENTION_IA["fr"]`) est sans
accents et reprise telle quelle (test d'égalité).

### CAL-08 — Emma et les variantes terminologiques — **fait sur jeu construit** ; rejeu du brief 117 **attend une décision de Sam**

Cause lue : `calculate_coverage_score` comparait les noms en minuscules, à
l'identique (`missing = uc_objects - sd_objects`) ; `SF_INFRA_OBJECTS`
n'était appliqué qu'au score, jamais à la liste des manques.

Correctif : `app/services/rapprochement_objets.py` — métadonnées (Flow,
Report, Queue, Dashboard, List View, Email Template, Approval Process…)
jamais classées en objets manquants (`non_objects`) ; identité ;
normalisation ; sens (lexique FR→EN, nom d'API et libellé, inclusion
contrôlée : `Order` ≠ `Order_Line__c`) ; renommages restitués
(`data_model.renamed`), distincts des manques.

> **Corrigé après revue 1 (R1, R2).** La règle d'inclusion ci-dessus était
> trop large : des objets absents passaient pour renommés (6 vrais manques du
> testeur : 0/6 retenus, score 100). Elle est restreinte (`1ec18a0`) ; et
> « restitués » n'était vrai qu'à l'écriture : aucun lecteur avant `e820382`.
> Chiffres à jour : §7.

Preuves : `tests/test_vague2_c_cal08_rapprochement_objets.py` au parent
`a8d06ff` : `18 failed, 5 passed` (les 5 verts = contrôles négatifs « un vrai
manque reste un manque ») ; après : `23 passed` ; CAL-09 inchangé (4 passés).
Comptage sur le jeu construit (6 variantes dont `credit_note__c` ↔ `Avoir__c`,
`actif__c` ↔ `Asset`, `mouvement_points__c`, `ligne_retour_ecommerce__c` ;
10 métadonnées ; 5 vrais manques), même conception :

    avant (388299a): manques=19 dont faux positifs=14 vrais manques retenus=5/5 score_objets=11.8
    apres: manques=5 dont faux positifs=0 vrais manques retenus=5/5 score_objets=60.0

**Ces chiffres « après » valaient pour `a4d43f0` et ne tiennent plus** : voir
§7 R1 (après reprise, sur ce même jeu : 7 manques, dont 2 renommages
désormais refusés volontairement).

(script `/root/.dh_orch_vague2/implc/compte_cal08.py` ; dans ce jeu combiné,
`credit_note__c` et `Avoir__c` sont tous deux présents dans la conception,
d'où 14 et non 16 faux positifs ; les cas croisés sont prouvés un par un par
les tests paramétrés.)

Rejeu du brief 117 (Omnichannel Loop, exécution 175) : **pas fait**. Aucune
sortie enregistrée de la revue d'Emma n'existe dans le dépôt ni dans
`/root/workspace/site-work/sds-calibration` (vérifié : `grep -rl credit_note__c`
ne trouve que le backlog et la mission ; le README de calibration n'a pas de
ligne remplie pour 175) ; les livrables sont dans `digital_humans_db`,
interdite. Le rejeu demande des appels réels (Olivia, Marcus, Emma) :
**attend une décision de Sam** (coût).

Non fait (hors texte de mission, proposé) : volet (2) du backlog — règle de
nommage dans les prompts de Marcus/Olivia (« réutiliser l'objet standard ou
existant ; un objet custom se justifie et se nomme en anglais API »).
Reste ouvert : le rapprochement des **automatisations** (noms de flows) est
inchangé — le test CAL-09 `test_la_composante_automation_tombe_sur_un_ecart_de_nom`
le constate toujours.

## 3. Attend une décision de Sam

1. **GL-22, choix pris « au plus prudent » faute de règle écrite** :
   portée = une exécution (ni le chat, ni la durée) ; montant = plafond ;
   formule = 7 appels Marcus au plus (as_is 1 + design 2 + gap 1 + wbs 1 +
   2 révisions, lu dans `pm_orchestrator_service_v2`, non mesuré) × estimation
   BILL-01 d'un appel (`max_tokens` 32 000 en entrée et en sortie) =
   **6 720 crédits** pour Opus, 1 344 avec Sonnet (sur 15 000 crédits/mois
   Pro). C'est une borne haute, pas une moyenne : elle peut effrayer ; la
   baisser suppose une mesure réelle. Texte de l'écran : version
   `gl22-v1-20261024` (`frontend/src/lib/opusConsent.ts`).
2. Palier **Team** (non ouvert) : sous le profil `cloud`, Team route Sophie,
   Olivia, Emma **et** Marcus sur Opus ; le plafond n'est calculé que pour
   Marcus, les autres agents le consomment aussi et passeront vite sur Sonnet
   (annoncé). À revoir avant d'ouvrir Team.
3. Preuve « modèle réel » de la langue et de GL-26 : un appel réel par cas.
4. Rejeu du brief 117 pour CAL-08 : appels réels Olivia/Marcus/Emma.
5. **Ordre de déploiement** : la migration `023c` remet l'opt-in d'Opus à
   `true` ; sans le code de ce lot, tout appel Opus serait refusé
   (`ModelNotAllowedError`). Code et migration ensemble. Une exécution lancée
   avant le déploiement (ou reprise ensuite) n'a pas de ligne de consentement :
   Marcus y passe sur Sonnet, annoncé sur l'exécution (lu dans le code, testé
   par `test_sans_consentement_marcus_passe_sur_sonnet_et_le_repli_est_annonce`).

6. Remarques de la revue 1, non codées, à arbitrer :
   - `opus_consents` est en `ON DELETE CASCADE` sur l'utilisateur **et** sur
     l'exécution : supprimer une exécution efface la preuve du consentement,
     alors que les transactions de crédits restent ;
   - le contrôle du plafond (`verifier_pour_appel`) et la réservation ne sont
     pas atomiques : deux appels Opus parallèles d'une même exécution peuvent
     dépasser le montant accepté d'un appel (lu, non exécuté ; Marcus est
     séquentiel aujourd'hui) ;
   - le consentement porte sur (exécution, modèle), pas sur l'agent : si la
     résolution du palier échoue (`_resolve_tier_for_execution` rend `None`),
     Sophie, Olivia et Emma seraient routées sur Opus et consommeraient le
     plafond accepté pour Marcus ;
   - `sans_compte=True` court-circuite le contrôle (concierge forcé sur Sonnet
     aujourd'hui ; aucune garde si un futur appelant sans compte route sur Opus).

## 4. Reste ouvert / pas fait

- Chat d'exécution (`hitl_routes.chat_with_sophie_contextual`) : il ne passe ni
  `execution_id` ni `subscription_tier` au LLM (lu). Conséquence lue : sous le
  profil `cloud`, un Pro qui parle à Sophie y était servi par **Opus** (pas de
  surcharge de palier) ; depuis ce lot, le repli Sonnet s'applique. **Après
  revue 1 (R4, `439a66a`)** : `avis_repli` est rendu par cette route et par le
  chat projet, et affiché. Reste : pas de marque `degraded` (la route ne passe
  pas l'exécution), et `sds_section_writer` (sans `execution_id`) ne marque
  pas le repli d'un compte Team sur l'exécution (lu, revue §3.2).
- Rendu de l'écran de consentement en navigateur : non vérifié.
- CAL-08 automatisations, règle de nommage des prompts : voir §2.

## 5. Fichiers en recouvrement touchés

| Fichier | Changement |
|---|---|
| `backend/app/services/llm_router_service.py` (C) | `LLMResponse.avis_repli` ; `complete()` appelle `_appliquer_consentement_opus` avant la réservation ; `_credit_reserve(..., opt_in)` ; `_response_to_dict` rend `avis_repli`. |
| `backend/app/api/routes/orchestrator/execution_routes.py` (personne) | route `GET /execute/opus-estimate` ; dans `start_execution`, contrôle 409 avant création et écriture de la décision dans la transaction de l'exécution. Rien sur `/workers/health` (OPS-02, file B). |
| `backend/app/api/routes/studio_chat.py` (personne) | `StudioChatTurn.agent_id`, `StudioChatRequest.lang`, étiquette de l'historique, consigne de langue, `StudioChatResponse.avis_repli`. Les 502 (file B) non touchés. |
| `backend/app/services/sophie_chat_service.py` (personne) | consigne de langue ajoutée au prompt ; ligne « Réponds en français » remplacée. |
| `backend/app/models/__init__.py` + `backend/alembic/versions/023c_consentement_opus.py` | import `ConsentementOpus` ; migration **023c** depuis `022_sec12_chat_logs_reclamation`. Si la file A ajoute une `023a_…` depuis la même tête : **deux têtes Alembic à la fusion**, à réunir par une migration de fusion. |
| `frontend/src/*` (C) | voir commits `47a5f87`, `b14086f`, `a8d06ff`. `frontend/package.json` **non touché** (`npm ci` local seulement). |

Non touchés : `app/main.py`, `app/config.py`, `requirements.txt`,
`app/services/credit_service.py` (j'appelle `_resolve_pricing` et
`_credits_for_tokens`, sans les modifier), `admin_alert_service.py`,
`pm_orchestrator_service_v2.py`, `tests/conftest.py`.

Autres fichiers touchés, hors liste de recouvrement : `backend/app/schemas/execution.py`,
`backend/config/llm_routing.yaml` (`repli_sans_consentement` du profil cloud),
`backend/config/agents_registry.yaml` (11 « Réponds en français » retirés),
`backend/app/api/routes/hitl_routes.py` (consigne de langue),
`backend/agents/roles/salesforce_research_analyst.py`,
`tools/build_sds.py`, `tools/lib/sds_i18n.py`, `docs/sds/templates/**`,
`backend/tests/test_vague1_d_gl19_mentions_ia.py` (test existant, voir GL-12).
Après revue 1 : `backend/app/api/routes/project_chat.py` et
`backend/app/schemas/project_conversation.py` (`avis_repli`, R4),
`backend/app/services/rapprochement_objets.py` (R1),
`docs/sds/templates/partials/coverage_report.html.j2` (R2) ; en recouvrement :
`llm_router_service.py` (message de journal du repli, R4),
`sophie_chat_service.py` (`avis_repli`, R4), `execution_routes.py` (409
`consentement_opus_texte_perime`, R3), `alembic/versions/023c_…` (colonne
`credits_presentes`, R5).

Diff proposé hors de ma file : aucun.

## 6. Écarts aux règles, dits platement

1. **Hook git de déploiement de la doc déclenché une fois.** Mon premier
   commit (`640f938`) touchait `backend/config/llm_routing.yaml`, que le hook
   versionné `tools/git-hooks/post-commit` (`core.hooksPath`) surveille : il a
   lancé en arrière-plan `tools/build_docs.py --deploy --strict` depuis mon
   worktree, avec cible `/var/www/digital-humans.fr/docs/refonte`. L'exécution
   a échoué **avant toute écriture** (`lib.collect.BuildError: backend/.env
   introuvable : /root/workspace/wt-vague2-c/backend/.env`). Vérifié :
   `find /var/www/digital-humans.fr/docs/refonte -newermt '2026-10-24 12:00'`
   ne rend rien, `index.html` daté du 2026-04-28. Le hook a écrit dans
   `/tmp/dh_post_commit_build.log` (ajout). Tous les commits suivants sont faits
   avec `git -c core.hooksPath=/dev/null commit` (option de ligne de commande,
   aucune configuration modifiée). **À savoir pour la fusion** : tout commit
   sur le VPS qui touche `llm_routing.yaml` ou `agents_registry.yaml` relance
   ce déploiement.
2. Sondes réseau : les tests qui démarrent l'application (`client`) déclenchent
   la sonde existante `verifier_fournisseurs_locaux` (`GET /v1/models` sur
   `127.0.0.1:18084`, comme la référence). Aucune requête de génération.
3. Un premier essai de mon outil d'extraction des textes a utilisé
   `pkill -f i18n_wrap.py`, qui a tué la commande elle-même (sans effet de bord).
4. Un test existant modifié (`test_vague1_d_gl19_mentions_ia.py`), dit en §2.
5. Commande lancée hors garde par erreur : un `pytest` sans
   `TEST_DATABASE_URL` a été **refusé à la collecte** par la garde hermétique
   (attendu) ; un `python -c` d'essai a importé `app.services` hors
   environnement de test (message `SECRET_KEY not set`), sans connexion ni
   écriture.


## 7. Reprises après revue 1 (`docs/missions/REVUE_VAGUE2_C.md`, commit `efb48e4`)

Chaque reprise : test rouge au commit précédent (journal gardé), correctif,
vert. Commits faits avec `git -c core.hooksPath=/dev/null commit`.

| Reprise | Commit | Rouge (commit précédent) | Vert |
|---|---|---|---|
| **R1** CAL-08 : un objet voisin ou enfant présent faisait passer l'objet demandé pour renommé ; Price Rule / Quote Template classés métadonnées | `1ec18a0` | au `efb48e4` : `8 failed, 25 passed` — 5 voisins/enfants (`Loyalty_Program__c`, `Credit_Note_Line__c`, `ServiceContract`, `Opportunity`, `Contact`↔`Emergency_Contact__c`), `Price Rule`, `Quote Template`, jeu des six (`implc/r1-rouge-efb48e4.log`) | `39 passed` (CAL-08 + CAL-09) |
| **R2** `renamed` / `non_objects` écrits sans lecteur | `e820382` | au `1ec18a0` : `2 failed, 22 passed` (rendu FR et EN du rapport de couverture) (`implc/r2-rouge-1ec18a0.log`) | `34 passed` (GL-12 + GL-19) |
| **R3** version du texte : test contre un littéral, non envoyée, non vérifiée | `88e0249` | au `e820382` : frontend `not ok 4` (# fail 1) ; backend `test_une_decision_sans_la_version_du_texte_affiche_est_refusee[absente/autre]` : `2 failed, 18 passed` (`implc/r3-rouge-e820382.log`, `implc/r3-front-rouge-e820382.log`) | backend `20 passed` ; frontend 67/67 |
| **R5** montant refusé non tracé | `6927eb0` | au `88e0249` : `AttributeError: 'ConsentementOpus' object has no attribute 'credits_presentes'` — `2 failed, 18 passed` (`implc/r5-rouge-88e0249.log`) | `20 passed` ; migration 023c rejouée par Alembic sur base jetable : colonne `credits_presentes` présente, downgrade/re-upgrade OK, `EXIT=0` (`impl-c-migration.log`) |
| **R4** chat projet (Team) et chat d'exécution : repli non dit au client ; journal « repli annonce » mensonger | `439a66a` | au `6927eb0` : chat projet Team `{'context_used': ['project'], 'message': 'ok', 'tokens_used': 2000}` → `assert (None)` ; chat d'exécution idem — `2 failed, 1 passed` (contrôle négatif Pro vert) ; frontend `not ok 7` (`implc/r4-rouge-6927eb0.log`, `implc/r4-front-rouge-6927eb0.log`) | `60 passed` (GL-22, langue, HITL SEC-05, PROD-01, PROD-06) ; frontend 68/68 |

### R1 — règle retenue et recomptes

Égalité des concepts, ou inclusion seulement si **tous** les mots en plus
sont des qualifiants (`ecommerce`, `online`, `web`, `digital`, `sf`,
`salesforce`, `dh`, `data`, `info`, `information`) ; métadonnée par suffixe :
`flow` seulement, le reste sur liste exacte. Choix assumé : un manque à relire
vaut mieux qu'un vrai manque masqué. Conséquence sur mes propres cas initiaux,
dite platement : `mouvement_points__c` ↔ `Loyalty_Point_Transaction__c` et
`Maintenance__c` ↔ `Maintenance_Activity__c` ne sont **plus** rapprochés (un
mot de plus, non qualifiant) — ils restent des manques, désormais testés comme
tels ; les variantes positives du test sont remplacées par
`Point_Transaction__c` et `Maintenance_Record__c` (libellé « Maintenance »).

Recompte avec le script du testeur (`/root/.dh_orch_vague2/testeur-C/compte_cal08_testeur.py`,
sortie `/root/.dh_orch_vague2/implc/r1-comptes.log`) :

    [implementeur] avant: manques=19 faux_positifs=14 vrais_retenus=5/5 score=11.8
    [implementeur] apres: manques=7 faux_positifs=2 vrais_retenus=5/5 score=40.0 renommes=['actif__c->asset', 'ligne_retour_ecommerce__c->return_line__c']
    [testeur-negatifs] avant: manques=6 faux_positifs=0 vrais_retenus=6/6 score=0.0
    [testeur-negatifs] apres: manques=6 faux_positifs=0 vrais_retenus=6/6 score=0.0

Les 2 « faux positifs » restants du jeu initial sont les deux renommages
refusés ci-dessus. Sonde du testeur (`sonde_cal08.py`) : les 12 cas → `MANQUANT`.

### R2

`partials/coverage_report.html.j2` lit `coverage.by_category.data_model.renamed`
et `.non_objects` (transmis par `collect_sds.collect_coverage`) et rend un
tableau « Objets rapprochés sous un autre nom / Objects matched under another
name » et la liste des non-objets écartés. `grep` montre désormais le lecteur.

### R3

`buildStartBody` envoie `texte_version_opus` avec la décision ; le serveur
refuse (409 `consentement_opus_texte_perime`, rien créé) une version absente
ou différente et trace celle reçue. Un test backend lit la constante du
fichier frontend et la compare à celle du serveur ; l'assertion trompeuse du
test frontend est retirée.

### R4

`avis_repli` rendu par `SophieChatService.chat` / `SophieResponse` et par
`ChatResponse` (HITL), ajouté à la réponse affichée (`withFallbackNotice` :
ProjectDetailPage, ChatSidebarStudio, ChatSidebar). Le journal dit
« avis_repli rendu à l'appelant » (et « marque degraded posée » seulement avec
une exécution).

### R5

Colonne `opus_consents.credits_presentes` (montant affiché, acceptation comme
refus) ; `credits_estimes` reste le plafond accepté (0 sur un refus). Ajoutée
au modèle et à la migration 023c (non déployée, modifiée sur place).

### Suites après reprises

Backend (`DH_TEST_RUN_ID=implc_apres2`, au commit `439a66a`, journal
`/root/.dh_orch_vague2/impl-c-apres2.log`) :

    31 failed, 1153 passed, 2 skipped, 7 xfailed, 1495 warnings in 662.11s (0:11:02)

Mêmes 31 échecs que la référence, nom par nom (`diff echecs-avant.txt
echecs-apres2.txt` → identiques). +21 passés par rapport à `c37e6aa` = tests
ajoutés par les reprises (R1 12, R2 3, R3 3, R4 3). Aucun `skip`/`xfail` ajouté
(`git diff efb48e4 -- backend/tests | grep -cE "^\+.*(pytest\.mark\.(skip|xfail)|pytest\.skip)"` → 0).

Frontend (journal `/root/.dh_orch_vague2/impl-c-front2.log`) :
`# tests 68 / # pass 68 / # fail 0`, `tsc -b` → `TSC_B_EXIT=0`.

Tests existants de la branche modifiés par les reprises (les miens, dits ici) :
`test_vague2_c_cal08_rapprochement_objets.py` (deux variantes positives
remplacées, R1), `test_vague2_c_gl22_consentement_opus.py` (les lancements avec
décision envoient `texte_version_opus`, R3 ; `credits_presentes` vérifié, R5 ;
le helper `_consentir` renseigne `credits_presentes`),
`frontend/tests/opusConsent.test.ts` (corps attendu avec la version ; assertion
contre un littéral retirée, R3).

## Reprises après revue passe 2 — faites par Claude le 24/10, hors orchestration (`1616080`)

| Défaut | Rouge prouvé (tests ajoutés avant correctif) | Vert |
|---|---|---|
| D1. Report/Queue/Dashboard/Email Template/Assignment Rule **nommés** classés objets manquants | 9 tests D1 → 9 failed | 52 passed (fichier CAL-08) |
| D2. Objets de plateforme exclus du score mais restés dans `missing` | 2 tests D2 → 2 failed | idem |

Correctif D1 : suffixes de métadonnée par expressions de type connu (report, queue, dashboard, email template, assignment/escalation rule, list view…), « rule »/« template » seuls hors liste (CPQ), `__c` toujours objet. Correctif D2 : `missing` suit le filtre du score ; **Order, Contract, Campaign, CampaignMember retirés de `SF_INFRA_OBJECTS`** — objets métier ; le contrôle négatif existant « Order vs Order_Line__c » a échoué au premier essai du correctif, qui les masquait (décision à confirmer par Sam : ils comptent désormais aussi dans le score).

Jeux du testeur rejoués (`/root/.dh_orch_vague2/claude-c-jeux.py`) : vrais manques 16/16, vrais renommages 13/13, objets CPQ 5/5, **métadonnées 22/22** (13/22 avant). Suite complète : **1 170 passés** (+17), mêmes 31 échecs que la référence, comparés nom par nom.

Restent ouverts : D3 (avis de repli en français seulement, identifiants internes), D4 (montant d'un refus = estimation serveur) — décisions de Sam.
