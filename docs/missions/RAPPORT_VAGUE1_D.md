# Rapport — Vague 1 / File D — Parcours réellement vendus (AS-09 + conformité)

**Date :** 16/09/2026 · **Branche :** `claude/vague1-d`, depuis `claude/vague-c-20260906`
à `f78e8ad` (PR #11 de la vague 0 fusionnée) · **Mission :**
`docs/missions/VAGUE1_D_PARCOURS.md`.

**Environnement : un bac à sable Claude Code, pas le VPS.** Python 3.11,
PostgreSQL 16 et Redis locaux ; suite lancée avec `TEST_DATABASE_URL` sur le
rôle `dh_test` et `env -u GITHUB_TOKEN`, comme l'impose le bootstrap hermétique
de la vague 0. Le réseau sortant est refusé par le bootstrap **et** par le bac
à sable : aucun appel Stripe, LLM ou Salesforce réel n'a été joué. Rien n'a été
exécuté sur le VPS, rien n'a été redémarré, `backend/.env` n'a pas été touché.

Chaque « fait » ci-dessous est une commande jouée dont la sortie est collée.
Le reste est dit « lu, non exécuté ».

---

## 0. Mesure avant / après (règle 4)

### Backend

    cd /home/user/wt-vague1-d/backend
    export $(cat /root/.dh_test_db.env)
    env -u GITHUB_TOKEN ./venv/bin/python -m pytest tests/ -q -p no:cacheprovider

| État | Résultat |
|---|---|
| **Référence, `f78e8ad`** (mesurée par moi, pas reprise du prompt) | `31 failed, 695 passed, 2 skipped, 7 xfailed in 189.03s` |
| Intermédiaire, après 7 correctifs | `32 failed, 732 passed, 2 skipped, 7 xfailed in 221.07s` |
| **Après, `b8ecd54`** | `31 failed, 748 passed, 2 skipped, 7 xfailed in 227.14s` |

**53 tests verts ajoutés, et les 31 rouges sont exactement les mêmes.** Vérifié
par comparaison des listes `FAILED`, pas à l'œil :

    grep "^FAILED" final.log | sed 's/ - .*//' | sort > final_failed.txt
    diff <(sort ref_failed.txt) final_failed.txt
    -> aucune différence

**Écart avec le chiffre du prompt.** L'orchestrateur annonçait
`32 failed, 694 passed` sur la tête précédente `5d35156`. J'ai mesuré
`31 failed, 695 passed` sur `f78e8ad`. L'écart d'une unité est le test instable
déjà signalé par la vague 0,
`test_lot_g_db_sessions.py::test_open_websockets_do_not_pin_connections`, qui
est passé dans ma mesure de référence. Les 31 rouges sont les rouges antérieurs
connus, inchangés :

| Fichier | Rouges | Cause (lue, non corrigée — OPS-06) |
|---|---|---|
| `test_lot_c_injection_commandes.py` | 27 | routeur `agent_tester` commenté dans `app/main.py` |
| `test_auth.py` | 3 | inscription sans consentement |
| `test_emma_phase3.py` | 1 | chemin VPS en dur |

Le passage intermédiaire a fait apparaître **un rouge nouveau, de mon fait** :
`test_vague_b_b7_tiers_source_unique.py::test_pricing_tsx_pas_de_nombre_nu_non_explique`,
un garde-fou de la file B qui interdit un chiffre nu dans `Pricing.tsx`. Il
mordait sur « 503 » écrit dans un **commentaire**. Corrigé par `7b7b82b` ; le
garde-fou est bon, c'est mon commentaire qui était fautif.

### Frontend — build strict (OPS-09) et tests

    cd /home/user/wt-vague1-d/frontend && export PATH=/opt/node22/bin:$PATH
    npx tsc -b --force        # le build de `npm run build` est `tsc -b && vite build`
    npm run build
    node --experimental-strip-types --test tests/*.test.ts

| État | `tsc -b --force` | `npm run build` | tests Node |
|---|---|---|---|
| **Référence, `f78e8ad`** | **exit 0** | **exit 0**, `✓ built in 16.50s` | `# pass 22 / # fail 0` |
| **Après, `b8ecd54`** | exit 0 | exit 0, `✓ built in 20.41s` | `# pass 61 / # fail 0` |

`npm ci` est passé (le proxy du bac à sable a laissé passer le registre npm).

---

## 1. Fait, avec preuve

### 1.1 GL-19 — mentions IA dans l'application (bloquant légal)

Commits `d35c4b8` (livrables), `be43563` (Studio), `b8ecd54` (contrôle Chromium).

Mesure d'entrée, sur `f78e8ad` :

    grep -rn "IA\b|intelligence artificielle|AI-generated|article 50" \
        frontend/src docs/sds/templates backend/app/services/*generator*.py

→ **une seule ligne**, `markdown_to_docx.py:206`, « Document généré par Digital
Humans Platform » — qui ne dit pas que le contenu vient d'une IA.

- **Livrables.** `backend/app/utils/ai_disclosure.py` porte le texte FR/EN, et
  un point de sortie unique `sauvegarder_docx_avec_mention()` par lequel
  passent désormais les trois générateurs Word (`markdown_to_docx`, qui est le
  chemin du SDS depuis `pm_orchestrator_service_v2._generate_sds_document` ;
  `ProfessionalDocumentGenerator.save` ; `SDSTemplateGenerator`). La mention est
  écrite dans le corps **et** dans `core_properties` (commentaires + catégorie),
  qui survivent au copier-coller d'un extrait. Le gabarit
  `docs/sds/templates/sds_shell.html.j2` porte `<meta name="generator">`,
  `<meta name="ai-generated">` et une ligne en pied.
- **Studio.** `frontend/src/lib/aiDisclosure.ts` + `AiDisclosureBanner`, monté en
  tête des trois fenêtres de dialogue (`ChatSidebarStudio`, `ChatSidebar`,
  onglet chat de `ProjectDetailPage`), donc présent au premier contact et
  ensuite.

Preuve exécutée — rouge d'abord :

    pytest tests/test_vague1_d_gl19_mentions_ia.py
    E ModuleNotFoundError: No module named 'app.utils.ai_disclosure'

    node --experimental-strip-types --test tests/aiDisclosure.test.ts
    # Error [ERR_MODULE_NOT_FOUND]: .../src/lib/aiDisclosure.ts   -> # fail 1

puis vert : `10 passed` (backend) et `# pass 28 / # fail 0` (frontend).

**Contrôle inverse exécuté** (l'assertion mord-elle ?) : mention retirée du pied
du gabarit →

    E AssertionError: la mention IA est absente du pied du SDS HTML

restaurée → `10 passed`.

**Contrôle Chromium** (`frontend/tests/harness/`, servi en HTTP local car
Chromium refuse les modules ES en `file://`) :

    {"vue":"studio","visible":true,"texte":"You are talking to an artificial intelligence, not to a person.","y":56.25,"ecranDAccueil":1,"erreursConsole":[]}
    {"vue":"legacy","visible":true,...,"y":59,"ecranDAccueil":1,"erreursConsole":[]}
    {"vue":"banner","visible":true,...,"y":0,"ecranDAccueil":0,"erreursConsole":[]}

`ecranDAccueil: 1` = l'écran « aucun message échangé » est affiché : le bandeau
est donc bien là **au premier contact**, au-dessus du fil, sans erreur console.

Même contrôle sur le SDS HTML rendu :

    {"visible":true,"texte":"Content generated by artificial intelligence. To be reviewed and validated by a professional before any use.","meta":"Digital·Humans Studio — Content generated by...","metaIa":"true","style":{"color":"rgb(118, 113, 106)","fontSize":"9px","display":"block"}}

9 px pour une mention légalement obligatoire n'est pas « clair » au sens de
l'article 50 : porté à 11 px, couleur plus contrastée (`b8ecd54`).

### 1.2 BILL-07 — produit vendu, et abonnement Pro branché

Commits `8d93bd9`, `7b7b82b`.

Mesure d'entrée : `Pricing.tsx` lisait bien prix et crédits depuis l'API, mais
son tableau de comparaison était une constante `FEATURES` qui **contredit** la
matrice serveur :

| ligne affichée | page | serveur (`TIER_FEATURES`) |
|---|---|---|
| Free · extraction des BR, document SDS | incluses | `br_extraction`, `sds_document` = False |
| Free · projets max | 1 | `max_projects: 0` |
| Pro · BUILD, SFDX, Git | inclus | les trois = False |
| Team · projets | illimités | `max_projects: 100` |
| Team · templates personnalisés | inclus | `custom_templates: False` |

Et `formatCredits(undefined)` affichait **« Illimité »** sur erreur de
chargement.

Correctifs : `frontend/src/lib/tierFeatures.ts` (lecture pure — cle absente =
non inclus, donnée absente = « Indisponible », `max_projects: null` distinct
d'une clé absente) ; `Pricing.tsx` ne porte plus aucune promesse ; le bouton Pro
appelle `POST /api/billing/checkout` et **affiche** le motif d'un refus ; le
modal « bientôt » est supprimé ; la promesse ZDR du Free disparaît de la FAQ ;
`SignupPage` n'annonce plus « 1 projet, SDS uniquement ».

Preuve : rouge `# fail 1` (module absent) puis
`pytest tests/test_vague1_d_bill07_produit_vendu.py -> 13 passed`,
`# pass 38 / # fail 0`, `tsc -b --force` exit 0.

**« Sonnet model » sur le Free — lequel des deux j'ai aligné.**
J'ai aligné **le discours, pas le routage**, et voici pourquoi.

- La page vitrine (`apercu-recent`) n'est pas dans ce dépôt : je ne pouvais pas
  la modifier. Ce que j'ai trouvé **dans** le dépôt est le même défaut sous une
  autre forme : `TIER_FEATURES` annonçait « Modèle Haiku uniquement » au Free,
  « Modèle Opus indisponible » au Pro, « Opus en opt-in » au Team — servis au
  public par `GET /api/subscription/tiers`.
- Le routage réel du Free, profil `cloud` actif depuis le 16/09, est
  `gpu_nemotron/nemotron` (`llm_routing.yaml`, bloc `tier_overrides`). Aucune de
  ces annonces n'était donc vraie.
- Changer le routage du Free pour Sonnet est une décision commerciale et un
  coût récurrent : hors mandat de cette file.
- Nommer un modèle au client contredit par ailleurs la règle de sortie que
  porte **chaque** prompt d'agent du dépôt (`prompts/agents/sophie_pm.yaml` :
  « ne fais jamais apparaître le nom d'un modèle de langage… le client achète un
  studio, pas une chaîne d'outils »). Une annonce publique ne peut pas dire ce
  que l'agent a interdiction de dire.

J'ai donc retiré tout nom de modèle des annonces publiques, avec un test qui le
verrouille (motif sur haiku|sonnet|opus|claude|gpt|nemotron|…, plus son contrôle
négatif). **Reste à faire hors dépôt :** retirer « Sonnet model » de la page de
tarifs du site vitrine. Le routage n'a pas été touché.

### 1.3 BILL-06 — le parcours Free existe enfin

Commit `6c9ecce`. `POST /api/studio/chat` et `GET /api/studio/chat/agents` :
dialogue authentifié sans projet ni exécution, palier résolu **côté serveur**,
capacité vérifiée **avant** l'appel LLM (un refus ne se paie pas), facturation
normale (D10), aucune mémoire serveur — ce que le Free annonce
(`persistent_memory: False`) —, historique fourni par le client et borné à 10
tours. Aucun projet technique caché, ce que le rapport d'Astra excluait.
Côté Studio : page `/chat`, bannière d'accueil du Free redirigée vers elle, et
le tableau de bord demande au serveur (`can-create-project`) quelle carte
afficher.

Preuve : rouge `assert 404 == 200` (×4), puis `10 passed`.
**Contrôles négatifs et positif :** un Free qui demande Marcus reçoit 403
`chat_full_team` *sans qu'aucun appel LLM ne soit payé* ; un **Pro** obtient
Marcus (donc le refus vient du palier, pas d'une liste fermée pour tous) ; un
palier envoyé dans le corps est ignoré ; sans jeton, 401/403 ; un agent inconnu
est refusé sans appel LLM ; « tour 0 » absent du prompt et « tour 59 » présent
(historique borné).

### 1.4 BILL-11 — le refus de crédits est visible

Commit `f3614f7`. Deux volets.

- **Écran d'exécution** : `/progress` servait déjà `failure_reason` (lot
  B1-bis) ; `useExecutionStream` ne le lisait pas. Il est typé, propagé,
  comparé dans `progressChanged` (sans quoi un motif arrivant après le passage
  en `failed` était ignoré), affiché, et « Rejouer » est remplacé par « Voir les
  offres » sur un refus de crédits.
- **Analyse de CR** : `analyze_impact` attrapait `InsufficientCreditsError` dans
  un `except Exception` nu, écrivait un fallback, passait la CR en `analyzed`
  avec une estimation de coût et rendait `success: True`. Désormais `CreditError`
  est traité avant, rend `success: False` / `code: insufficient_credits` et **ne
  touche pas** à la CR ; la route rend 402 structuré et restitue `fallback_used`.

Preuve : rouge `assert True is False` et `une CR non analysee est annoncee
analysee`, puis `5 passed` (backend) et `# pass 52` (frontend).
**Contrôle négatif :** une panne de fournisseur (`RuntimeError`) garde le repli
documenté et la CR passe bien en `analyzed` — sans lui, « ne plus avaler le
refus de crédits » se confondrait avec « ne plus jamais se replier ».

### 1.5 PROD-10 — contrats frontend/API

Commit `937d45f`. Les cinq parcours : 204 traité (une suppression réussie
n'affiche plus un échec) ; erreur structurée conservée (`ApiError` porte
status/code/required_tier/upgrade_url — fini `Error("[object Object]")`) ;
la réponse de Sophie lue sous le nom réellement servi (`message`, pas
`assistant_message`) ; statut de CR lu dans la réponse (`analyzed`, pas
`submitted` forcé) ; snapshot SDS envoyant `execution_id`.

Preuve : rouge `# fail 1`, puis `# pass 52 / # fail 0`, `tsc -b --force` exit 0.

### 1.6 GL-18 — les trois compteurs sont mesurés

Commit `7722108`. Mesure d'entrée : l'écran alimentait `ExecutionMetrics` avec
`(a as any).tokens_used || 0`, `.cost || 0`, `.duration_seconds || 0` lus dans
`agent_progress` — or `build_agent_progress` ne pose **aucun** de ces trois
champs. Les trois compteurs affichaient 0 pour toute exécution, toujours.
`/executions/{id}/metrics` existait mais lisait `agent_execution_status` et
`execution.total_cost`, et l'écran ne l'appelait pas.

Correctif : la route mesure sur `llm_interactions` (jetons, temps en agent) et
`credit_transactions` (ce que le client paie) ; l'écran l'appelle et montre un
motif si la source est muette.

Preuve : rouge `KeyError: 'totals'` (×5), puis `7 passed`.
**Contrôles négatifs :** une exécution sans appel rend zéro *et le dit* ; les
appels d'une exécution voisine ne sont pas comptés (sans quoi une somme sans
filtre passerait tout) ; un tiers reçoit 403/404.

### 1.7 GL-16 — purge des conversations du Studio, durée réglable

Commit `9ac58b7`. Voir aussi § 2 (constat partiellement infirmé).

Le trou réel : `project_conversations` — les conversations Sophie que le client
tient dans le Studio — n'avait **aucune** purge par âge. Mesure :

    grep -rn "ProjectConversation" backend/app --include=*.py | grep -i "delete|purge|retention"

→ une seule ligne, la cascade `all, delete-orphan` : ces messages ne
disparaissaient que si le projet était supprimé.

Correctif : `app/services/retention_service.py`, durée lue dans
`DH_RETENTION_CONVERSATIONS_JOURS` (passer à 90 jours devient un réglage, pas un
patch), défaut aligné sur la décision la plus récente. Une durée illisible,
nulle ou négative est **refusée** : un zéro silencieux viderait la table à la
première purge. La politique de confidentialité
(`docs/marketing-site/scripts/dh-mod28-legal-content.py`) est alignée sur ce que
le code fait — la promesse « pour le palier Free, les conversations ne sont pas
conservées au-delà de la session » était fausse (RGPD-04) et disparaît.

Preuve : rouge `ModuleNotFoundError: app.services.retention_service`, puis
`8 passed`, et `tests/test_b5_retention_chat_logs.py -> 5 passed` (non-régression).
**Contrôles négatifs :** une conversation récente survit ; purger les
conversations de projet n'emporte pas les `chat_logs` du concierge ; une durée
illisible lève au lieu de se replier.

### 1.8 PROD-11 — le wizard ne promet plus ce qu'il ne fait pas

Commit `1762ab6`. **Décision : la fonction PDF est retirée, pas simulée.**
Motif mesuré, et il est décisif : `agents/roles/salesforce_pm.py` — Sophie,
celle qui extrait les BR — passe `rag_context=None` et n'interroge **jamais** le
RAG projet ; seuls Olivia, Marcus et Lucas passent `project_id` à
`get_salesforce_context`. Même téléversé, le PDF ne serait pas lu au moment où
l'écran promet qu'il l'est. Et le palier Free n'a pas `upload_documents`. Le
téléversement réel existe déjà, ailleurs et au bon moment :
`POST /api/projects/{id}/documents`, depuis la page projet.

Les trois autres pertes sont corrigées : le produit est demandé et n'est plus
déduit de l'édition (un produit inconnu devient `Platform`, pas un Cloud choisi
au hasard) ; le secteur et l'édition — qui n'ont **pas** de colonne côté serveur
(`industry` n'existe ni dans `ProjectCreate` ni dans le modèle `Project`, grep :
aucune ligne) — sont portés par le texte des exigences, que l'extraction lit,
au lieu d'être envoyés dans un champ ignoré ; les coûts fixes et l'option
« Express +20 % » disparaissent ; le wizard navigue vers le monitoring et
**affiche** un refus de démarrage au lieu de le convertir en succès de
navigation.

Preuve : rouge `# fail 1`, puis `# pass 61 / # fail 0`, `tsc -b --force` exit 0,
`npm run build` OK. Le build strict a lui-même attrapé trois imports devenus
inutiles (`TS6133` sur `Upload`, `X`, `FileText`) : le mécanisme décrit par
OPS-09 fonctionne.

---

## 2. Non confirmé — constats infirmés par la mesure

### OPS-09 — « le build frontend strict contient au moins un échec statique » : **infirmé**

Le constat visait `ChatSidebarStudio.tsx`, « `lang` n'est pas utilisé ».
Mesure sur `f78e8ad` :

    grep -n "\blang\b" frontend/src/components/studio/ChatSidebarStudio.tsx
    64:  const { t, lang } = useLang();
    190:              alt={selected.name[lang]}
    198:                {selected.name[lang]}
    305:                  alt={selected.name[lang]}
    351:              alt={selected.name[lang]}

`lang` est utilisé quatre fois. Et le build complet passe :

    npx tsc -b --force   ->  tsc --force exit=0
    npm run build        ->  ✓ built in 16.50s, build exit=0

**Contrôle négatif exécuté** — le mécanisme mord-il vraiment ? Variable inutile
introduite volontairement :

    src/components/studio/ChatSidebarStudio.tsx(65,9): error TS6133:
      'temoinInutilise' is declared but its value is never read.
    exit=2

puis retirée → exit 0. `noUnusedLocals` est bien actif et bloquant ; il n'y a
simplement aucun échec à corriger. Le constat d'Astra portait sur un arbre
antérieur ou n'a pas été compilé (l'audit le dit lui-même : « aucune
compilation n'a été exécutée »). **Rien n'a été commité pour OPS-09** — il n'y
avait rien à corriger. La valeur livrée est la mesure, plus le fait que le build
strict a servi de garde-fou trois fois pendant cette file.

### GL-16 — « `chat_log.py` ne purge pas » : **infirmé**

    pytest tests/test_b5_retention_chat_logs.py   ->  5 passed

`app/workers/retention.py` existe depuis le lot B5 du 03/09, planifié à 03:17
UTC dans `WorkerSettings.cron_jobs`. Le constat du backlog était périmé. Le
trou réel était ailleurs (§ 1.7).

### GL-16 — la durée : **contradiction de décisions humaines, non tranchée**

DEC-0813-02 et DEC-0817-04 (13 et 17 août) disent **90 jours** ; D3 (03/09,
`docs/vague-b/EXECUTION.md`) dit **12 mois**, et c'est elle qui est dans le code
(`RETENTION_JOURS = 365`). D3 est postérieure aux deux décisions que GL-16 cite.
Trancher est une décision de Sam, pas un correctif : j'ai rendu la durée
réglable et gardé la décision la plus récente par défaut. **Une ligne de
configuration suffit pour passer à 90 jours** :
`DH_RETENTION_CONVERSATIONS_JOURS=90`.

### BILL-11 — « la page utilise du polling, pas le hook SSE » : exact mais sans conséquence ici

`useExecutionStream` fait bien du polling. Ce n'est pas la cause du défaut : la
route `/progress` sert `failure_reason` aussi bien en polling qu'en SSE. Le
défaut était que personne ne lisait le champ. Corrigé sans toucher au mode de
transport.

---

## 3. Reste ouvert

1. **Le branchement du cron de purge GL-16.** `app/workers/*` est attribué à la
   **file C**. Le diff est livré, non appliqué, dans
   `docs/missions/diffs-vague1-d/GL-16-branchement-cron-file-C.diff`.
   **Tant qu'il n'est pas appliqué, `purger_conversations_projet` existe, est
   testée, et n'est appelée par aucun planificateur** — c'est exactement le
   défaut de DEC-0817-04. Je le nomme plutôt que de le taire.
2. **La mémoire persistante du dialogue hors projet (BILL-06).** Le Free est
   conforme (stateless, annoncé comme tel dans la réponse). Les paliers payants
   annoncent `persistent_memory: True` : le tenir demande une table, donc une
   migration Alembic — non faite pour ne pas créer une tête de migration
   concurrente pendant que trois autres files travaillent. À chiffrer en vague 2.
3. **« Sonnet model » sur la page de tarifs du site vitrine** : hors dépôt, à
   retirer avec le reste du contenu marketing (§ 1.2).
4. **Le Checkout Stripe n'a pas été joué**, ni en sandbox ni autrement (§ 5).
5. **Le rendu Chromium de la page `/chat` et du wizard** n'a pas été joué : ils
   demandent un backend servi et un compte authentifié. Seules les fenêtres de
   dialogue et le SDS HTML l'ont été (§ 1.1).
6. **31 rouges antérieurs** (OPS-06), non corrigés et non marqués xfail, comme
   demandé.
7. **`test_open_websockets_do_not_pin_connections`** reste instable (vague 0).

---

## 4. Non fait, et pourquoi

- **Aucune migration Alembic.** Trois autres files travaillent en parallèle ;
  une tête de migration concurrente se paie en conflit de fusion et en base
  incohérente. Conséquence assumée : point 2 du § 3.
- **Aucun fichier d'une autre file commité.** `credit*` et `stripe*` (file B),
  `pm_orchestrator_service_v2.py` et `workers/*` (file C) : non touchés. Seule
  lecture faite : `credit_transactions` est **lu** par la route de métriques
  (GL-18) et par `_helpers` ; aucun service de crédit n'est modifié.
- **Pas de `pip install`.** Le venv est partagé par les quatre agents. Aucune
  dépendance nouvelle n'a été nécessaire : `python-docx`, `jinja2`, Playwright et
  Chromium étaient déjà là. **Rien à ajouter à `requirements.txt`.**
- **Pas de test Chromium dans la suite automatisée.** Le harnais se construit et
  se joue à la main (`frontend/tests/harness/README.md`). L'intégrer à une CI
  suppose une CI — le dépôt n'en a pas.

---

## 5. Ce qui n'a pas pu être joué

| Attendu de la mission | État | Pourquoi |
|---|---|---|
| Parcours Free de bout en bout sans projet | Joué **au niveau HTTP** (10 tests, client authentifié, routes réelles, transport LLM simulé) | Aucun LLM réel joignable : réseau sortant refusé par le bootstrap **et** par le bac à sable |
| Souscription Pro en sandbox Stripe → accès ouvert | **Non joué** | Aucun appel réseau possible. Le parcours est branché côté frontend et la route `POST /api/billing/checkout` existait déjà. **À rejouer sur le VPS**, avec un Price ID de sandbox, avant l'ouverture |
| Refus de crédits visible dans l'écran réellement utilisé | Joué en tests (backend + modules frontend) | Le rendu de l'écran d'exécution en navigateur n'a pas été joué (backend servi requis) |
| Chromium : bandeau IA au premier message | **Joué** (§ 1.1) | — |
| Chromium : mention en pied de livrable | **Joué** sur le SDS HTML (§ 1.1) | Le pied du `.docx` est vérifié en relisant le fichier produit, pas dans un navigateur — un `.docx` ne s'ouvre pas dans Chromium |
| Purge 90 j testée sur une conversation antidatée | **Joué**, sur une conversation antidatée, à la durée configurée | La durée par défaut reste 12 mois : trancher 90 j est une décision humaine (§ 2) |

**Les webhooks Stripe rejoués par fixtures** n'ont pas été nécessaires : aucun
de mes correctifs ne touche `stripe_service` (file B). Ce que j'ai changé est en
amont — le bouton qui appelle le Checkout et l'affichage du refus.

---

## 6. Tableau constat par constat

| Constat | Verdict | Preuve |
|---|---|---|
| **BILL-06** L717 — Free sans parcours de dialogue | **corrigé** | `6c9ecce` · rouge `404 == 200` → `10 passed`, 5 contrôles négatifs + 1 positif |
| **BILL-07** L733 — produit vendu incorrect, Pro non branché | **corrigé** | `8d93bd9`, `7b7b82b` · `13 passed` + `# pass 38` ; Checkout branché mais non joué (§ 5) |
| **BILL-11** L807 — refus de crédits invisible | **corrigé** | `f3614f7` · `5 passed` + `# pass 52`, contrôle négatif « panne ≠ crédits » |
| **PROD-10** L526 — contrats frontend/API | **corrigé** (5/5) | `937d45f` · `# pass 52`, `tsc` exit 0 |
| **PROD-11** L546 — PDF non envoyé, informations perdues | **corrigé** — fonction PDF **retirée** | `1762ab6` · `# pass 61`, motif mesuré (`rag_context=None` chez Sophie) |
| **OPS-09** L1036 — échec statique au build strict | **infirmé** | build exit 0 sur `f78e8ad` ; `lang` utilisé 4× ; contrôle négatif TS6133 exit 2 |
| **GL-16** — `chat_log.py` ne purge pas | **infirmé** (B5 du 03/09) | `5 passed` |
| **GL-16** — conversations du Studio jamais purgées | **corrigé** (purge) + **ouvert** (branchement cron, file C) | `9ac58b7` · `8 passed` + diff non commis |
| **GL-16** — 90 j vs 12 mois | **non tranché** (décision humaine), rendu réglable | `DH_RETENTION_CONVERSATIONS_JOURS` |
| **GL-18** — trois compteurs faux | **corrigé** | `7722108` · rouge `KeyError: 'totals'` → `7 passed` |
| **GL-19** — mentions IA dans l'application | **corrigé**, vérifié en navigateur | `d35c4b8`, `be43563`, `b8ecd54` · `10 passed` + Chromium |

---

## 7. Diffs destinés à d'autres files — non commis

### 7.1 File C — `app/workers/*` : brancher la purge GL-16

Fichier : `docs/missions/diffs-vague1-d/GL-16-branchement-cron-file-C.diff`.
Ajoute `purge_conversations_projet_task` dans `app/workers/retention.py` et la
planifie à 03:23 UTC dans `WorkerSettings.cron_jobs`, à côté de la purge des
`chat_logs` du lot B5. La règle de durée reste dans
`app/services/retention_service.py` (cette file). Vérification après
application : les deux fichiers de test de rétention, 13 tests.

### 7.2 File B — `credit*` / `stripe*` : rien à appliquer, deux remarques

Aucun diff : je n'ai eu besoin d'aucune modification de ces services. Deux
constats mesurés en passant, à leur main :

1. `POST /api/billing/checkout` répond 503 quand `STRIPE_SECRET_KEY` est absente
   — comportement correct, et mon bouton l'affiche désormais au lieu de
   l'avaler. **Les Price ID Stripe (`STRIPE_PRICE_ID_PRO`) doivent être posés
   sur le VPS avant l'ouverture**, sinon `create_checkout_session` lève
   `ValueError` (400) : « Tier 'pro' is not subscribable via Stripe ».
2. `_handle_subscription_change` garde le palier payant sur `past_due` et
   `unpaid`. C'est un choix défendable (période de grâce), mais il n'est écrit
   nulle part dans les CGV. À trancher par la file B ou par Sam.

---

## 8. Commits de la branche

| Commit | Objet |
|---|---|
| `d35c4b8` | GL-19 — mention « contenu généré par IA » sur tous les livrables |
| `be43563` | GL-19 — bandeau « vous échangez avec une IA » dans les fenêtres du Studio |
| `8d93bd9` | BILL-07 — le produit vendu est celui que le serveur accorde |
| `6c9ecce` | BILL-06 — dialogue authentifié hors projet |
| `937d45f` | PROD-10 — contrats frontend/API sur les opérations ordinaires |
| `f3614f7` | BILL-11 — refus de crédits visible là où le client regarde |
| `7722108` | GL-18 — les trois compteurs de l'écran d'exécution sont mesurés |
| `7b7b82b` | BILL-07 — retirer un code HTTP nu d'un commentaire (garde-fou B7) |
| `9ac58b7` | GL-16 — purge des conversations du Studio, durée réglable |
| `1762ab6` | PROD-11 — le wizard ne promet plus ce qu'il ne fait pas |
| `b8ecd54` | GL-19 — harnais Chromium, mention de livrable lisible |

Aucune fusion, aucun `push --force`, aucun `git checkout` d'une autre branche.
La PR n'est pas ouverte : c'est l'orchestrateur qui l'ouvre.
