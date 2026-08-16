# EMMA-BATCH-001 — découper `_execute_analyze` en lots, sur le modèle de Sophie

> **Décidé par Sam le 11/08.** À tester, pas à déployer. Priorité : après validation E2E.

## Constat

`_execute_analyze` (`agents/roles/salesforce_research_analyst.py`, ~ligne 500) construit
un `uc_text` qui concatène **tous** les use cases — objet, automation, main flow, trois
critères d'acceptation chacun — puis fait **un appel unique à `max_tokens=32000`**.
Le volume croît linéairement avec le nombre d'UC : 83 sur l'exécution 143.

C'est le profil exact de Sophie avant TRUNC-002. Le correctif y est déjà écrit et
éprouvé : `app/services/sds_section_writer.py`, `generate_uc_section_batched`,
`UC_BATCH_SIZE = 50` — passé de 100 à 50 après débordement à 16K et raccords.

**Ce qui n'est PAS en cause.** `_execute_validate` est déjà correctement conçu : scoring
100 % programmatique, LLM appelé seulement sous 95 % et uniquement sur les écarts.
`_execute_write_sds` ne fait plus d'appel LLM (assemblage Jinja2, 1,6 s, coût nul).
**Une seule méthode est à reprendre.**

## Ce qu'il faut vérifier avant de découper

**Le UC Digest est-il additif ?** Le découpage est valide si chaque UC produit son entrée
indépendamment. Il est **invalide** si Emma doit repérer des redondances ou des conflits
*entre* UC — un lot ne voit pas les autres. À trancher en lisant le gabarit
`emma_research / uc_digest` avant d'écrire une ligne de code. **C'est le point de
rupture possible de toute l'idée.**

## Effet croisé avec Gemma — à mesurer, pas à supposer

Gemma 4 remplit `reasoning_content` avant `content` : un `max_tokens` trop bas est
intégralement consommé par la réflexion et `content` revient **vide**. Plancher posé à
2 000 jetons (commit `286d4de`).

**Conséquence directe** : en découpant en N appels, le plancher de réflexion se paie
**N fois**. Le gain de découpe et le surcoût de réflexion jouent en sens inverse, et le
point d'équilibre dépend de la taille de lot. **Aucune conclusion sans mesure.**

## Protocole

Entrées gelées : un projet réel à fort volume d'UC (exécution 143, 83 UC).
Variantes : appel unique (témoin) · lots de 50 · lots de 25.
Sur les deux routages : Gemma en local, et Sonnet en API.

| Critère | Mesure |
| --- | --- |
| Complétude | nombre d'UC présents dans le digest / nombre d'UC en entrée |
| Fidélité | contenu tronqué, critères d'acceptation perdus, raccords |
| Vue d'ensemble | redondances entre UC détectées en appel unique et perdues en lots |
| Coût | jetons totaux, dont réflexion Gemma, sur les deux routages |
| Latence | bout en bout |

**Livrable** : un tableau, une taille de lot recommandée, ou le constat que le digest
n'est pas découpable. Les trois issues sont acceptables.

## Point annexe, à ne pas confondre avec celui-ci

Emma est le seul agent qui interroge le RAG, et les embeddings ChromaDB sont en
`text-embedding-3-large` **chez OpenAI**. Sur un profil local ou on-premise, sa recherche
sort du périmètre à chaque requête. Sujet distinct, à instruire séparément.
