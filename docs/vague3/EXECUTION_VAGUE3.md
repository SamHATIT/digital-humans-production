# Exécution de la vague 3 — reprise d'exécution et sélection des experts

Branche `claude/reprise-experts-k7m2`, issue de `851843a` · 7 commits ·
16 fichiers · +3408 / −193

Périmètre : `SPEC_VAGUE3_reprise_et_selection_experts.md`, arbitrages rendus par
Sam le 23 août 2026. L'ordre de réalisation du §5 a été suivi à la lettre —
§3.5, §3.1, §3.2, §3.3/§3.4, puis §4 en dernier parce qu'il modifie ce qu'une
reprise en `phase4` doit relire.

**Un lot = un commit.** Chaque correctif a un test rouge avant / vert après,
dont la sortie est citée.

---

## Suite de tests

| | échecs | passés | xfail | erreurs |
|---|---|---|---|---|
| Départ, mesuré à `851843a` | 9 | 456 | 6 | 0 |
| Après la vague 3 | **8** | **595** | **7** | 0 |

Le 9ᵉ échec de départ, `test_deployment_cloisonnement`, est passé en `xfail`
sur arbitrage (voir §1). Les 8 restants sont la même liste nominative qu'au
départ : `test_credit_service.py` (4), `test_auth.py` (3),
`test_emma_phase3.py` (1). Tous préexistent à cette vague et sont hors
périmètre.

**139 tests ajoutés**, tous en Python :

| Fichier | Tests | Objet |
|---|---|---|
| `test_vague3_resume_points.py` | 24 | §3.5 — refus des valeurs inconnues |
| `test_vague3_reprise_phases.py` | 16 | §3.1 — `phase2_5` et `phase3` |
| `test_vague3_correspondance.py` | 32 | §3.2 — table de correspondance |
| `test_vague3_export_et_build.py` | 25 | §3.3 et §3.4 — export et BUILD |
| `test_vague3_annotations_kwarg.py` | 7 | §6 — kwarg refusé par le worker |
| `test_vague3_selection_experts.py` | 19 | §4 — la règle de sélection |
| `test_vague3_selection_persistee.py` | 8 | §4 — persistance et relecture |
| `test_vague3_selection_phase4.py` | 8 | §4 — exercée en phase 4 |

---

## 1. Arbitrage rendu — `test_deployment_cloisonnement` *(commit `17d9bf8`)*

Dernier des neuf échecs à être inexpliqué. Le routeur `deployment` a été
démonté volontairement par `1438431` ; le test attend `401` sur
`POST /api/deployment/promote` et obtient `404`. **Le test est correct — c'est
sa cible qui a disparu.**

`xfail(strict=True)` et non suppression : il porte la trace que sept routes non
cloisonnées ont existé, et il repassera en `XPASS` — donc en échec de suite —
le jour où le routeur sera remonté. C'est exactement le moment où il faudra le
relire.

Preuve : `9 passed, 1 failed` → `9 passed, 1 xfailed`.

---

## 2. §3.5 — une valeur inconnue est refusée *(commit `1170d46`)*

**Défaut.** `execute_workflow` ne reconnaissait que cinq points de reprise.
Toute autre valeur tombait dans la branche générique « saute la phase 1, rejoue
à partir de la phase 2 ».

**Cause.** Le repli était silencieux. C'est la cause commune des douze valeurs
mortes, pas douze défauts indépendants. La vague 2 en avait corrigé une
(`build_tasks`) et posé un WARNING sur les autres : le WARNING les rend
visibles, il ne les empêche pas.

**Correctif.** Le WARNING devient un `ValueError` qui nomme la valeur refusée,
la liste des points valides, et oriente vers `execute_build_task` pour les
reprises BUILD. Une exception coûte un job en échec ; un repli silencieux coûte
une chaîne SDS entière, facturée, sur un travail déjà fait.

Le refus est **avant le `try:`** de la méthode : un point de reprise faux est
une erreur d'appelant, pas un échec d'exécution à consigner —
`execute_workflow` capte tout le reste et rend `{"success": False, ...}`. La
différence est testée des deux côtés.

**Preuve exécutée.**

