# Note d'analyse — BUILD incrémental (DEC-2026-0802-03)

**Décision** : DEC-2026-0802-03, évolution BUILD prioritaire — le travail incrémental.
**Objectif formulé par Sam** : *« comme on écrit en base, on ne renvoie que les modifications demandées et éventuellement les éléments impactés »*.
**Statut** : note d'analyse. **Aucune modification de code.** Cette évolution touche le cœur de l'orchestration et sera revue avant application.
**Établi le** : 05/08/2026 · session `session/2026-08-05-decisions-accordees`

---

## 1. Ce que les mesures montrent — et en quoi elles corrigent la prémisse

La décision s'appuie sur l'idée que *« le contexte croît de façon quadratique »*, appuyée par quatre entrées successives de la revue : 35 953, 37 128, 37 331 puis 58 799 jetons.

Ces quatre valeurs sont exactes. Ce sont les entrées 15 à 18 de l'exécution 165 (`llm_interactions`, agent `elena`). Mais **replacées dans la série complète, elles ne décrivent pas une croissance quadratique** :

| # | jetons d'entrée | # | jetons d'entrée |
|---|---|---|---|
| 1 | 13 520 | 10 | 35 485 |
| 2 | 35 489 | 11 | 35 741 |
| 3 | 35 801 | 12 | 35 378 |
| 4 | 35 691 | 13 | 35 466 |
| 5 | 35 488 | 14 | 35 490 |
| 6 | 34 907 | 15 | 35 953 |
| 7 | 35 721 | 16 | 37 128 |
| 8 | 34 400 | 17 | 37 331 |
| 9 | 35 224 | 18 | **58 799** |

L'entrée de la revue est **plate autour de 35 000 jetons de l'appel 2 à l'appel 17**, avec un seul saut sur le dernier appel. Ce n'est pas une croissance quadratique : c'est une **répétition**.

**Le vrai gisement est là.** Elena a été appelée **18 fois** sur l'exécution 165, pour **643 012 jetons d'entrée cumulés**, à relire essentiellement le même agrégat. Et l'agent Raj a été appelé **136 fois** pour 886 757 jetons de sortie.

| agent | appels | jetons d'entrée | jetons de sortie |
|---|---|---|---|
| raj | **136** | *non enregistrés* | 886 757 |
| elena | **18** | 643 012 | 797 808 |
| marcus | 6 | 96 479 | 155 695 |
| olivia | 10 | 9 555 | 30 513 |
| autres | 8 | 59 339 | 116 000 |

> **Conséquence pour la décision** : le volet 1 (ne régénérer que les lots rejetés) attaque le gisement réel — la répétition. Le volet 2 (ne transmettre que les références) attaque un problème qui, aux mesures, est **beaucoup plus petit que supposé**, et qui est déjà partiellement résolu (§ 4). L'ordre de priorité devrait suivre.
>
> **Défaut d'instrumentation à corriger d'abord** : les jetons d'entrée de Raj — l'agent le plus appelé — **ne sont pas enregistrés** (colonne `tokens_input` à NULL sur ses 136 appels). Sans cette mesure, aucun gain ne sera démontrable après coup. C'est le prérequis n° 0.

---

## 2. Volet 1 — ne régénérer que les lots rejetés

### Le mécanisme actuel

`backend/app/services/phased_build_executor.py`, méthode `execute_phase` (lignes 234 à 277) :

```
while retry_count < self.MAX_RETRIES:          # MAX_RETRIES = 3
    batches   = await self.generate_phase_batches(agent, tasks, phase_num, retry_feedback)
    aggregated = self.aggregator.aggregate(phase_num, batches)
    review     = await self._elena_review(phase_num, aggregated)
    if review.get("verdict") == "FAIL":
        retry_count += 1
        retry_feedback = review.get("feedback_for_developer", "")
        continue                                # ← repart de zéro
```

Au `continue`, `generate_phase_batches` est rappelée avec la liste **`tasks` entière**. Elle reconstruit tous les lots via `_create_task_batches` et boucle sur l'intégralité (ligne 380). **Les lots qu'Elena avait acceptés sont régénérés à l'identique**, à un coût plein.

### Le verrou structurel

