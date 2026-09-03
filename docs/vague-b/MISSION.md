# Mission — Vague B (Digital·Humans, pré-ouverture)

Tu travailles sur `/root/workspace/digital-humans-production`, branche
`claude/vague-b-20260903`, créée depuis `main` (`608a09a`, vague A déployée
le 03/09). Même processus que la vague A : bac à sable Claude Code, revue
Sam + Claude, déploiement VPS ensuite. Tu ne touches ni `main`, ni `.env`,
ni la base `digital_humans_db`, ni les services systemd. Tu pousses la branche
à la fin, sans merger.

## Environnement, modèles, outils

- Bac à sable Claude Code, pas le VPS. PostgreSQL à installer (`digital_humans_test`),
  venv `backend/venv` à créer, `TEST_DATABASE_URL` = `DATABASE_URL` = base de test.
  Jamais SQLite : `tests/conftest.py` exige Postgres.
- Modèles : orchestrateur Fable 5.1 ; Opus pour B1, B2, B4 ; Sonnet pour B3, B5,
  B6, B7, B8, B9 et l'écriture des tests.
- Référence pytest : **mesurée par toi au lot B0**. Chiffre du VPS le 03/09 après
  vague A : `15 failed, 611 passed, 7 xfailed, 0 error`. Dans le bac à sable les
  11 `test_lot_e` passent (ils échouent sur le VPS parce que la prod vit sous
  `/root/workspace`, voir B9) ; attends-toi à `4 failed` (3 `test_auth`,
  1 `test_emma_phase3`), tous antérieurs. Ne les corrige pas, ne les marque
  pas `xfail`.
- La suite dure ~5 min : arrière-plan + lecture du log.

## Discipline

Les huit règles de `docs/vague-a/MISSION.md`, section « Discipline », s'appliquent
mot pour mot. Lis aussi `.claude/skills/dh-discipline-de-preuve/SKILL.md`,
`docs/vague-a/EXECUTION.md` (ce qui a été fait, et ses quatre « non confirmés »)
et `docs/vague-a/DECISIONS_SAM.md`.

Deux règles de plus, nées de la vague A :

9. **Une URL, un port, un identifiant déclaré = un service qui répond.** Tu
   n'écris jamais une adresse de service dans un YAML, un script ou un test
   sans l'avoir sondée (`curl`) ou sans pouvoir prouver qu'elle est sondée au
   démarrage. La vague A a trouvé un port mort et un `model_id` refusé en 404
   qui rendaient la plateforme inopérante depuis trois jours sans un mot.
10. **Un test qui passe dans le bac à sable et échoue en prod est un test faux,
    ou une prod mal placée — jamais un détail.** Signale-le, ne le contourne pas.

## Ordre

**B0 puis B1 seuls, en séquence** — B1 touche l'orchestrateur, personne d'autre
n'y entre tant qu'il n'est pas commité. Ensuite B2..B9 en parallèle, périmètres
disjoints (un `git worktree` par sous-agent). B2 et B5 lisent
`docs/vague-b/DECISIONS_SAM.md` avant de commencer : une ligne « À TRANCHER »
sur leur sujet les arrête.

## Lots

### B0 — Référence
Installer, mesurer, coller la ligne pytest. Pas de code.