```
$ pytest tests/test_vague3_resume_points.py
AVANT : 14 failed, 8 passed
APRÈS : 22 passed        (puis 24 après l'ajout des contrôles de §3.1)
```

Les 14 rouges couvrent nominativement les onze valeurs mortes de la
spécification, `phase2_ba`, une valeur inventée, et l'énoncé des valeurs valides
dans le message.

---

## 3. §3.1 — `phase2_5` et `phase3` *(commit `c01b141`)*

Le plus gros gain de la spécification.

**Défaut.** Aucun point d'entrée entre `phase2` et `phase4`. Si Marcus échouait
à son quatrième appel — le cas le plus fréquent et le plus coûteux — la seule
reprise disponible était `phase2`, qui refait tous les UC d'Olivia. **Un échec
de l'architecte détruisait le travail de l'analyste, et le repayait.**

**Correctif.** Règle retenue par Sam : « on garde ce qui est terminé
correctement, et on reprend à la suite du dernier qui a réussi. »

- `phase2_5` — les UC d'Olivia sont conservés, le digest d'Emma est refait.
- `phase3` — UC et digest conservés, Marcus reprend ses quatre appels.

La `checkpoint_map` de la reprise automatique (BUG-010) applique la même règle.
`phase2_ba` pointait `phase2` — commentaire à l'appui, « re-run Phase 2 (UCs in
DB, safe to redo) », donc sans danger mais entièrement repayé ; elle pointe
désormais `phase2_5`. `phase2_5_emma` passe de `phase2` à `phase3`.

**Trois endroits où le correctif refuse de dégrader en silence.**

- **Le digest est relu, pas supposé.** Sans `_load_uc_digest`, une reprise
  `phase3` serait *pire* que `phase2` : Marcus concevrait avec `uc_digest = {}`,
  donc sans la synthèse des UC, et rien ne le signalerait — le repli « Marcus
  utilisera les UC bruts » est prévu pour un échec d'Emma, pas pour une reprise.
- **Digest absent en reprise `phase3`** : Marcus continue sur les UC bruts, mais
  un WARNING le dit. Sans trace, un SDS de moindre qualité serait
  indistinguable d'un SDS nominal.
- **Aucun UC en base** : la porte qui suit la phase 2 distingue les deux causes.
  Sur une reprise, Olivia n'a pas échoué — elle n'a pas tourné. Le message
  oriente vers `phase2` au lieu de faire chercher une panne qui n'a pas eu lieu.

**Méthode de preuve.** `_run_agent` est le point de passage unique de tous les
appels d'agents. Il est instrumenté pour enregistrer qui est appelé, et la
course est arrêtée à l'entrée de Marcus. Ce qui est prouvé n'est pas qu'une
exécution va au bout, c'est **qui a été rappelé et qui ne l'a pas été**.

```
$ pytest tests/test_vague3_reprise_phases.py
AVANT : 9 failed, 2 passed
APRÈS : 16 passed
```

Les 2 verts d'emblée sont les contrôles de non-régression : un démarrage normal
repart bien de Sophie, et `phase2` continue de rejouer Olivia — la reprise
coûteuse que ce lot vient éviter, pas supprimer.

---

## 4. §3.2 — les routes enfilent du canonique *(commit `2ac0ba4`)*

**Défaut.** Chaque route raisonne en **agents**, parce que c'est ce qu'elle
observe (`agent_execution_status`), alors que le workflow raisonne en
**phases**. L'écart n'avait jamais été traduit.

**Correctif.** `resolve_resume_point()` porte la table de §3.2 et vit **au
bord** : les routes traduisent avant d'enfiler, et `execute_workflow` continue
de n'accepter que `SDS_RESUME_POINTS`. La table alimente son vocabulaire, elle
ne l'affaiblit pas. Elle est idempotente, de sorte qu'une route qui parle déjà
le bon vocabulaire (`phase1`) n'a pas besoin d'être distinguée.

`phase2_ba` produisait déjà le bon effet, **mais par accident** : elle tombait
dans la branche générique comme les onze autres. La traduction transforme la
coïncidence en contrat.

