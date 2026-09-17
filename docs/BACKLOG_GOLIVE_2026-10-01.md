# Backlog go-live 1er octobre 2026 — source unique (ouvert le 15/09/2026)

> Ce fichier devient le backlog unique du go-live. Il absorbera, à la revue du 15/09 après-midi,
> les 41 décisions accordées du comité, les 49 tâches `a_faire` et les 58 constats de l'audit Astra
> (docs/audit-20260906/rapport-astra.md). Une entrée = un défaut mesuré (commande, date), pas une impression.
> Périmètre décidé par Sam le 15/09 : ouverture **Free + Pro** le 1er octobre.
> Statuts : ❌ à faire · 🟡 en cours / à valider · ✅ fait (avec preuve).

## 1. Bugs découverts par la calibration SDS sur modèles locaux (15/09, exécution 172, Muse Glimmer 30B)

| Id | Sévérité | Constat (mesuré) | Correctif attendu | Statut |
|---|---|---|---|---|
| CAL-01 | Haute | `worker.py` : `job_timeout = 3600` constante globale. Le job de reprise de l'exec 172 (démarré 09:24:31) a été annulé à 10:24:31 en plein appel de Marcus (« Patching architecture, attempt 1 »). Un 30B local à 12 tok/s ne tient pas 1 h. | Rendre le délai dépendant du profil de routage (cloud vs gpu_local) ou du modèle ; ne pas annuler un job dont un appel LLM est en cours de réponse. | 🟡 porté à 21600 pour la calibration (commentaire dans worker.py) — **à rendre configurable et à remettre à 3600 pour le profil cloud** |
| CAL-02 | Haute | Une exécution tuée par CAL-01 reste `RUNNING` / `sds_phase3_running`, sans erreur visible, jusqu'au prochain redémarrage du worker (`[Startup] Found stuck execution`). Un client Pro verrait « en cours » indéfiniment. | Sur `TimeoutError` / `CancelledError` du job : passer l'exécution en FAILED avec message explicite, notifier, libérer les crédits réservés. | ❌ |
| CAL-03 | Moyenne | La route `POST /execute/{id}/resume` ne connaît que `phase2_ba` pour une exécution FAILED, alors que `last_completed_phase` (= `phase2_5_emma` pour 172) et `execute_workflow(resume_from="phase3")` permettent de reprendre sans rejouer Sophie/Olivia/Emma. Repris à la main le 15/09 via `pool.enqueue_job(..., resume_from='phase3', _queue_name='digital-humans')`. | `_determine_resume_point()` doit dériver le point de reprise de `last_completed_phase`. | ❌ |
| CAL-04 | Basse | Machine à états : à la reprise en phase 3, `[StateMachine] transition failed: sds_phase3_running → queued` puis `→ sds_phase3_running` (refusées, non bloquantes). | Autoriser la transition de reprise ou remettre l'état à `queued` avant l'enqueue. | ❌ |
| CAL-05 | Basse | `tasks.py` ignore comme « fantôme » tout job dont l'exécution est FAILED — correct pour les jobs orphelins, mais empêche une reprise explicite depuis FAILED sans passer par la route. | Distinguer job orphelin et reprise demandée (drapeau `resume_from`). | ❌ |
| CAL-06 | Info | Débit mesuré Muse Glimmer 30B Q8 + DFlash sur Spark (llama.cpp) : 12,4 tok/s génération, ~460 tok/s ingestion. Phase 1 Sophie 20 min (4 738 tokens), phases 1→2.5 ≈ 1 h 35. Qualité phase 1 : 20 BR atomiques, fidèles au brief, rien d'inventé. | Alimente D2 (modèle Pro). Résultats complets 15-16/09 (4 SDS, 2 conditions) dans `/root/workspace/site-work/sds-calibration/README.md` ; les 4 SDS sont publiées (#176-179) et branchées dans « The Work ». Suite éventuelle : Nemotron, Qwen3.8, gpt-oss-120b sur un même brief. | ✅ calibration v1 faite |
| CAL-07 | Moyenne | Les routes `/resume` et la reprise d'architecture enfilent toujours sur la file `digital-humans` : impossible de reprendre une exécution sur un autre worker/profil (mesuré 15/09 : 174 repris sur Muse au lieu de DeepSeek Flash). Aucune annulation de job (`allow_abort_jobs` absent), aucun point d'arrêt coopératif dans `execute_workflow` : seul un redémarrage du worker interrompt une exécution, et il tue toutes les autres. | Mémoriser file/profil sur l'exécution (colonne) et les réutiliser à la reprise ; ajouter une annulation coopérative entre agents ; activer `allow_abort_jobs`. | ❌ |
| CAL-08 | Moyenne | Revue de couverture d'Emma : sur l'exec 175 (GLM 5.3 Flash), 81 « manques critiques » dont la grande majorité sont des **variantes terminologiques d'objets déjà présents** (`credit_note__c` pour un avoir, `mouvement_points__c`, `ligne_retour_ecommerce__c`…) ; sur 172/174, « objet Flow manquant » (un Flow n'est pas un objet), `actif__c` alors qu'Asset 360 fournit `Asset`. Deux défauts distincts : (1) Emma compte comme manque une divergence de nom au lieu de rapprocher par sens (récidive EMMA-COV-001, faux positifs) ; (2) Marcus/Olivia inventent des objets custom en français qui doublonnent des objets standard — pas de discipline de nommage. | (1) Emma : rapprochement sémantique objet référencé ↔ objet existant (nom, libellé, champs) avant de déclarer un manque ; distinguer « manque » de « renommage » ; ne jamais classer un métadonnée (Flow, Report, Queue) comme objet manquant. (2) Prompts Marcus/Olivia : règle explicite « réutiliser l'objet standard ou existant ; un objet custom se justifie et se nomme en anglais API ». Test : rejouer le brief 117 et compter les manques après correctif. | ❌ |
| CAL-09 | Moyenne | Score de couverture après révision = **85,0 % exactement** sur les quatre exécutions révisées (174, 176, 177, 178), avec des nombres de manques différents (10, 14, 20, 49). Quatre valeurs identiques ne sont pas une mesure : plafond, seuil ou valeur cible renvoyée par le code d'Emma / la boucle de révision. | Lire le calcul du score après révision ; s'assurer que la valeur affichée est mesurée, pas assignée ; sinon corriger et rejouer une révision pour vérifier. | ❌ |
| CAL-10 | Moyenne | Durée d'un SDS dominée par la structure, pas par le modèle : appels séquentiels (phase 4 : apex, lwc, admin, qa, devops, data, trainer enchaînés alors qu'indépendants), sorties JSON de 30-50 Ko par appel, raisonnement toujours activé. Mesuré 15/09 : phases 1-3 en ~20 min sur DeepSeek V4 Flash, chaque appel Marcus 2-3 min. | (1) Exécuter les agents de phase 4 en parallèle (asyncio.gather, plafond de concurrence par fournisseur) ; (2) `reasoning_effort` configurable par agent dans llm_routing.yaml (bas pour les workers, haut pour Marcus) ; (3) mesurer avant/après sur le même brief. | ❌ |
| CAL-11 | Haute | Au démarrage, chaque worker marque FAILED **toutes** les exécutions RUNNING (`[Startup] Found stuck execution … marking as FAILED`), sans vérifier qu'elles lui appartiennent. Mesuré 15/09 18:0x : le redémarrage des trois workers de calibration a basculé 179 (en cours dans le worker principal) en FAILED alors que son job continuait. Avec plusieurs workers (ou un redéploiement pendant un run), état incohérent garanti. | Ne nettoyer que les exécutions dont le job arq est réellement absent/mort (vérifier le job dans Redis, ou un heartbeat par exécution), jamais sur le seul statut. | ❌ |
| GL-11 | **Bloquant** | `tools/lib/collect_sds.py::_db_conn()` : mot de passe Postgres en dur (`DH_SecurePass2025!`), périmé depuis la rotation SEC-01 du 06/09 → **phase 5 (assemblage du SDS) en échec pour toutes les exécutions depuis dix jours**. Mesuré 15/09 sur 176/177/178. Corrigé `f297bb3` (DSN depuis DATABASE_URL, erreur explicite sinon). Le même secret par défaut traîne encore dans `blog.py`, `document_generator.py`, `sds_template_generator.py` et trois tests. | Purger tous les secrets par défaut du dépôt (grep `DH_SecurePass`) ; ajouter un test de non-régression « aucun secret en dur » ; ajouter la phase 5 au smoke test post-déploiement (elle n'y est pas — sinon la rotation du 06/09 l'aurait cassée visiblement). | ✅ purgé `a1c…` (blog, document_generator, sds_template_generator, 3 tests), test `test_no_hardcoded_secrets.py` (rouge/vert vérifié), smoke test assertion 6 = build_sds(146) > 100 ko |
| GL-12 | Moyenne | Le gabarit SDS (`tools/templates/sds_shell.html.j2` et partiels) n'existe qu'en anglais : phrases narratives fixes (« Olivia produced N use cases… », « This is a greenfield project… ») injectées dans un document dont tout le contenu généré est en français. Mesuré 15/09 sur #176/#177 : ~4 % des segments en anglais, tous issus du gabarit, 0 issu des modèles. Le gabarit contient aussi la phrase « The DATA_MODEL gaps are likely false positives — the validator is matching on raw object names », qui expose au client le défaut CAL-08. | Gabarit bilingue piloté par la langue du projet (FR par défaut pour un brief FR) ; retirer la phrase d'excuse une fois CAL-08 corrigé. | ❌ |
| GL-13 | Haute | Aucun canal de support client défini pour l'ouverture (DEC-0802-04 : Email-to-Case Salesforce, jamais mis en place). | Décidé 16/09 : **Email-to-Case** (Service Cloud) + alias `support@digital-humans.fr` redirigé vers l'adresse de routage Salesforce ; CGV : délai de réponse à afficher. Reste : org cible, activation, test d'un ticket de bout en bout. | 🟡 |
| GL-14 | Moyenne | Clé de la sauvegarde chiffrée quotidienne stockée dans `/etc/dh-backup` sur le même hôte (DEC-0808-10). | Copier la clé hors VPS (coffre Sam + copie chiffrée), documenter la restauration, tester une restauration à blanc. | ❌ |
| GL-15 | Basse | Supervision N8N « Monitoring Services » : 1 350 exécutions, 0 succès (DEC-0811-05). | Réparer si utile, sinon retirer le workflow ; ne pas laisser une supervision qui échoue en silence. | ❌ |
| GL-16 | Haute | Rétention des conversations Sophie : 90 jours tranchés (DEC-0813-02 / 0817-04) ; le code (`chat_log.py`) ne purge pas, la politique de confidentialité doit dire la même chose (lié RGPD-04 : la promesse « zero data retention » du Free est fausse). | **Décision Sam 16/09 : 90 jours, sauf besoin de fonctionnement** (une durée plus courte reste possible si le fonctionnement l'impose, à documenter). Durée lue dans `DH_RETENTION_CONVERSATIONS_JOURS` (file D). Reste : poser 90, aligner politique de confidentialité et CGV, retirer ou rendre vraie la promesse ZDR du Free. | 🟡 |
| GL-17 | Moyenne | Onze contenus marketing écrits, aucun publié (DEC-0814-02) ; le journal Ghost existe. | Sam choisit les 3 premiers ; publication Ghost + lien depuis le site ; cadence après ouverture. | 👤 puis ❌ |
| GL-18 | Basse | Trois compteurs faux sur l'écran d'exécution (DEC-0815-02, = PROD-10 partiel). | Corriger l'affichage (tokens, coût, durée) depuis `llm_interactions`. | ❌ (AS-09) |
| GL-19 | **Bloquant** | Mentions IA article 50 absentes de **l'application** (widget concierge, fenêtres Studio, pied de livrable) — DEC-0817-03 / TASK-0823-01 ; obligation en vigueur depuis le 02/08/2026. Le site est conforme depuis le 15/09. | Bandeau « vous échangez avec une IA » au premier contact dans le widget et le Studio ; mention « contenu généré par IA » en pied de chaque livrable et dans les métadonnées Word/PDF/HTML ; test Chromium. | ❌ |
| GL-20 | **Bloquant** | Webhook Stripe : avec le SDK installé (15.1.0), le chemin `event["data"]["object"].get(...)` lève `AttributeError` sur **tout** événement réel → HTTP 500, aucun abonnement n'ouvre l'accès. Vérifié par Claude le 16/09 sur le VPS (contre-épreuve : code d'avant = `AttributeError get` ; code de la file B = insertion de l'événement en base). Le parcours Pro ne pouvait pas fonctionner au 1er octobre. | Corrigé par la file B (PR #12) : accès aux champs sans `.get`, journal `stripe_events` idempotent, reconciliation, délai de grâce impayé. Rejoué de bout en bout sur le VPS le 17/09 : checkout → carte de test → `customer.subscription.created` **appliqué** → palier `pro`, 15 000 crédits, `/api/billing/balance` renvoie `tier: pro` ; 6 événements journalisés ; renvoi d'un événement par Stripe (15:24:25) → 200, marqué `duplicate`, aucune ligne en plus, crédits inchangés. | ✅ |
| GL-21 | **Bloquant** | Aucun des trois modèles servis par le profil `cloud` (`claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001`) n'a de ligne dans `model_pricing` ; le code retombe sur un tarif par ressemblance (mesuré : `modele-jamais-vu → 3.0/15.0`). Tout le trafic cloud était facturé au tarif d'une génération antérieure. Vérifié par Claude le 16/09. | File B (PR #12) : refus des modèles inconnus + migration `016_tarifs_modeles_servis`. Migration `016_tarifs_modeles_servis` appliquée en prod le 17/09 : `claude-opus-5`, `claude-sonnet-5`, `claude-haiku-4-5-20251001` présents avec leurs paliers. Reste la vigilance à chaque changement de modèle. | ✅ |
| GL-22 | Haute | Consentement Opus au palier Pro : le site promet « Opus on opt-in, cost shown before each call » ; ouvrir Opus à Marcus sans écran de recueil ferait mentir la page de prix. **Décision Sam 16/09 : on ajoute le recueil.** | Écran de consentement avec coût estimé avant appel Opus, trace du consentement, refus = repli Sonnet annoncé. À caler en vague 2 (file D). | ❌ |
| GL-23 | **Bloquant** | Écart de prix Pro : Stripe facture **49 €/mois** (`price_1TRW5X2U0jLqzz5TWvNKYxow`, sandbox) alors que le site annonce **79 € HT/mois**. Mesuré le 17/09 pendant la souscription de bout en bout — la page de paiement affiche « Subscribe to Pro €49.00 per month ». **Décision Sam 17/09 : on reste à 79 €.** Fait en sandbox le 17/09 : prix `price_1UGhEN2U0jLqzz5TGaGQ7m58` créé à 79 €/mois, posé en prix par défaut du produit Pro, ancien prix 49 € désactivé, `STRIPE_PRICE_ID_PRO` mis à jour (sauvegarde `env.pre-prix-pro-79-20260917`), backend redémarré ; page de paiement vérifiée : « Subscribe to Pro €79.00 per month ». Team déjà à 1 490 €, correct. **Reste : refaire exactement la même opération sur le compte Stripe de production** avant l'ouverture. | 🟡 |
| GL-24 | Basse | `robots.txt` n'existait pas : la requête retombait sur la SPA (page Entracte, puis le site entier). Créé le 17/09 (`/var/www/dh-preview/robots.txt`) : tout autorisé sauf `/apercu-recent/`, `/holding-preview/`, `/sds-preview/`, avec le sitemap. | Vérifier que les SDS du portfolio doivent bien rester hors index (liens partagés, pas de référencement). | 🟡 |
| GL-25 | **Bloquant** | Le compte **Anthropic** n'a plus de crédits : un échange Pro renvoie `400 — Your credit balance is too low to access the Anthropic API` (mesuré 17/09, compte smoke en palier `pro`, HTTP 502 côté API). Le palier Pro — Sonnet + Marcus en Opus — ne peut pas fonctionner. Même classe que GL-10 (OpenAI épuisé le 15/09) : **deux paliers payants dépendent de soldes que personne ne surveille**. **Contrainte de trésorerie (Sam, 17/09) : recharge impossible avant la fin du mois ; smoke Pro reporté à fin septembre.** Conséquence à arbitrer : le palier Pro ne peut pas être vendu tant que le solde Anthropic est vide — voir la décision de périmètre ci-dessous. À faire quand le solde est rechargé : rejouer le smoke Pro, puis poser une alerte admin sous seuil (même mécanique que GL-10) et un refus explicite côté client plutôt qu'un 502. | 👤 fin sept. |
| GL-26 | Basse | Persona : interrogée sur son rôle, **Olivia répond « En tant que Project Manager senior »** — c'est le rôle de Sophie ; Olivia est architecte de solution. Mesuré 17/09 sur le parcours Free. | Vérifier le prompt système par agent dans le chat Studio (l'agent demandé et le profil chargé ne correspondent peut-être pas). | ❌ |

## 2. Constats du 15/09 hors calibration (bloquants ou à traiter avant l'ouverture)

| Id | Sévérité | Constat (mesuré) | Correctif attendu | Statut |
|---|---|---|---|---|
| GL-01 | **Bloquant** | `backend/.env` : `DH_DEPLOYMENT_PROFILE=test_gpu_complet` en prod (environnement des processus backend PID 2425519 et worker, journal 12/09 « profile=test_gpu_complet, build_enabled=True »). Tout est routé sur le GPU local ; un client Pro aurait Nemotron, pas Sonnet/Opus. Commentaire « À RETIRER après la validation » présent. | Smoke **Free vérifié le 17/09** : inscription par le parcours réel (consentements CGV/confidentialité exigés, courriel de confirmation envoyé par SMTP), échange avec Sophie puis Olivia, **servi par Nemotron sur le Spark** (compteur vLLM 148 → 288 tokens). Smoke **Pro en échec** : voir GL-25 (crédits Anthropic épuisés). | 🟡 |
| GL-02 | **Bloquant** | Mentions légales digital-humans.fr : numéro de TVA intracommunautaire `[À COMPLÉTER]`. VIES répond INVALID pour FR28343172490 ; la fiche Guichet Unique du 19/05 dit « franchise en base ». Facturer 79 € HT + TVA sans assujettissement = erreur de facturation dès la première vente. | Mentions légales affichent « en cours d'attribution » / « application in progress » depuis le 17/09 (décision Sam du 16/09). Reste : injecter le numéro dès réception, et vérifier la cohérence avec la facturation Stripe. | 🟡 |
| GL-03 | ✅ | Relecture faite par Sam le 16/09 au soir, clauses validées. (Historique) Relecture juridique des clauses IA (AI Act art. 50) ajoutées le 15/09 sur les trois sites (mentions légales + CGV §6 DH ; `/legal` et `/privacy` DEOS et SH Conseil). Rédigées par Claude, pas par un juriste. | Relecture par un professionnel avant le 1er. | ❌ (action Sam) |
| GL-04 | Moyenne | Trois sites chargent Google Fonts (transfert IP vers Google LLC, déclaré dans les politiques de confidentialité). | Auto-héberger Cormorant / Inter / JetBrains Mono sur les trois sites, puis retirer le paragraphe « Polices » des politiques. | ❌ |
| GL-05 | Moyenne | Bundle digital-humans.fr : Babel « in-browser » sur 16 Mo ; un bloc CSS collé dans un script JSX le 30/08 a rendu le site et `/cgv` `/legal` `/privacy` noirs pendant 16 jours sans que personne ne le mesure (corrigé 15/09, `index.html.pre-fix-css-20260915`). | Contrôle Chromium automatique (console vide + texte rendu) après chaque modification du bundle ; envisager le bundle précompilé pour l'ouverture. Outils : `/root/workspace/site-work/pack.py`, `/tmp/chk_apercu.py`. | ❌ |
| GL-06 | Basse | nginx : `sites-enabled/` contient des copies `.pre-*` chargées par `include sites-enabled/*` (avertissements « conflicting server name »). `/var/www/digital-humans.fr/` contient des SDS clients, une archive de livrables et un `login-test.html` (non servis — vhost ailleurs — mais à sortir de `/var/www`). `/test-site/` et `/apercu-recent/` accessibles sans mot de passe. | Déplacer les `.pre-*` hors de `sites-enabled`, nettoyer `/var/www/digital-humans.fr/`, retirer `/test-site/` à la bascule. | ❌ |
| GL-07 | Basse | Spark : ComfyUI, vox-tts, lobe-chat se relancent au démarrage et occupent de la mémoire unifiée en permanence (mesuré après le redémarrage du 15/09 : 50 Go utilisés avant chargement des modèles). | Décider ce qui tourne au boot ; désactiver le reste. | ❌ |
| GL-08 | Basse | `model_pricing` : lignes `muse-glimmer`, `qwen38`, `gpt-oss-120b` ajoutées à la main le 15/09 (palier team) pour la calibration ; `credit_balances` admin (user 2) initialisé à 100 000 (palier Team, était 0). | Migration Alembic si un modèle local est retenu ; sinon supprimer les lignes de calibration. | 🟡 |
| GL-09 | Info | Comité DEOS : cron rituels suspendus le 15/09 (`/etc/cron.d/dh-comite-rituels`, sauvegarde `dh-comite/dh-comite-rituels.pre-suspension-20260915`). Retour conditionné : une décision accordée = une branche + un test. | Traité dans la revue backlog/curseur. | 🟡 |
| GL-10 | **Bloquant** | Le RAG documentaire (collections technical / operations / business, embeddings OpenAI `text-embedding-3-large`) est tombé silencieusement toute la journée du 15/09 : `429 credit_balance_exhausted` sur le compte OpenAI, 146 requêtes RAG échouées (worker principal dès 09:24, workers de calibration dès 12:16). Les agents continuent sans corpus avec un simple avertissement — repli silencieux. Recrédité 5 € par Sam à 13:4x. | (1) Alerte **admin** (Telegram + journal + tableau de bord admin) dès la première collection RAG injoignable — pas de message au client (précisé par Sam le 15/09), mais l'exploitant doit le savoir dans la minute, avec l'exécution concernée et la cause ; la poursuite sans corpus est tolérée mais tracée sur l'exécution (`degraded: rag_unavailable`) pour pouvoir rejouer ensuite ; (2) surveillance du solde OpenAI ou bascule des embeddings sur un modèle local (re-indexation à chiffrer) ; (3) le contrôle de santé `[RAG HEALTH] OK` ne teste pas l'API d'embeddings — le corriger. | ❌ |

## 3. Fusion des trois sources (revue du 16/09) — tri proposé, à valider par Sam

Légende : ✅ fait (preuve) · ⛔ périmé (comité suspendu ou dépassé par Astra) · 🔀 fusionné dans une ligne CAL/GL/AS · 👤 décision ou action de Sam · ⏩ plus tard (après le 1er) · ❌ à faire avant le 1er

### 3.1 — 41 décisions accordées du comité (02/08 → 23/08)

| Décision | Objet | Tri | Où |
|---|---|---|---|
| DEC-0802-04 | Rationalisation support sur Salesforce (Email-to-Case, Knowledge) — canal de tickets client | ❌ | GL-13 canal support avant ouverture (Email-to-Case ou boîte hello@ + procédure) |
| DEC-0802-01 | Démo phare Agentforce → DH → sandbox | ⏩ | Lot 3 Astra (BUILD) |
| DEC-0802-02 | BUILD reprise sur incident | ⏩ | = PROD-13, Lot 3 |
| DEC-0802-06 | Mission juridique — audit RGPD du parcours complet | 🔀 | rapport juridique 08/08 rendu ; reste = RGPD-01..04 (AS-06, Lot 2) |
| DEC-0802-03 | BUILD travail incrémental (delta) | ⏩ | Lot 3 |
| DEC-0804-02 | Suivi des 8 chantiers O2 (produit prêt 31/08) | ⛔ | dépassé par l'audit Astra du 06/09 |
| DEC-0804-05 | Mission collective interface web globale | 👤 | Sam décide si l'admin dashboard actuel suffit au lancement |
| DEC-0804-01 | Fiabilisation exécution, journalisation uvicorn | ✅ | commit c3e534c |
| DEC-0805-01 | Offre canonique grands comptes (offre_dh.md) | ✅ | à relire une fois, cohérence avec le site (Enterprise sur devis) |
| DEC-0806-09 | Offre intégrateur (12 intégrateurs FR) | ⏩ | après ouverture ; fiches déjà en base |
| DEC-0806-08 | Audit de sécurité des accès, secrets → coffre | 🔀 | rotation faite (SEC-01 06/09), purge faite (GL-11 16/09) ; reste coffre = SEC-17 (AS-10) |
| DEC-0806-14 | Opportunité DEOS Crédit Logement — présentation DSI | 👤 | Sam (commercial) |
| DEC-0808-01 | Audit légal des deux sites vitrines | ✅ | pages légales DEOS + SH Conseil, 15/09 |
| DEC-0808-10 | Clé de sauvegarde à l'abri (hors /etc/dh-backup) | ❌ | GL-14 — 30 min ops |
| DEC-0808-08 | Relecture Elena étendue à tout ce qui part chez le client | ⏩ | après ouverture |
| DEC-0809-05 | Sécurité des données clients B2/B3 | 🔀 | = SEC-04/05/06/19 → AS-03, AS-06 |
| DEC-0809-01 | Réouverture du site (GO conditionnel du 08/08) | 🔀 | = bascule C.9, conditionnée à GL-02/GL-03 |
| DEC-0809-04 | Hygiène du dispositif comité (garde-fou) | ⛔ | comité suspendu ; à reprendre avec la règle du curseur |
| DEC-0809-08 | Concurrent NAAIA identifié | ✅ | ajouté au business plan v3 §5.2 le 16/09 : AIMS ISO 42001, Série A 6 M€ Ventech (07/2026), 9 M€ levés — couche de conformité, pas de fonction opérée ; partenaire naturel plutôt que concurrent frontal de DEOS |
| DEC-0809-10 | Carte bancaire à l'inscription, y compris Free | 👤 | décision produit go-live (Stripe sur le Free ?) — Sam |
| DEC-0809-07 | GPU et souveraineté (rester sur le Spark) | ✅ | tranché, calibration 15/09 confirme la voie locale possible |
| DEC-0810-23 | Tableau de bord comité périmé après exécution manuelle | ⛔ | comité |
| DEC-0810-02 | Compte d'organisation Digital-Humans (GitHub org, Anthropic, Hostinger…) | 👤 ⏩ | Sam, après ouverture |
| DEC-0810-08 | Marketing : production de contenu | 🔀 | = DEC-0814-02 |
| DEC-0810-05 | Conduite du rituel CEO | ⛔ | comité |
| DEC-0810-22 | Notification des décisions en attente | ⛔ | comité (à reprendre avec la règle du curseur) |
| DEC-0810-11 | Déploiement entièrement local chez le client | ⏩ | Enterprise |
| DEC-0811-01 | Écart de traçabilité PROP-0805-01 | ✅ | corrigé le 11/08 |
| DEC-0811-05 | Supervision N8N hors service : réparer ou retirer | ❌ | GL-15 — à vérifier puis retirer si toujours 0 succès |
| DEC-0811-10 | Documents Trust Center Hostinger (butoir 22/08 dépassé) | 👤 | Sam, accès nominatif |
| DEC-0811-04 | Ce que chaque cran du curseur tient réellement (support Crédit Logement) | 👤 | Sam / DEOS commercial |
| DEC-0811-02 | Garde-fou du comité, faux négatifs | ⛔ | comité |
| DEC-0812-01 | Chiffrage B3 cloisonnement RAG/DB (RLS) | 🔀 | = SEC-04 → AS-06 |
| DEC-0813-02 / 0817-04 | Rétention des conversations Sophie : 90 jours tranché, code à aligner (chat_log.py) | ❌ | GL-16 — cron de purge + politique de confidentialité alignée (lié RGPD-04) |
| DEC-0813-03 | Intégration/déploiement des 3 sites | 🔀 | = bascule C.9 |
| DEC-0814-02 | Pipeline de publication marketing (11 contenus, 0 publié) | ❌ | GL-17 — publier via Ghost (journal) avant/au lancement ; Sam choisit les 3 premiers |
| DEC-0815-02 | Trois compteurs faux sur l'écran d'exécution | ❌ | GL-18 — UX, petit, = PROD-10 partiel |
| DEC-0817-03 | Mentions IA art. 50 **dans l'application** (widget concierge, Studio, pied de livrable) | ❌ | GL-19 — obligatoire depuis le 02/08 ; le site est fait (15/09), l'app pas encore |
| DEC-0817-05 | Journalisation BUILD | ⏩ | Lot 3 |
| DEC-0823-03 | Suivi tasks/preflight | ⛔ | comité |

Bilan : 6 faites · 9 périmées · 9 fusionnées · 7 à Sam · 7 plus tard · **7 à faire avant le 1er (GL-13 à GL-19)**.

### 3.2 — 49 tâches `a_faire`

44 sont du bruit de rondes (suivis, « vérifier l'initialisation du reporting » ×8, « Test task ») : **à archiver en bloc** (`statut = perimee`, motif « comité suspendu 15/09 »). Cinq ont un contenu :

| Tâche | Objet | Tri |
|---|---|---|
| TASK-0823-01 | Mentions IA art. 50 dans le code | 🔀 GL-19 |
| TASK-0826-02 | Traiter le lot de 30 contacts Growth non qualifiés | 👤 Sam |
| TASK-0905-01 + 7 doublons | Reporting quotidien des dépenses (API, GPU) | ⏩ fonction DEOS ; pour le go-live, GL-08 (tarifs) suffit |
| TASK-0822-02, 0906-03 | Outillage comité (CLI, preflight yaml) | ⛔ comité |
| TASK-0905-03 | WebSearch pour le growth | ⛔ comité |

### 3.3 — 58 constats Astra (06/09), par lot d'Astra

**Lot 1 — avant le 1er octobre** (ordre d'Astra, effort/risque) :

| AS | Chantier Astra | Constats | État 16/09 |
|---|---|---|---|
| AS-01 | Révoquer les secrets, fermer les surfaces internes | SEC-01/02/11 | ✅ SEC-01/02 (cc89ca8), GL-11 purge ; **SEC-11 (blog public → dépenses, injection CLI) à faire** |
| AS-02 | Environnement de correction sûr | OPS-05 | ✅ PR #11 fusionnée 16/09 (fbc5f60) : base par exécution (rôle `dh_test` CREATEDB, DSN dans `/root/.dh_test_db.env`), `.env.test` seul lu, secrets factices, garde réseau comptée, Redis/file/Chroma/sorties isolés ; 24 tests dont 4 contrôles négatifs, rouges sur la base (6 failed / 12 errors), verts sur le VPS ; suite 671→694 passés, les 31 rouges préexistants inchangés (→ OPS-06, AS-11) |
| AS-03 | Fuites interclients à correctif court | SEC-05/06/19, puis SEC-12 | ❌ |
| AS-04 | Contenus actifs et sorties réseau | SEC-09/10/15, SEC-03 | ❌ |
| AS-05 | Fermer toutes les écritures BUILD pour Free/Pro | SEC-08, BILL-05 | ❌ |
| AS-06 | Sécuriser le RAG avant données réelles | SEC-04, PROD-09, RGPD-03 | ❌ (absorbe DEC-0809-05, 0812-01) |
| AS-07 | Grand livre et Stripe | BILL-01/04/08/09/10 | ❌ (BILL-08 « modèles inconnus tarifés par ressemblance » = GL-08) |
| AS-08 | Stabiliser LLM, jobs et reprises | PROD-01/07/12 + hotfix | ❌ — **absorbe CAL-01/02/03/04/05/07/11** (PROD-04/05/06 confirmés par la calibration) |
| AS-09 | Parcours réellement vendus | BILL-06/07/11, PROD-10/11, OPS-09 | ❌ (absorbe GL-18) |
| AS-10 | Dépendances, posture de déploiement, sondes | SEC-17/18, OPS-01/02/08 | ❌ (OPS-01 = GL-10, absorbe DEC-0806-08 coffre) |
| AS-11 | Recette indépendante de fermeture | OPS-06 | ❌ — clôture du lot |

**Lot 2 — 30 jours après l'ouverture** : RGPD-01/02, OPS-04, SEC-14/16, OPS-07, PROD-06/08 (si retirés du lancement), SEC-13 + BILL-09, OPS-06 (reste).
**Lot 3 — avant activation des fonctions** : BUILD/Team (SEC-03/07/08, PROD-13/15), testeur interne (SEC-02), notifications (OPS-03), Alembic vierge, nettoyage routeurs morts.

### 3.4 — Les trois décisions humaines qu'Astra demande (inchangées)
1. Périmètre exact ouvert et fonctions explicitement fermées → **Free + Pro, BUILD fermé** (Sam, 15/09) ✅
2. Modèle Pro et promesse correspondante → Sonnet + Marcus Opus (site) ; la calibration ouvre la voie DeepSeek V4 Flash pour les workers — **à arrêter avant la recette finale** 👤
3. Politique de conservation des données personnelles → 90 jours tranchés (DEC-0813-02) ; **code à aligner** (GL-16) 👤 pour les pièces

## 3.5 — Décision de périmètre à prendre avant le 30/09 (ajoutée le 17/09)

Le palier Pro suppose un solde Anthropic disponible **le jour de l'ouverture** : un client qui paie 79 € et reçoit un 502 est pire que pas de client. Le Free, lui, tourne sur le Spark et ne coûte rien à l'appel. Trois voies, à trancher par Sam :

| Voie | Ce qu'on ouvre le 1er | Ce que ça suppose | Risque |
|---|---|---|---|
| **A — Free seul le 1er, Pro quand le solde le permet** | Free (Nemotron, coût marginal nul) + liste d'attente Pro | Rien de plus ; le site annonce Pro « bientôt » comme aujourd'hui pour Team | Aucun risque client ; retarde le premier euro |
| **B — Pro ouvert, solde rechargé avant le 1er** | Free + Pro | Une recharge Anthropic suffisante pour absorber les premiers clients (2 SDS/mois inclus par client) | Si le solde tombe pendant le mois, panne visible chez un client payant |
| **C — Pro ouvert sur modèles à bas coût** | Free + Pro, workers sur DeepSeek V4 Flash (ModelArk), Marcus seul sur Opus | Décision D2 anticipée ; calibration du 15/09 : SDS complet à ~1,50 $ contre ~9,75 $ voie Anthropic | Qualité mesurée 85 % de couverture, acceptable ; dépendance à un fournisseur hors UE à assumer contractuellement |

Rappel des mesures du 15/09 (coût d'un SDS complet) : Muse Glimmer local ≈ 0 $ · DeepSeek V4 Flash ≈ 1,50 $ · DeepSeek V4 Pro ≈ 2,40 $ · GLM 5.3 ≈ 0,55 $ · voie Anthropic (Sonnet + Marcus Opus) ≈ 9,75 $.

## 4. Plan d'action à quinze jours (16 → 30 septembre) — validé sur le tri du 16/09

Principe : quatre files parallèles (Astra) — **sécurité**, **crédits/Stripe**, **pipeline/reprise**, **parcours/recette** — chacune une branche `claude/vague-<n>-<file>`, un prompt de mission Claude Code avec la discipline de preuve, un intégrateur par fichier partagé. Rien n'est « fait » sans commande, sortie, date. Go/no-go le **30/09**.

| Vague | Dates | Contenu | Sortie attendue |
|---|---|---|---|
| **0 — préalables** | 16-17/09 | AS-02 environnement de correction sûr (base/file/clés de test isolées, garde OPS-05) · bascule du site dès relecture juridique (C.9 irréversible + GL-04 polices) · GL-14 clé de sauvegarde · GL-15 N8N · archivage des 47 tâches ✅ | Les vagues peuvent toucher le code sans risque pour la prod ; le site est ouvert |
| **1 — quatre files** | 18-22/09 | **Sécurité** : AS-01 reste (SEC-11), AS-03, AS-04, AS-05 · **Crédits/Stripe** : AS-07 (BILL-01/04/08/09/10) · **Pipeline** : AS-08 absorbant CAL-01/02/03/04/05/07/11, GL-10 alerte admin RAG, CAL-08/09 Emma · **Parcours** : AS-09 + GL-18, **GL-19 mentions IA app**, GL-16 rétention 90 j | Chaque file : tests rouge→vert enregistrés par constat ; PR par file |
| **2 — consolidation** | 23-26/09 | AS-06 RAG cloisonné · AS-10 dépendances, debug off, sondes worker/LLM, alerte de bout en bout · GL-13 support · GL-17 publication des 3 contenus · GL-12 gabarit SDS FR si le temps le permet · D2 : décision modèle Pro (Sonnet+Opus vs Flash workers) sur les mesures de la calibration | Prod déployable ; supervision réelle ; contenu en ligne |
| **3 — recette et gel** | 27-30/09 | AS-11 recette indépendante (tests négatifs/positifs, deux tenants, artefact exact) · smoke test Free (Nemotron) + Pro (Sonnet) sur la prod (GL-01 reste) · gel du code le 29/09 · go/no-go 30/09 sur preuves | Décision d'ouverture documentée |
| Après le 1er | oct. | Lot 2 Astra (30 jours), CAL-10 phase 4 parallèle + `reasoning_effort`, calibration suite (même brief, 4 modèles), Lot 3 (BUILD/Team) | — |

**Décisions de Sam avec date :** TVA (GL-02) — en cours, « en cours » affiché en attendant · relecture juridique (GL-03) — 16/09 soir · canal support (GL-13) — avant le 20/09 · carte bancaire sur le Free (DEC-0809-10) — avant le 22/09, conditionne AS-07 · 3 contenus (GL-17) — avant le 23/09 · modèle Pro (D2) — avant le 26/09.

**Non retenu avant le 1er, dit explicitement :** CAL-10 (durée), GL-12 (gabarit FR) si la vague 2 déborde, Lot 2 et 3 d'Astra, offre intégrateur, compte d'organisation, démo Agentforce.
