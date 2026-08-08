# Pièges de fonctionnement — à lire avant toute modification

> Ce fichier ne documente pas l'architecture (voir `MODULE-MAP.md`).
> Il consigne **ce qui fait perdre du temps** : les endroits où l'intuition
> trompe, où une modification semble faite alors qu'elle n'a aucun effet.
>
> Règle d'alimentation : quand une correction a demandé plus d'un essai parce
> qu'on s'est trompé d'endroit, on écrit ici pourquoi. Une entrée = une erreur
> qui ne se répétera pas.

---

## 1. Les prompts d'agent — trois chemins, pas un

**Le piège** : écrire une règle dans un fichier `prompts/agents/*.yaml` ne
garantit pas qu'un agent la lise. Il existe **trois chemins distincts**, et une
règle posée sur l'un n'atteint pas les autres.

| Chemin | Ce qui est lu | Qui l'utilise |
| --- | --- | --- |
| `system_prompt` racine | `PromptService.get_system_prompt(agent)` | agents en mode BUILD/SDS |
| `modes.<mode>.system_prompt` | **ÉCRASE** celui de la racine quand il existe | 10 modes, dont le `concierge` public |
| en dur dans le code | ne lit aucun YAML | `sophie_chat_service._build_system_prompt` |

**Vérifié le 08/08** : `get_system_prompt(agent, mode)` renvoie le prompt du mode
s'il existe, **sinon seulement** celui de la racine. Ce n'est pas un ajout,
c'est un remplacement.

**Les commentaires YAML (`#`) ne sont JAMAIS lus.** Une règle écrite en
commentaire, ou dans une clé inventée comme `garde_suffixe: true`, n'existe pas
du point de vue de l'agent. Erreur commise trois fois le 08/08.

**À faire** : après toute modification de prompt, vérifier par
`PromptService().get_system_prompt("raj_admin")` que le texte y est.

---

## 2. `sfdx_service._run_command` renvoie un TUPLE

```python
success, result = await self._run_command(cmd)   # correct
result = await self._run_command(cmd)            # bug : result est un tuple
```

Trois fonctions traitaient le tuple comme un dictionnaire — `retrieve_metadata`,
`execute_anonymous` et une troisième. Symptôme :
`TypeError: tuple indices must be integers or slices, not str`.

Corrigé le 08/08 sur les 10 appels. **Le bug datait de l'origine** : ce code
n'avait jamais tourné jusqu'au premier déploiement réel.

---

## 3. La classification des phases du BUILD

`TASK_TYPE_TO_PHASE` dans `phased_build_executor.py` attend un vocabulaire
précis. **Marcus en produit un autre** — deux générations coexistent :

- ancien : `create_object`, `apex_class`, `flow`
- nouveau : `dev_data_model`, `dev_apex`, `dev_flow`

Quand aucun terme ne correspond, le code retombe sur le **repli par agent**, qui
place tout chez Diego en phase 2 : le modèle de données n'est jamais construit,
et l'Apex se génère contre des objets inexistants.

**Les deux vocabulaires sont désormais reconnus.** Si Marcus en change encore,
c'est ici qu'il faut ajouter les termes — pas dans son prompt.

---

## 4. Objets Salesforce standard et suffixe `__c`

`sf_admin_service.normaliser_objet()` est la seule autorité. Ne jamais ajouter
`__c` ailleurs.

- **Objets standard** — `Lead`, `Opportunity`, `Account`, `Contact`, `Case`,
  `User`, `Task`, `Event` : **jamais** de suffixe.
- **Objets créés** : suffixe obligatoire.
- **Champs personnalisés** : suffixe toujours, y compris sur un objet standard.
- **`Task` et `Event`** : leurs champs personnalisés se déploient sur le
  conteneur **`Activity`**, jamais directement.

Le code ajoutait `__c` à tout objet qui n'en avait pas. Le WBS disait bien
`Lead` ; le déploiement demandait `Lead__c`. Trois exécutions perdues le 08/08.

---

## 5. Les recherches SQL et l'underscore

`LIKE '%Lead__c%'` ne cherche **pas** `Lead__c` : dans `LIKE`, `_` est un joker
qui matche un caractère quelconque. Le motif signifie « Lead + 2 caractères + c ».

Utiliser `position('Lead__c' in colonne) > 0`, ou `LIKE ... ESCAPE`.

Cette erreur a produit un faux diagnostic le 08/08 — un agent accusé à tort sur
sept occurrences qui n'existaient pas.

---

## 6. Le garde-fou anti-production a besoin de l'instance

`org_est_productive(cible, instance_url)` fonctionne par **liste blanche** : il
refuse tout ce qui ne porte pas un marqueur de non-production. C'est voulu.

Mais le nom d'utilisateur seul ne porte aucun marqueur — ce sont les **URL
d'instance** qui les portent (`sandbox`, `develop`, `scratch`, `orgfarm`,
`dev-ed`). Sans instance, le garde-fou refuse tout, y compris une org de
développement légitime.

`_instance_de_l_org()` interroge SFDX pour l'obtenir. Ne pas contourner le
garde-fou : ajouter le marqueur manquant à `MARQUEURS_NON_PRODUCTION`.

---

## 7. La version d'API Salesforce

Source unique : `backend/config/platform_state.yaml` → `api_version`.

Le code déployait en dur en **59.0** alors que l'état déclarait **67.0** — huit
versions de retard. Et Elena rejette tout plan qui ne déclare pas
`target_api_version`, ce que Raj ne faisait jamais : boucle de trois tentatives
puis échec, à chaque lancement.

---

## 8. Ce qui n'a jamais tourné cache des bugs

Le 08/08, le premier passage réel jusqu'au déploiement a révélé **sept défauts**
en quelques heures — tous présents depuis longtemps, aucun détectable sans
exécuter le chemin complet.

**Conséquence pratique** : quand une étape est franchie pour la première fois,
s'attendre à une série de bugs et ne pas les interpréter comme un problème de
fond. Chaque échec fait avancer d'un cran.

---

## 9. La revue d'Elena porte sur le PLAN, pas sur le XML

Elena relit le plan JSON de Raj. Le XML Salesforce est généré **après** sa revue.
Les défauts de génération vivaient donc dans cet interstice — trop tard pour
elle, trop tôt pour Salesforce.

Depuis le 08/08, `VALIDATION-XML-001` fait valider le XML par Salesforce en mode
blanc (`--dry-run`) avant tout déploiement. Aucun appel de modèle, un
aller-retour réseau.

---

## 10. Redémarrer les bons services

Une modification de code Python n'est active qu'après redémarrage :

```
systemctl restart digital-humans-worker    # exécute le BUILD
systemctl restart digital-humans-backend   # sert l'API
```

Le worker peut mettre jusqu'à une minute à s'arrêter s'il termine un travail.
Une modification de prompt YAML demande aussi un redémarrage — les prompts sont
mis en cache au chargement.

---

*Tenu à jour au fil des sessions. Dernière entrée : 8 août 2026.*