**Effet de bord évité, et c'est le point d'attention de ce lot.** Le câblage
avait d'abord été posé en import de niveau module dans `retry_routes`.
`pm_orchestrator_service_v2` tire python-docx et chromadb : cela aurait fait
dépendre le démarrage de l'API de ces deux paquets, alors qu'`app.main`
s'importe sans eux — propriété constatée en vague 2, c'est ainsi que le défaut
1b avait été reproduit. L'import est local, comme le reste du fichier, et un
test verrouille la propriété sur tout `app/api/routes`.

```
$ pytest tests/test_vague3_correspondance.py
AVANT : 3 failed, 26 passed
  AssertionError: la route enfile 'phase_ba', qu'execute_workflow refuse
APRÈS : 32 passed
```

---

## 5. §3.3 et §3.4 — export et BUILD *(commit `e9c210d`)*

**Défaut.** Une seule destination — `execute_sds_task` — pour trois chaînes
distinctes. Les six valeurs des deux tables de `validation_gate_routes` étaient
mortes. La plus coûteuse est dans le chemin nominal du client : approuver la
porte `after_build_code` émettait `deploy` et relançait toute la chaîne SDS.
**Une validation humaine relançait le travail qu'elle venait de valider.**

**Correctif.** `_relancer_apres_porte` aiguille vers la bonne chaîne.

§3.4 — BUILD (`deploy`, `build`) : job `execute_build_task`, `TaskExecution`
remises à PENDING avant l'enfilage. Même mécanique que le LOT 1a de la vague 2
(`57ee795`), qui a servi de modèle comme la spécification le demandait.

§3.3 — export (`phase6_export`) : aucun agent relancé.

| État | `sds_document_path` | Action |
|---|---|---|
| `sds_complete` | `.docx` / `.pdf` | mise à disposition, rien de relancé |
| `sds_complete` | `.md` seul | régénération de l'export |
| `sds_phase4_complete` | — | Emma reprend l'écriture (`phase5`) |
| avant `phase4_complete` | — | **409** — pas un cas d'export |

**Le Markdown n'est pas un livrable.** La phase 6 le renseigne en repli quand
l'export DOCX échoue ; il sert la vue HTML. Le servir rendrait au client un
fichier qu'il ne peut pas ouvrir dans Word, en prétendant que tout va bien.
C'est l'extension qui est vérifiée, pas la seule présence du chemin — et une
extension inconnue (`.txt`, `.json`, aucune) n'est pas plus un livrable qu'un
`.md`.

**Deux défauts trouvés en réécrivant le bloc**, tous deux du même genre que ceux
de la spécification :

- **Une porte inconnue produisait un job muet.** `resume_map.get(gate_name)`
  rendait `None`, qui partait tel quel dans `resume_from`. Désormais 400.
- **Un rejet avec annotations sur la chaîne BUILD les perdrait en silence** :
  `execute_build_task` ne les transporte pas. Traité en §6.

```
$ pytest tests/test_vague3_export_et_build.py
AVANT : ImportError, puis 1 failed / 17 passed
  AssertionError: la porte BUILD doit reprendre le BUILD, pas le SDS :
  execute_sds_task (kwargs={... 'resume_from': 'deploy'})
APRÈS : 25 passed
```

Les trois destinations sont prouvées **au niveau route**, pas seulement en
unité.

---

## 6. §6 — le kwarg que le worker refuse *(commit `4a86300`)*

**Défaut.** `validation_gate_routes` passait `annotations=` à
`execute_sds_task`, qui n'a pas ce paramètre. ARQ sérialise les kwargs sans les
valider : l'enfilage réussit, le job meurt en `TypeError` **dans le worker**.
Côté client, la porte est rejetée, la réponse est 200, et rien ne redémarre.
**Rejeter une porte avec commentaires ne relançait rien**, et l'échec était
entièrement invisible depuis l'API.

**Correctif.** Le kwarg est retiré. Il n'est **pas** rebranché plus loin, et
c'est un choix documenté. Vérification faite avant de concevoir : **personne ne
lit ces annotations.** Aucun agent, aucun prompt ; `execute_workflow` n'a pas de
paramètre `annotations` ; `execution.validation_history` est écrit par
`ValidationGateService` et jamais relu ailleurs. Le kwarg était un passe-plat
vers un consommateur inexistant.

Le câbler jusqu'à `execute_workflow` aurait créé un paramètre inerte de plus.
Faire relire les annotations par les agents est de la fonctionnalité, pas un
correctif.

