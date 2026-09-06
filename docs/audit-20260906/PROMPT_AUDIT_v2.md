Tu audites le code d'une plateforme SaaS avant sa mise en production, prévue le **1er octobre 2026**. L'éditeur est une personne seule, entrepreneur individuel, mais il dispose d'agents de développement pour appliquer les correctifs en parallèle. Calibre tes recommandations en conséquence : le facteur limitant est le temps d'arbitrage humain, pas le nombre de mains. Ton rapport servira de feuille de route — ce que tu ne signales pas ne sera pas corrigé.

Tu es le **troisième auditeur indépendant**. Le premier (23/08) a produit onze bloquants ; les deux vagues de correctifs qui ont suivi (« vague A » 03/09, « vague B » 05/09) ont été relues et déployées. Tu ne dois **ni refaire cet audit, ni le croire sur parole** : ton rôle est de vérifier que ce qui est déclaré corrigé l'est réellement, et de trouver ce qui a été manqué. Un problème déclaré résolu qui ne l'est pas est plus dangereux qu'un problème connu.

## Ce que fait la plateforme

Onze agents d'IA spécialisés produisent des livrables Salesforce en deux séquences. La première génère un document de spécification (SDS) : un agent cadre le besoin, un deuxième le traduit en exigences, un troisième interroge une base documentaire, un quatrième arbitre les choix techniques, le premier rédige. La seconde séquence (BUILD) produit du code en six phases — modèle de données, Apex, composants d'interface, automatisations, sécurité, migration — avec une relecture qualité avant chaque déploiement.

Pile : FastAPI (`backend/`, port 8002) et PostgreSQL, React/Vite (`frontend/`), ChromaDB pour la recherche documentaire, Redis et ARQ pour les tâches asynchrones et un cron de rétention, Nginx en frontal, Alembic pour les migrations (tête actuelle : `015`). Le routage des modèles de langage est déclaré dans `backend/config/llm_routing.yaml` (profils × tiers × agents) ; le profil actif en production envoie tous les agents sur un modèle local (Nemotron, vLLM, port 18084 via tunnel SSH). Le déploiement Salesforce passe par SFDX.