Ce n'est pas une simple boucle à raffiner. `_elena_review(phase_num, aggregated)` reçoit **l'agrégat de la phase**, pas les lots. Elle rend **un seul verdict pour toute la phase** (`verdict`, `feedback_for_developer`). 

**Rien dans la sortie de la revue ne dit quel lot a échoué.** C'est le vrai obstacle : on ne peut pas régénérer « seulement les lots rejetés » tant que la revue ne les nomme pas.

### Points d'intervention, dans l'ordre

| # | Fichier · point | Nature |
|---|---|---|
| 1 | `agents/roles/salesforce_qa_tester.py` · `review_phase_output` | Faire rendre à la revue un verdict **par lot** (ou au minimum la liste des identifiants de tâche fautifs), en plus du verdict global. Sans ce point, les suivants sont impossibles. |
| 2 | `phased_build_executor.py:380` · boucle de `generate_phase_batches` | Accepter un sous-ensemble de lots à régénérer, plutôt que reconstruire depuis `tasks`. |
| 3 | `phased_build_executor.py:234` · boucle `while` de `execute_phase` | Conserver les lots acceptés d'une itération à l'autre au lieu de repartir d'une liste vide. |
| 4 | `phase_aggregator.py:17` · `aggregate` | Agréger un mélange de lots conservés et de lots régénérés, sans double compte ni collision d'API names — la vérification de collision existe déjà pour la phase 1 (`aggregate_data_model`). |
| 5 | `phase_context_registry.py:51` · `register_batch_output` | **Point le plus délicat.** Le registre est cumulatif. Régénérer un lot déjà enregistré doit **remplacer** son apport, jamais l'ajouter deux fois. Aucune notion de retrait n'existe aujourd'hui. |

---

## 3. Le risque principal : le registre de contexte n'est pas idempotent

`register_batch_output` accumule. Exemple, `_register_data_model` (lignes 77-89) :

```
if api_name and api_name not in self.generated_objects:
    self.generated_objects.append(api_name)
...
if field_name not in self.generated_fields[obj]:
    self.generated_fields[obj].append(field_name)
```

Les gardes `not in` protègent contre le doublon **exact**. Elles ne protègent pas contre la **dérive** : si un lot régénéré produit `Contrat__c.Date_Fin__c` là où la version précédente avait produit `Contrat__c.Date_Cloture__c`, les **deux** champs resteront dans le registre. Le contexte injecté dans les phases suivantes décrira alors un modèle de données qui n'a jamais été déployé.

C'est le risque le plus sérieux de l'évolution, et il est **silencieux** : rien ne le signalerait.

**Atténuation** : indexer les apports du registre par identifiant de lot, et purger l'apport d'un lot avant de réenregistrer sa nouvelle version. Cela suppose de faire porter au registre une structure par lot qu'il n'a pas aujourd'hui.

### Autres risques

| Risque | Portée | Atténuation |
|---|---|---|
| Un lot conservé devient incohérent avec un lot régénéré (une classe appelle une méthode qui a changé de signature) | Phase 2 surtout | Régénérer aussi les lots **dépendants** du lot rejeté — c'est le « éventuellement les éléments impactés » de Sam. `task_executions.depends_on` existe déjà et est alimenté. |
| La revue par lot devient plus coûteuse que la revue globale (18 appels deviennent 12 × N) | Coût | Conserver la revue globale et n'y **ajouter** que l'attribution des fautes, sans multiplier les appels. |
| `MAX_RETRIES = 3` compté par phase devient ambigu s'il est compté par lot | Boucle | Trancher explicitement : compteur par lot, avec un plafond global de phase. |
| Perte de la trace d'audit : un lot conservé n'a pas de nouvelle entrée `llm_interactions` | Observabilité | Journaliser explicitement « lot N conservé, non régénéré » pour que le compte de lots reste lisible. |

---

## 4. Volet 2 — ne transmettre que les références : déjà fait en grande partie

**Constat qui change le périmètre.** Le mécanisme demandé par Sam — transmettre les noms d'objets et de champs plutôt que leur définition entière — **existe déjà** pour le passage d'une phase à l'autre.

`phase_context_registry.py:238`, `get_full_data_model()` :