Ce qui est fait à la place, pour que la perte cesse d'être silencieuse : un
WARNING au rejet, et un champ `annotations_applied: false` dans la réponse. Le
client voit que son commentaire est enregistré et qu'il n'est pas encore
réinjecté — au lieu de le supposer pris en compte.

Un test verrouille l'inverse : il rougit le jour où `execute_workflow` acquiert
un paramètre `annotations`. C'est exactement le moment de rebrancher la chaîne.

```
$ pytest tests/test_vague3_annotations_kwarg.py
AVANT : 4 failed, 3 passed
  AssertionError: le job 'execute_sds_task' porte des kwargs que la tâche
  refuse : ['annotations']. Il mourra en TypeError dans le worker.
APRÈS : 7 passed
```

La vérification se fait par **introspection de la signature de la tâche ARQ**,
sur les trois portes en rejet : elle aurait attrapé le défaut d'origine, et
attrapera toute dérive de kwargs à venir, sur `execute_sds_task` comme sur
`execute_build_task`.

---

## 7. §4 — la sélection des experts par Marcus *(commit `04e8ebb`)*

**Défaut.** Le filtre portait sur `execution.selected_agents`, une colonne
renseignée **au lancement** — donc avant que quiconque ait analysé le projet.
Vide, les quatre experts tournent ; en pratique elle est toujours vide. Le
mécanisme existait mais était alimenté par le mauvais bout. Dispositif inerte de
plus, même famille que `BuildEnabledMiddleware` et `require_feature` avant la
vague 1.

**Comment Marcus décide — et c'est le point à valider.** Pas par un cinquième
appel LLM : par ce qu'il vient d'écrire. Le WBS, l'architecture et les écarts
sont ses livrables ; s'ils ne portent aucune tâche de migration, Marcus a déjà
décidé qu'il n'y a pas de migration. La règle est lue dans ses artefacts —
déterministe, gratuite, sans nouveau mode de panne, vérifiable ligne à ligne.

Les signaux sont volontairement larges : **un faux positif coûte un livrable de
trop, un faux négatif coûte un volet absent du SDS**, et un volet manquant se
découvre chez le client. Les deux ne se valent pas.

Le jour où un jugement plus fin qu'un faisceau de mots-clés sera voulu, l'appel
dédié se branchera au même endroit sans changer le contrat de sortie. **C'est
une décision d'implémentation que la spécification ne tranchait pas** — elle dit
« au vu de l'architecture qu'il vient de produire », ce qui est satisfait, mais
n'exclut pas un appel dédié.

**Les quatre contraintes.**

1. **Elena est inamovible.** Marcus décide de `data`, `trainer` et `devops`.
2. **La sélection est persistée** — colonne `executions.expert_selection`
   (JSONB, révision Alembic `011_expert_selection`). Colonne dédiée et non
   réutilisation de `selected_agents` : cette dernière porte l'intention du
   client, qui prime sur Marcus — l'écraser effacerait ce qui doit primer sur
   lui. `NULL` signifie « Marcus n'a pas tranché », pas « aucun expert ».
   Une reprise **relit** et se déclare `decided_by="resumed"`. C'est le point
   que §3.2 signalait à revoir ; il l'est.
3. **Un expert écarté est justifié dans le SDS**, avec la formulation de Sam.
   La section est ajoutée au markdown **par le code**, pas confiée au prompt
   d'Emma : la couverture est un fait de l'exécution, pas une rédaction, et ne
   doit pas dépendre de ce que le LLM a bien voulu reprendre.
4. **Le choix explicite de l'utilisateur prime.** Une liste sans aucun expert
   (`["pm","ba","architect"]`) n'est pas un choix d'experts : la laisser
   signifier « aucun expert » écarterait Elena et reproduirait le défaut
   d'origine.

**Sur la méthode de preuve — un correctif apporté en cours de route.** Les tests
de phase 4 ont d'abord été écrits en inspection de source
(`assert "decide_sds_experts" in source`). Ils ont été **remplacés par des tests
de comportement** qui exécutent réellement `_execute_from_phase4` et constatent
quels agents ont tourné. Une assertion sur le texte du fichier prouve qu'une
chaîne est présente, pas que la phase lance les bons experts — c'est la forme
exacte du test de LOT-G qui certifiait « boot sans `create_all` » en assertant
la présence de la ligne fautive.

