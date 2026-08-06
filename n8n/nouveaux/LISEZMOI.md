# Collecteur de signaux publics — état au 06/08/2026

## Ce qui est construit et fonctionne

`signaux-publics.json` — workflow N8N importé, **inactif**. Cinq nœuds :
déclencheur quotidien 7h30, déclencheur manuel (webhook `signaux-publics-manuel`),
interrogation du BOAMP, filtrage/normalisation, enregistrement en base.

Table `signaux_publics` créée, vue `v_deos_signaux` accordée à `deos_ro`.
Aucune donnée personnelle : uniquement des organisations et des avis publics.

## Ce que la mesure a montré — à arbitrer

Le collecteur marche. **C'est la source qui pose problème.**

| Source testée | Résultat mesuré | Verdict |
| --- | --- | --- |
| **BOAMP** (marchés publics) | 962 avis mentionnent « salesforce », mais **1 seul par an** le mentionne dans l'OBJET du marché. Les autres sont du bruit (traiteur, consommables…) | Signal très fort mais **trop rare** |
| **Remotive** (offres d'emploi) | 34 résultats, aucun poste Salesforce réel, périmètre mondial et distanciel | **Inadapté** |
| **France Travail** | Clé d'API requise (inscription gratuite sur francetravail.io) | **À tester** — la plus prometteuse pour la France |
| **Adzuna** | Clé requise, offre gratuite disponible | À tester |

Sans filtre sur l'objet, le BOAMP remonte n'importe quoi. Avec le filtre, il ne
remonte presque rien. Les deux sont vrais, et c'est ce qui rend l'arbitrage utile.

## Ce que je recommande

1. **Garder le BOAMP** malgré son faible débit : un marché public Salesforce est
   le signal le plus fort qui existe (budget voté, besoin décrit, calendrier connu).
   Un par an vaut la peine d'être capté. Coût : zéro.
2. **Obtenir une clé France Travail** (gratuite) et brancher la même mécanique.
   C'est là que le volume devrait être.
3. **Ne pas industrialiser avant d'avoir mesuré** le débit réel de France Travail.
   Le principe reste : mesurer avant d'investir.

## Réserve honnête

Le rendement des sources publiques n'est pas démontré. Il est possible que le
meilleur canal reste le réseau et les partenaires, comme l'analyse stratégique
le suggérait. Ce collecteur ne coûte rien à laisser tourner, mais il ne doit pas
retarder les démarches directes.

## Activer

Depuis la console N8N ou l'interface, activer « Signaux Publics - Collecteur (BOAMP) ».
Test manuel : `curl -X POST https://n8n.samhatit-consulting.cloud/webhook/signaux-publics-manuel`