```
lines = ["## MODÈLE DE DONNÉES DISPONIBLE (Phase 1 déployée)", ""]
for obj in self.generated_objects:
    lines.append(f"### {obj}")
    fields = self.generated_fields.get(obj, [])
    if fields:
        lines.append("**Champs:** " + ", ".join(fields))
```

Ce sont des **noms**, pas des définitions. De même `get_class_signatures()` ne transmet que les signatures. Le contexte inter-phases est donc déjà réduit à des références — ce qui explique pourquoi l'entrée de la revue reste plate à 35 000 jetons au lieu de croître.

**Ce qui reste à traiter** :
- `get_context_for_batch(phase, include_previous_batches=True)` (ligne 189) réinjecte les **lots précédents de la même phase**. C'est la seule accumulation intra-phase, et c'est là que se logerait une croissance si le nombre de lots augmentait. Le paramètre `include_previous_batches` existe déjà : le rendre pilotable par phase est un changement de faible ampleur.
- Le saut de l'appel 18 (58 799 jetons) n'est pas expliqué par ce document et **mérite une mesure dédiée** avant toute optimisation : optimiser sans avoir compris ce saut reviendrait à traiter un symptôme.

**Recommandation** : traiter le volet 2 **après** le volet 1, et le réduire à son reste réel plutôt qu'au périmètre initialement supposé.

---

## 5. Plan de test

Aucune de ces étapes ne demande de relancer un BUILD intégral — contrainte de coût et de présence de Sam.

**Étape 0 — instrumenter (prérequis)**
Enregistrer `tokens_input` pour tous les agents, Raj compris. Vérification : sur une exécution quelconque, `SELECT count(*) FROM llm_interactions WHERE tokens_input IS NULL` doit rendre 0. Sans cela, aucun gain n'est mesurable.

**Étape 1 — tests unitaires du registre (sans LLM)**
- Enregistrer un lot, le réenregistrer modifié, vérifier que l'apport précédent a bien été **remplacé** et non cumulé. C'est le test qui couvre le risque du § 3.
- Vérifier l'idempotence : enregistrer deux fois le même lot laisse le registre identique.

**Étape 2 — tests unitaires de la boucle (revue simulée)**
Simuler `_elena_review` pour qu'elle rejette les lots 3 et 7 sur 12, et vérifier :
- que `generate_phase_batches` n'est appelée que pour les lots 3 et 7 (et leurs dépendants) ;
- que l'agrégat final contient bien les 12 lots ;
- que le compteur d'avancement publié par `_publish_batch_progress` reste cohérent (il affiche `completed/total` — corrigé par FIX-BATCHPROG-001, à ne pas casser).

**Étape 3 — rejeu à froid sur données réelles**
L'exécution 165 dispose de 18 revues Elena et de 136 appels Raj enregistrés. Rejouer la logique de sélection des lots **sur ces enregistrements**, sans appeler aucun LLM, et mesurer combien de lots auraient été épargnés. Cela chiffre le gain avant d'engager le moindre coût.

**Étape 4 — exécution réelle, une seule phase**
Sur la phase 1 seule (la moins coûteuse, et celle qui a produit les 136 appels Raj), comparer le nombre d'appels et les jetons consommés avant et après. **En présence de Sam**, conformément à la règle de la maison.

**Critère d'acceptation proposé** : sur un rejeu équivalent à l'exécution 165, réduction d'au moins la moitié des appels de régénération, sans aucune divergence du modèle de données agrégé par rapport à la version actuelle.

---

## 6. Ce qui n'est pas tranché dans cette note

- **L'ordre entre correctif et évolution.** Le brief du comité rappelle un ordre technique : delta incrémental (DEC-2026-0802-03) **puis** correctif. Le correctif FIX-TASKTYPE-001 de cette session a été appliqué en premier, la décision DEC-2026-0803-01 étant la priorité absolue de la session. Cet ordre doit être arbitré par Sam avant toute relance.
- **Le saut de l'appel 18** (58 799 jetons) reste inexpliqué.
- **La granularité du verdict d'Elena** — par lot, ou par fichier — n'est pas tranchée ; elle détermine tout le reste.

---

*Document d'analyse, aucune modification de code. Toutes les mesures citées proviennent de `llm_interactions` sur l'exécution 165, relevées le 05/08/2026.*