Leur rouge a été mesuré en restaurant temporairement l'ancien filtre :

```
$ pytest tests/test_vague3_selection_phase4.py     # ancien filtre restauré
4 failed, 4 passed
$ pytest tests/test_vague3_selection_phase4.py     # correctif en place
8 passed
```

Les 4 qui restent vertes sont les contrôles positifs (Elena tourne, Aisha tourne
quand il y a migration, le choix utilisateur est respecté) : elles ne
discriminent pas ce défaut-là, elles en attrapent le symétrique.

**Le harnais de test a lui-même dû être corrigé.** Son `except Exception`
masquait un `NameError`, si bien que quatre tests passaient parce que **rien
n'avait tourné**. Il échoue désormais si aucun agent n'est appelé. Un vert
obtenu sur une phase qui n'a pas démarré ne prouve rien.

```
$ pytest tests/test_vague3_selection_experts.py    19 passed  (avant : ImportError)
$ pytest tests/test_vague3_selection_persistee.py   8 passed  (avant : 8 failed)
```

---

## 8. Constats infirmés, ou plus étroits qu'annoncé

| Constat | Verdict |
|---|---|
| « onze autres valeurs sont dans le même cas » | **Confirmé, dénombrement exact.** Les onze sont nominativement couvertes par un test chacune. `phase2_ba` en fait douze au total avec `build_tasks`, déjà traitée en vague 2. |
| « `phase2_ba` … son effet réel coïncide avec l'intention. Juste par accident » | **Confirmé.** Elle tombait bien dans la branche générique ; le bon comportement était fortuit. |
| §3.2, « si la sélection par Marcus est mise en place, ce point est à revoir » | **Traité dans la même vague.** `decide_sds_experts` relit la sélection persistée ; une reprise en `phase4` ne ressuscite pas un expert écarté. Un test le prouve en rejouant la phase 4 avec des artefacts *contenant* de la migration. |
| « Le mécanisme de sélection existe mais est alimenté par le mauvais bout » | **Confirmé, et plus large :** le filtre existait à **deux** endroits — `_init_agent_status` (l'affichage) et `_execute_from_phase4` (l'exécution). Seul le second est corrigé (voir §9.2). |

Aucun constat de la spécification n'a été infirmé. C'est notable et vaut d'être
dit : les vagues 1 et 2 en avaient produit neuf et cinq. La spécification de la
vague 3 a été écrite après mesure, pas avant.

---

## 9. Ce qui reste ouvert

### 9.1 La chaîne Alembic ne construit pas une base depuis zéro

**Mesuré, pas supposé.** Sur une base vide :

```
$ alembic upgrade head
INFO  Running upgrade 006_validation_gates -> 007_conv_agent_id
sqlalchemy.exc.NoSuchTableError: project_conversations
```

Huit révisions passent, la neuvième échoue : `007_conv_agent_id` indexe et
remplit `project_conversations`, table qu'aucune révision antérieure ne crée.
Elle vient de `create_all`.

C'est exactement l'incident annoncé par PROD-05, et signalé sans être traité en
vague 2 (`EXECUTION_VAGUE2.md` §7.5). **Préexistant à cette vague** — non causé
par la révision `011`.

Ma révision, elle, a été vérifiée isolément :

```
$ alembic stamp 010_pro_tier_marcus_opus && alembic upgrade head
Running upgrade 010_pro_tier_marcus_opus -> 011_expert_selection
$ psql -tAc "SELECT column_name, data_type FROM information_schema.columns
             WHERE table_name='executions' AND column_name='expert_selection'"
expert_selection|jsonb
$ alembic downgrade -1     # puis vérification : 0 colonne
```

Elle s'applique et se renverse. Mais **elle ne pourra être déployée que sur une
base déjà stampée**, comme toutes les précédentes. Hors périmètre de cette
vague ; c'est un chantier à part entière.

### 9.2 Le filtre d'affichage des agents n'est pas aligné sur la décision