Trois paliers : **Free** (Sophie + Olivia en dialogue, 50 crédits/jour, modèle local), **Pro** (79 €/mois HT, 15 000 crédits/mois, SDS complet), **Team** (1 490 €/mois HT, BUILD jusqu'au bac à sable). Aucun déploiement automatique en production client. La vérité des paliers est la table `tier_config`, lue par `GET /api/subscription/tiers`.

## Ce qui est déclaré fait depuis le 23/08 — à vérifier

| Réf | Déclaré | Où regarder |
| --- | --- | --- |
| A1 | `httpx<0.28` épinglé ; 118 tests remis en jeu | `backend/requirements.txt`, `backend/tests/` |
| A3/012 | Prix Pro 79 € aux trois endroits (`Pricing.tsx`, `subscription.py`, `tier_config`) | migration `012` |
| A5 | Le concierge public (`sophie_concierge_service.py`) n'atteint pas le RAG — test de garde | `tests/test_vague_a_a5*` |
| A6/B6 | Comptage RAG sorti du chemin de démarrage ; `/health` lit un cache TTL 30 min | `app/main.py` |
| A9 | Fournisseurs LLM locaux sondés au boot (`verifier_fournisseurs_locaux`) ; `model_id` exact envoyé à vLLM | `llm_router_service.py` |
| B1 | `user_id` obligatoire sur tout appel LLM agent ; concierge par `sans_compte=True` ; ligne CRITICAL si une facturation est perdue | `llm_router_service.py`, `pm_orchestrator_service_v2.py` |
| B2/014 | Free routé sur le modèle local, tarifé 0,2/1,0 crédit par 1 000 jetons | `llm_routing.yaml`, migration `014` |
| B3/013 | Consentement CGV obligatoire à l'inscription (`consent_cgv_at`, `consent_version`, `consent_ip_hash`) | `routes/auth.py`, migration `013` |
| B4 | RGPD art. 15/17 : `GET /api/account/export`, `DELETE /api/account` (anonymisation) | `routes/account.py`, `services/account_service.py`, `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md` |
| B5 | Purge `chat_logs` > 12 mois, cron ARQ 03:17 UTC | `app/workers/retention.py`, `worker.py` |
| B7 | Plus aucun chiffre de tier en dur (front, prompts) | `Pricing.tsx`, `sophie_pm.yaml` |
| 015 | Free à 50 crédits/jour | migration `015` |
| Hotfix 05/09 | Un échec LLM ne devient jamais un 200 vide dans le chat Sophie | `sophie_chat_service.py` |

## Ce qui est **connu ouvert** — ne le redécouvre pas, mais vérifie que rien ne l'aggrave

- Douze tables ORM sans migration Alembic : `alembic upgrade head` échoue sur base vierge à la révision `007` (installation on-premise impossible ; le SaaS tourne sur une base existante).
- `max_projects` du Free (0) n'est pas appliqué à la création de projet — seulement dans les routes d'information.
- `audit_logs` stocke l'IP en clair (une demande d'effacement ne l'atteint pas).
- Un chemin machine en dur dans `journal_webhook.py`.
- L'ancien mot de passe PostgreSQL (`DH_SecurePass2025`) figure encore dans 12 fichiers de l'arbre et dans l'historique git. Il a été **rotaté deux fois** (03/09, 05/09) : ce n'est plus une faille active, c'est de la saleté — mais dis-moi si tu trouves un **autre** secret encore valide.
- Démarrage du backend ~90 s (comptage RAG à froid avant l'écoute).
- `pm_orchestrator_service_v2.py` : 3 800 lignes.

## Ce que je te demande

Cinq axes, dans cet ordre. Les axes « passage à l'échelle » et « dette » de l'audit précédent sont hors périmètre aujourd'hui : je veux la **sécurité et la robustesse de ce qui part le 1er octobre**.

**1. Sécurité, en priorité absolue.** Authentification et autorisation : un utilisateur peut-il lire, modifier ou supprimer les projets, exécutions, documents, crédits d'un autre ? Suis chaque route de `backend/app/api/routes/` et vérifie que le filtre `user_id` est appliqué côté serveur, pas seulement côté interface. Injection (SQL, commande, chemin) — les agents écrivent des fichiers et lancent SFDX : par où passe l'entrée utilisateur ? Secrets : tout ce qui ressemble à une clé, un mot de passe, un jeton, dans le code, la configuration, les tests, les scripts, les journaux. Exposition dans les messages d'erreur et les journaux. Dépendances vulnérables (`requirements.txt`, `package.json`). Webhooks Stripe : la signature est-elle vérifiée, le secret rotaté ? CORS, cookies, en-têtes.

**2. Ce qui casse en production.** Erreurs non rattrapées, appels bloquants dans du code asynchrone, transactions non atomiques, ressources non fermées, délais non gérés — en particulier autour des appels LLM (600 s de timeout déclaré), de ChromaDB et du worker ARQ. Repli silencieux : tout endroit où une valeur inconnue ou une erreur est absorbée sans journal ni message.

**3. Cohérence des paliers et de la facturation.** Le Free ne doit produire aucun livrable ni créer de projet ; le Pro ne doit pas déclencher le BUILD ; chaque appel LLM d'un compte doit produire une ligne `credit_transactions` ; le plafond journalier Free et mensuel Pro doivent refuser avec un message, pas laisser passer. Vérifie que `credits_consumed` (entier, arrondi vers le haut) est cohérent avec ce que la page de prix annonce.

**4. RGPD, concrètement.** Compare `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md` aux modèles réels : y a-t-il une table ou une colonne qui porte une donnée personnelle et que l'export ou l'effacement ne couvre pas ? Le consentement est-il exigé sur **tous** les chemins d'inscription (formulaire, OAuth, invitation) ?

**5. Ce qui manque pour être exploitable.** Journalisation, métriques, sondes, reprise après erreur, migrations réversibles — uniquement ce qui rendrait une panne invisible ou indiagnosticable.

## Format attendu

**Un verdict d'ouverture, en cinq lignes.** Ce code peut-il partir en production le 1er octobre pour les paliers Free et Pro ? Oui, non, ou à quelles conditions. Sois direct : je préfère un refus argumenté à un accord poli.

**Puis les constats**, un par bloc, avec systématiquement : un identifiant (`SEC-01`, `PROD-03`…) ; la gravité — **bloquant** (empêche l'ouverture), **majeur** (sous 30 jours), **mineur** ; le fichier et la ligne ; le scénario concret si ce n'est pas corrigé ; le correctif, avec le code quand il tient en quelques lignes ; l'effort en heures.

**Puis, séparément, la table des déclarations vérifiées** : pour chaque ligne du tableau « déclaré fait », ton verdict — *confirmé*, *incomplet* (avec ce qui manque), ou *contourné* (le problème est réapparu ailleurs).

**Enfin une feuille de route** en trois lots : avant le 1er octobre, dans les trente jours, plus tard. Ordonnée par rapport entre le risque évité et l'effort consenti.

## Règles

Cite toujours le fichier et la ligne. Un constat sans emplacement précis est inutilisable.

Ne signale pas ce que tu n'as pas vérifié dans le code. Si tu soupçonnes sans pouvoir confirmer, dis-le explicitement.

Distingue ce que tu as **lu** de ce que tu as **exécuté**. Si tu ne peux rien exécuter, dis-le en tête de rapport.

Ne propose pas de réécriture d'architecture. Le lancement est dans trois semaines : des correctifs applicables, pas un projet de refonte.

Le dépôt fourni est à `main` = `8a74866` (05/09/2026). Les fichiers `.env` en sont exclus volontairement ; les variables attendues sont listées dans `backend/app/config.py`.
