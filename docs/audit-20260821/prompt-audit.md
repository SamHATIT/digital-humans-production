Tu audites le code d'une plateforme SaaS avant sa mise en production, prévue le **1er octobre 2026**. L'éditeur est une personne seule, mais elle dispose d'agents de développement pour appliquer les correctifs en parallèle. Calibre tes recommandations en conséquence : le facteur limitant est le temps d'arbitrage humain, pas le nombre de mains. Ton rapport servira de feuille de route — ce que tu ne signales pas ne sera pas corrigé.

## Ce que fait la plateforme

Onze agents d'IA spécialisés produisent des livrables Salesforce en deux séquences. La première génère un document de spécification : un agent cadre le besoin, un deuxième le traduit en exigences, un troisième interroge une base documentaire, un quatrième arbitre les choix techniques, le premier rédige. La seconde séquence produit du code en six phases — modèle de données, Apex, composants d'interface, automatisations, sécurité, migration — avec une relecture qualité avant chaque déploiement.

Pile : FastAPI et PostgreSQL au backend, React et Vite au frontend, ChromaDB pour la recherche documentaire, Redis et ARQ pour les tâches asynchrones, Nginx en frontal. Le déploiement Salesforce passe par SFDX.

Trois paliers commerciaux : un accès gratuit limité au dialogue, un palier professionnel à 79 €/mois qui produit des spécifications, un palier équipe à 1 490 €/mois qui ouvre la séquence de construction jusqu'à l'environnement de test. Aucun déploiement automatique en production.

## Ce qui a déjà été corrigé — à vérifier

Un audit interne a identifié treize problèmes. Voici leur statut **déclaré**. Une partie de ton travail consiste à vérifier que les correctifs annoncés tiennent réellement dans le code, et que le problème n'est pas réapparu ailleurs.

| Réf | Statut déclaré | Problème |
| --- | --- | --- |
| P0 | corrigé | Routes async avec SQLAlchemy synchrone — bloquaient la boucle d'événements |
| P1 | corrigé | Split brain — `pm.py` v1 et `pm_orchestrator.py` v2 cohabitaient |
| P2 | corrigé | 52 chemins absolus codés en dur |
| P3 | corrigé | Agents lancés via `subprocess.run()` — 3 à 5 s de surcoût par appel |
| P4 | **partiel** | Contrôleur surdimensionné : `pm_orchestrator`, 2 637 lignes |
| P5 | corrigé | Journaux fragmentés |
| P6 | corrigé | 13 modèles LLM codés en dur |
| P7 | corrigé | Transactions non atomiques — 24 `db.commit()` éparpillés |
| P8 | corrigé | Rotation de secrets absente |
| P9 | corrigé | `safe_content()` tronquait 93 à 96 % du contenu |
| P10 | **partiel** | Pas de classe `BaseAgent` commune aux onze agents |
| P11 | corrigé | Santé du RAG silencieuse — pannes non détectées |
| P12 | **partiel** | Deux fichiers `.env` pour la clé OpenAI |

Signale explicitement tout correctif que tu juges incomplet ou contourné. Un problème déclaré résolu qui ne l'est pas est plus dangereux qu'un problème connu.

## Ce que je te demande

Sept axes. Traite-les tous, dans cet ordre.

**1. Ce qui casse en production.** Erreurs non rattrapées, transactions non atomiques, conditions de course, fuites de ressources, blocages de la boucle d'événements, appels bloquants dans du code asynchrone, dépassements de délai non gérés. Pour chacun : le fichier, la ligne, ce qui déclenche la panne, et ce qu'il faut écrire à la place.

**2. Ce qui ne tient pas ensemble.** Références mortes, imports circulaires, points d'API appelés côté frontend qui n'existent pas côté backend, ou l'inverse. Schémas de base incohérents avec le code qui les lit. Fichiers de configuration cités mais absents. Variables d'environnement lues sans être déclarées nulle part. Chemins codés en dur.

**3. Sécurité.** Injection SQL, injection de commandes, traversée de répertoires, désérialisation non sûre. Authentification et autorisation : un utilisateur peut-il accéder aux données d'un autre, ou dépasser les limites de son palier commercial ? Secrets en clair dans le dépôt. Dépendances vulnérables. Exposition de données dans les journaux ou les messages d'erreur.

**4. Cohérence des paliers.** Le palier professionnel ne doit pas pouvoir déclencher la séquence de construction. Le palier gratuit ne doit produire aucun livrable. Vérifie que ces limites sont appliquées côté serveur et pas seulement masquées côté interface.

**5. Passage à l'échelle.** C'est le point sur lequel je veux ton jugement, pas seulement un inventaire.

Le code peut-il monter en charge, oui ou non, et pourquoi ? Où sont les goulots d'étranglement — connexions à la base, file d'attente, ChromaDB, appels aux modèles de langage, stockage de fichiers ? Qu'est-ce qui casse en premier quand le nombre d'utilisateurs augmente ?

Puis donne-moi la configuration nécessaire à quatre paliers, en étant concret sur les dimensions : **10 clients**, **100 clients**, **1 000 clients**, **10 000 clients**. Combien de machines, quelles tailles, quels services à séparer, à quel moment faut-il découpler quoi. Indique ce qui doit être refait avant chaque palier, et ce qui peut attendre.

Au palier de 10 000, je veux que tu ailles au-delà du redimensionnement : quelles limites de l'architecture actuelle ne se corrigent pas en ajoutant des machines ? Chiffre aussi ce que représente le coût d'inférence à ce volume — c'est le poste qui décide de la viabilité du modèle économique, et je préfère le savoir maintenant.

**6. Ce qui manque pour être exploitable.** Absence de journalisation structurée, de métriques, de sondes de santé, de reprise après erreur, de migration réversible. Points où une panne serait invisible ou indiagnosticable.

**7. Dette technique qui coûtera cher.** Duplication de logique, contrôleurs surdimensionnés, absence de contrat entre modules, code mort. Uniquement ce qui gênera réellement l'évolution — pas les questions de style.

## Format attendu

Un rapport en Markdown, structuré ainsi.

**Un verdict d'ouverture, en cinq lignes.** Ce code peut-il partir en production le 1er octobre ? Oui, non, ou à quelles conditions. Sois direct : je préfère un refus argumenté à un accord poli.

**Puis les constats**, un par bloc, avec systématiquement :

- un identifiant court (`SEC-01`, `SCALE-03`…)
- la gravité : **bloquant** (empêche l'ouverture), **majeur** (à corriger sous 30 jours), **mineur** (peut attendre)
- le fichier et la ligne
- ce qui se passe concrètement si ce n'est pas corrigé — pas une formule générique, le scénario réel
- le correctif, avec le code quand il tient en quelques lignes
- l'effort estimé en heures

**Enfin une feuille de route** en trois vagues : avant le 1er octobre, dans les trente jours, puis plus tard. Ordonnée par rapport entre le risque évité et l'effort consenti.

## Règles

Cite toujours le fichier et la ligne. Un constat sans emplacement précis est inutilisable.

Ne signale pas ce que tu n'as pas vérifié dans le code. Si tu soupçonnes un problème sans pouvoir le confirmer, dis-le explicitement plutôt que de l'affirmer.

Ne propose pas de réécriture d'architecture. Le lancement est dans six semaines : je veux des correctifs applicables, pas un projet de refonte.

Si un point te paraît juste — bien fait, correctement traité — dis-le aussi. Savoir ce qui tient m'évite d'y toucher.

Ignore le style, le formatage, les conventions de nommage, sauf s'ils causent un bug réel.

Réponds en français.
