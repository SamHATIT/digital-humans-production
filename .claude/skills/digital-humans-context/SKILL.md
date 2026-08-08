# Digital Humans Context

Documents de référence produits par Phase 1 (L'Architecte).
Ces fichiers sont la source de vérité pour tous les agents de Phase 2+.

## Fichiers
- MODULE-MAP.md : Cartographie de chaque module (chemin, rôle, statut, imports)
- ARCHITECTURE.md : Diagrammes de flux, couches, anti-patterns
- API-CONTRACTS.md : Endpoints, formats request/response, dépendances
- DEPENDENCY-GRAPH.md : Graphe imports, circulaires, singletons
- REFACTOR-ASSIGNMENTS.md : Répartition tâches par agent spécialisé
- **PIEGES.md : les endroits où l'intuition trompe.** À lire AVANT toute
  modification de prompt, de routage de phase ou de service SFDX. Ne documente
  pas l'architecture mais ce qui fait perdre du temps : les trois chemins par
  lesquels un prompt se charge, les fonctions qui renvoient un tuple, le
  vocabulaire attendu par la table des phases, le suffixe des objets standard
  Salesforce, le piège du LIKE avec underscore. Alimenté au fil des sessions —
  une entrée = une erreur qui ne se répétera pas.

## Usage
Lire ces fichiers AVANT toute modification de code.
Ils sont générés par l'agent Architect en Phase 1.