`_init_agent_status` (`pm_orchestrator_service_v2.py`) construit la liste des
agents affichés dans l'UI en filtrant `ALL_SDS_EXPERTS` sur `selected_agents` —
c'est-à-dire l'ancien mécanisme, au lancement, **avant que Marcus ait décidé**.

Conséquence : l'UI affichera les quatre experts en attente, puis trois d'entre
eux passeront de « waiting » à rien. Ce n'est pas faux — la décision n'existe
pas encore au moment où la liste est construite — mais c'est incohérent avec le
SDS produit.

Non traité : aligner suppose soit de retarder l'initialisation du statut après
la phase 3, soit de rafraîchir la liste à la décision. Les deux touchent au
contrat de l'endpoint de progression et au frontend, hors du périmètre de cette
spécification.

### 9.3 `agent_deliverables.agent_id` est NOT NULL, et son repli ne peut pas fonctionner

Trouvé en montant les fixtures de §3.1. `resolve_agent_pk` documente : « Ne lève
jamais : un échec de résolution ne doit pas bloquer l'écriture d'un deliverable
(on retombe sur le comportement legacy NULL, sans régression). »

Or la colonne est `nullable=False`. Le repli insère donc `NULL` dans une colonne
qui le refuse, l'`IntegrityError` est avalée par le `try/except` de
`_save_deliverable`, et **le livrable est perdu en silence**.

Cela ne se manifeste que si la table `agents` ne contient pas la ligne
attendue — ce qui n'est pas le cas en production, sinon tous les livrables
seraient perdus. C'est une fragilité latente, pas une panne active. Mais elle
frapperait exactement une reprise `phase3`, qui dépend du digest en base.

Non traité : hors périmètre, et le corriger demande de trancher entre rendre la
colonne nullable et garantir le peuplement de `agents`.

### 9.4 Le vocabulaire `resume_from` reste large

Sept valeurs canoniques, dont deux redondantes (`phase1` et `phase1_pm`). La
spécification le relève au §1 sans demander de les fusionner. Non fait : la
fusion casserait des appelants existants pour un gain cosmétique.

---

## 10. Ce qui n'a pas été fait, et pourquoi

Distinct de la section précédente : ce sont des choix, pas du reliquat.

- **Aucun redémarrage de service.** Tout est préparé, testé hors ligne et
  commité. La mise en production est une décision de Sam.
- **La révision `011` n'a pas été appliquée à la base de production.** Elle a
  été vérifiée sur une base jetable. `alembic upgrade head` sur le VPS est un
  geste d'exploitation.
- **Les annotations ne sont pas rebranchées jusqu'aux agents** (§6) : c'est de
  la fonctionnalité, et rien ne les consomme aujourd'hui.
- **Marcus ne fait pas d'appel LLM dédié pour choisir** (§7) : la décision est
  lue dans ses artefacts. Le point de branchement d'un appel dédié est prévu et
  isolé si Sam préfère cette voie.
- **`_init_agent_status` n'est pas aligné** (§9.2) : touche au frontend.

---

## 11. Commits

| SHA | Objet |
|---|---|
| `17d9bf8` | `test_deployment_cloisonnement` en `xfail` — routeur démonté |
| `1170d46` | §3.5 — une valeur de `resume_from` inconnue est refusée |
| `c01b141` | §3.1 — reprise en `phase2_5` et `phase3` |
| `2ac0ba4` | §3.2 — les routes enfilent un point de reprise canonique |
| `e9c210d` | §3.3 §3.4 — export conditionnel, porte BUILD vers le worker BUILD |
| `4a86300` | §6 — le rejet d'une porte enfilait un job que le worker refuse |
| `04e8ebb` | §4 — Marcus décide des experts, décision persistée et justifiée |

### Note sur la branche

`claude/reprise-experts-k7m2`, créée depuis `851843a` comme demandé — pas la
continuation de `claude/new-session-ihss3x`. `851843a` en est l'ancêtre direct,
donc l'intégration est une avance rapide.

Le déploiement demande **un redémarrage** (`git pull` ne recharge pas Python) et
**un `alembic upgrade head`** pour la colonne `expert_selection`, dans cet
ordre : la migration d'abord, sinon le code écrira dans une colonne qui n'existe
pas. Rien n'a été redémarré ni migré.