### B1 — Compteur de crédits (bloquant Pro)
Périmètre : `backend/app/services/llm_router_service.py`,
`backend/app/services/pm_orchestrator_service_v2.py`, les agents sous
`backend/app/agents/` ou `backend/agents/` qui construisent un appel LLM,
`backend/app/services/sophie_concierge_service.py` (un seul point d'appel).
Défaut mesuré (02/09) : `LLMRequest.user_id: Optional[int] = None  # None = skip
credit hook` ; aucun appel de l'orchestrateur ne le renseigne ; table
`credit_transactions` : **0 ligne** pour 222 `llm_interactions` sur 30 jours.
Le Pro à 79 €/mois pour 15 000 crédits qui ne sont jamais décomptés.
`executions.user_id` est renseigné sur 131/131 lignes : la propagation est possible.
À faire :
1. `user_id` devient **obligatoire** dans le chemin agent (règle 5 : `None` lève
   une erreur nommant l'appelant, ne saute pas). Le concierge public, sans
   compte, passe par un chemin explicite `sans_compte=True`, jamais par `None`.
2. Chaque appel de l'orchestrateur propage `user_id` depuis l'exécution.
3. Test rouge d'abord : un SDS Free de bout en bout (agents simulés, LLM simulé
   renvoyant des jetons) produit ≥ 1 ligne `credit_transactions` par appel.
4. Contrôles négatifs : Free au-delà de 300 crédits/jour → `InsufficientCreditsError`
   remontée à l'API avec un message clair ; Pro au-delà de 15 000/mois → idem.
5. `credit_service` : les quatre tests existants restent verts.
Fin : `grep -n "None = skip credit hook"` → 0 ; tests ci-dessus verts.

### B2 — Routage par tier
Périmètre : `backend/config/llm_routing.yaml` **uniquement** ; un test dans
`tests/`. Jamais dans le code des agents.
Bloqué par **D2** (Pro : Sonnet/Opus via Anthropic, ou Nemotron local avec
promesse marketing ajustée). Si D2 est « À TRANCHER » : arrête, signale.
Sinon : `tier_overrides.free` → `gpu_nemotron/nemotron` ; `tier_overrides.pro`
selon D2 ; agent inconnu → `warning` nommant l'agent et les agents valides.
Test : `get_tier_for_agent("marcus")` pour un Pro renvoie le modèle tranché ;
pour un Free, Nemotron ; agent `"zorro"` → warning, pas de repli silencieux.

### B3 — RGPD consentement
Périmètre : migration Alembic 013, `backend/app/models/user.py`,
`backend/app/api/routes/auth.py`, le formulaire d'inscription du frontend.
Colonnes `consent_cgv_at TIMESTAMPTZ`, `consent_version VARCHAR(16)`,
`consent_ip_hash VARCHAR(64)` (hash, jamais l'IP brute — même règle que
`chat_logs.ip_hash`). L'inscription sans consentement explicite → 400 avec
message. Test rouge d'abord, contrôle négatif. La migration est idempotente et
réversible, testée sur la base jetable ; **pas exécutée sur prod**.

### B4 — RGPD droits (art. 15, 17, 20)
Périmètre : `backend/app/api/routes/account.py` (nouveau), `backend/app/services/account_service.py`
(nouveau), tests.
Inventaire d'abord, table par table, des données rattachées à un compte. Point
de départ mesuré : `credit_balances`, `credit_transactions`, `executions`,
`projects` portent `user_id` ; `chat_logs` porte `session_uuid`, `ip_hash`,
`email_collected` (rattachement par email). Complète l'inventaire par lecture
des modèles et écris-le dans `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md`.
Puis : `GET /api/account/export` (JSON de tout ce qui précède) ;
`DELETE /api/account` (anonymisation des lignes à conserver pour la compta,
suppression du reste, purge Chroma des collections liées aux projets du
compte, révocation du jeton). Tests : l'export contient les projets et les
transactions ; après suppression, login → 401 et export → 404.
Art. 22 hors périmètre (validation humaine à chaque étape, client = personne morale).

### B5 — Rétention des conversations Sophie
Périmètre : `backend/app/workers/`, un test.
Bloqué par **D3** (durée). Tâche `arq` périodique qui purge `chat_logs` au-delà
de la durée ; test : une ligne antidatée disparaît, une ligne récente reste.

### B6 — `/health` sans recompte à chaque appel
Périmètre : la sonde RAG de `backend/app/main.py` (lot A6 de la vague A) et
`backend/app/services/rag_service.py` si nécessaire.
Constat corrigé du 27/08 : `/health` compte déjà dans un fil, la boucle n'est
pas bloquée ; mais il recompte 161 856 chunks à chaque appel du watchdog
(50 ms à chaud, 11–16 s dans les pics, d'où les fausses alertes `000`).
Correctif : résultat du comptage en cache avec TTL (30 min), rafraîchi en tâche
de fond ; `/health` lit le cache. Test : deux appels consécutifs → un seul
comptage ; cache périmé → recomptage.

### B7 — Une seule source pour les tiers
Périmètre : `frontend/src/pages/Pricing.tsx`, `backend/app/models/subscription.py`,
`backend/app/agents/prompts/sophie_pm.yaml` (ou l'emplacement réel du prompt
de Sophie), un endpoint `GET /api/public/tiers` si absent.
Constat vague A : `Pricing.tsx` affiche Free « 500/mois » (vrai : 300/jour),
Team « 50 000 » (vrai : 100 000), FAQ « un SDS ≈ 800 crédits » (mesure :
≈ 1 200) ; `sophie_pm.yaml` annonce « 2 SDS/mois ». Vérité = table `tier_config`.
Fin : plus aucun chiffre de crédits ou de prix en dur côté front ni dans un
prompt ; tous lus depuis l'API ; test qui compare le rendu à `tier_config`.

### B8 — Deux compteurs muets
Périmètre : `backend/app/services/sophie_concierge_service.py`,
`dh-comite` n'est pas dans ce dépôt — pour `daily.sh`, écris le correctif dans
`docs/vague-b/CORRECTIF_DAILY_RC.md` (Sam l'appliquera).
1. `chat_logs.tokens_in / tokens_out` restent NULL : le service écrit
   `tokens_input`/`tokens_output`. Aligner sur les colonnes, test.
2. `daily.sh` affiche `RC=1` alors que `claude -p` réussit (`is_error: false`,
   `subtype: success`) : documenter la cause (probablement le `|| RC=$?` qui
   capture le code du `cat` ou d'un pipe) et le correctif ; l'alerte doit se
   fonder sur `is_error` du JSON, pas sur le code de retour du shell.

### B9 — `test_lot_e` contre la réalité de la prod
Périmètre : `backend/tests/test_lot_e_secrets_and_paths.py` et
`docs/vague-b/ARBITRAGE_CHEMIN_PROD.md`.
Le test interdit le préfixe `/root/workspace` ; la prod vit dans
`/root/workspace/digital-humans-production`. Il passe dans le bac à sable et
échoue sur le VPS depuis des semaines. Écris l'arbitrage : soit le test
vérifie que les chemins **dérivent du checkout** (ce que dit sa docstring)
sans lister de préfixes interdits, soit la prod déménage. Propose le premier,
implémente-le, et note ce que le second coûterait. Ne supprime pas le test.

## Livrable

`docs/vague-b/EXECUTION.md`, quatre sections : fait (commande + sortie par lot),
non confirmé, ouvert, non fait par choix. Puis `git log --oneline main..HEAD`
et la ligne pytest finale. Un commit par lot, en français, citant défaut, cause,
correctif, preuve. Migrations 013 et suivantes : produites, testées sur base
jetable, **jamais exécutées sur prod**. Pousse la branche, ne merge pas.
