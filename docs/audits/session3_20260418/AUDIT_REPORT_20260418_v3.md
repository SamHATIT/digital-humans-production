# AUDIT_REPORT_20260418 — v3 (final)

**Date** : 18 avril 2026
**Auteur** : Claude (sessions 1, 2, 3)
**Repository** : `github.com/SamHATIT/digital-humans-production`
**Branche** : `main` — dernier commit `064cc04 docs: update CLAUDE.md`
**Version** : v3 (v1 structure + v2 addendum N8-N16 + v3 findings N17-N96)

---

## 1. Executive Summary

### Verdict global

Le codebase Digital Humans présente **5 types de dettes interdépendantes** qui, prises individuellement, seraient tolérables mais qui, combinées, expliquent pourquoi les E2E #140-145 avancent sans que le BUILD produise jamais de résultat fonctionnel :

1. **Event loop bloqué systématique** — 30 à 50 endpoints en `async def` font des `db.query()` synchrones. L'endpoint `/execute` (démarrage d'une exécution) est touché.
2. **BUILD cascade morte** — Elena `generate_test` crash à chaque appel avec `NameError: response` et le `phased_build_executor` convertit cette exception en `verdict=PASS` explicite. Aisha `generate_build` n'existe même pas en module-level. Résultat : zéro validation LLM effective et phase 6 jamais exécutée.
3. **Duplications massives sur le mapping agent** — 6 dicts Python différents décrivent "qui est Marcus" avec des conventions de nommage divergentes. Un même agent peut tomber sur Opus via Router V3, sur Haiku via fallback V1, ou sur Ollama local si alias manquant.
4. **Tracking coût biaisé par 3-4x** — `record_cost` sans commit + model string mismatch Opus 4.6 + double tracking V1/V3 non réconcilié expliquent le ratio $0.86 app / $3.43 Anthropic.
5. **RAG silencieusement vide** — Collections ChromaDB retournent `context=""` sans alerte lorsque les embeddings échouent. Les agents travaillent sans RAG en pensant avoir le contexte.

### Métriques

| Métrique | v1 | v2 | **v3** |
|---|---|---|---|
| LOC absorbées en détail | ~4 000 | ~10 730 | **~23 700** (couverture ~85% backend) |
| Findings détectés | 20 | 25 | **103** (16 v2 + 87 session 3) |
| Chantiers consolidés | 9 (P0-P8) | 10 (+P9) | **13 (+P10, P11, P12)** |
| Agents couverts | 7/11 | 7/11 | **11/11** ✅ |
| Sessions d'audit | 1h | 3h20 | **~6h** |

### Découvertes critiques nouvelles (v3)

- **Elena `generate_test` crash systématique** (N17a/b/c) → cause racine de N11 "Elena PASS on exception"
- **Aisha `generate_build` absente module-level** (N18b) → Phase 6 BUILD silencieusement désactivée
- **3 agents BUILD (Diego/Zara/Raj) avec F821 module-level** (cumul) → fonctions inline cassées
- **`phased_build_executor` fail-open par design** (L622-624) → accepte tout même en cas d'exception
- **P0 d'une ampleur 2-3x supérieure** (30-50 endpoints, pas 17)
- **6 duplications de mapping agent** (AGENT_TIER_MAP, agent_complexity_map, AGENT_COLLECTIONS, CATEGORY_AGENT_MAP, agent_artifact_needs, AGENT_CHAT_PROFILES)

### Impact refonte

La refonte peut être structurée en **4 Agent Teams** (Backend, LLM, Contracts, Hygiene) + 1 QA Agent de validation. Avec la directive "uniformisation Opus/Sonnet multi-profile" (cloud / on-premise / freemium), **9 findings LLM disparaissent** avant même d'être traités — simplification majeure.

---

## 2. Couverture d'audit — session 3

### Bloc 1 — Agents restants (2 612 LOC, ~50 min)

| Fichier | LOC | Findings | État |
|---|---|---|---|
| `salesforce_qa_tester.py` (Elena) | 829 | N17a-e + méta | 🔥 Critique (generate_test cassée) |
| `salesforce_data_migration.py` (Aisha) | 659 | N18a-b | 🔥 Critique (generate_build absente) |
| `salesforce_trainer.py` (Lucas) | 610 | N19a-b | 🟡 Bugs latents |
| `salesforce_devops.py` (Jordan) | 514 | N20a-b | 🟡 Dispatch partiel |

### Bloc 2 — LLM + Budget (1 720 LOC + 70 YAML, ~30 min)

| Fichier | LOC | Findings | État |
|---|---|---|---|
| `llm_service.py` | 752 | N21-N27 | 🔥 Hardcoded models + double tracking |
| `llm_router_service.py` | 773 | N28-N34 | 🟠 Router V3 OK mais régression CRIT-02 |
| `budget_service.py` | 195 | N35-N40 | 🔥 record_cost sans commit |
| `config/llm_routing.yaml` | 70 | N41-N44 | 🟠 Pas de fallback_chain, alias manquants |

### Bloc 3 — Services métier (2 560 LOC, ~45 min)

| Fichier | LOC | Findings | État |
|---|---|---|---|
| `change_request_service.py` | 492 | N45-N52 | 🔥 Bypass Router V3 + P7 |
| `sds_synthesis_service.py` | 528 | N53-N61 | 🔥 PASS 1 absent (orphelin) |
| `rag_service.py` | 439 | N62-N71 | 🔥 Silent failure |
| `audit_service.py` | 475 | N72-N76 | 🟡 Pas thread-safe |
| `artifact_service.py` | 472 | N77-N81 | 🟡 Race conditions codes |
| `deliverable_service.py` | 154 | N82-N85 | 🟢 Pas de versioning |

### Bloc 4 — Routes + YAML agents (~3 900 + 2 474 LOC, ~40 min)

| Fichier | LOC | Findings | État |
|---|---|---|---|
| `hitl_routes.py` | 742 | N86-N93 | 🔥 Bypass V3 + chat history vide |
| Routes globales (10+ fichiers) | ~3 000 | N94 (méta) | 🔥 P0 à 30-50 endpoints |
| `sds_v3_routes.py` | 728 | — | 🟠 6/8 endpoints orphelins côté frontend |
| YAML agents (11 fichiers) | 2 474 | N95-N96 | 🔥 3 stubs (Diego/Zara/Raj) |

---

## 3. Chantiers consolidés — P0 à P12

### Matrice de priorité

| ID | Titre | Gravité | Findings rattachés | Agent Team |
|----|-------|---------|--------------------|------------|
| **P0** | Event loop bloqué (async def + sync query) | 🔥 Bloquant | N94, H1 | A (Backend) |
| **P1** | Split brain pm.py v1 + pm_orchestrator v2 | 🔥 Majeur | v1 findings | A (Backend) |
| **P2** | 52 chemins absolus hardcodés | 🟠 Majeur | v1 findings | D (Hygiene) |
| **P3** | subprocess.run() dans async (partiellement résolu) | 🟠 Partiel | commit 7aa5db9 | A (vérif) |
| **P4** | Fat Controller pm_orchestrator_v2 (2637 L) | 🟠 Majeur | N1, N16 | A (Backend) |
| **P5** | Logs fragmentés | 🟡 Moyen | v1, N65, N70 | D (Hygiene) |
| **P6** | LLM router sous-utilisé / duplications | 🔥 Critique | N21-N44, N45, N86 | **C (LLM)** |
| **P7** | Transactions non-atomiques | 🔥 Majeur | N36, N46, N77, N85 | A (Backend) |
| **P8** | Rotation secrets absente | 🟠 Sécurité | v1 findings | D (Hygiene) |
| **P9** | SDS sectioned incomplet (3 YAML stubs) | 🔥 Majeur | N95 | B (Contracts) |
| **P10** | BaseAgent class manquante | 🔥 Architecture | Pattern N17-N20 | A + B |
| **P11** | RAG silent failure | 🔥 Critique | N65, N70 | A (Backend) |
| **P12** | BUILD cascade cassée | 🔥🔥 Critique | N17-N20, N18b, méta phased_build | **A (Backend)** |

### Chantiers détaillés

#### P0 — Event loop bloqué (30-50 endpoints)

**Ampleur** : ~100 `async def` dans les routes, dont 30-50 avec `db.query()` synchrone dans le corps. Endpoints critiques affectés :
- `execution_routes.py` : `/execute`, `/execute/{id}/resume`, `/execute/{id}/progress/stream`, `/execute/{id}/result` — **cœur du pipeline**
- `change_requests.py` : 9 async def × 14 db.query
- `projects.py` : 6 async def × 12 db.query
- `sds_v3_routes.py` : 5 async def × 13 db.query
- `wizard.py`, `deployment.py`, `environments.py`, `business_requirements.py` : idem

**Effet** : pendant toute la durée d'une query SQLAlchemy sync (50ms à plusieurs secondes selon la complexité), l'event loop est bloqué → **tout le backend freeze**, autres requests en attente.

**Solutions** (à choisir pour la refonte) :
1. **Rapide** : convertir les endpoints en `def` sync → FastAPI les exécute dans un ThreadPoolExecutor automatiquement
2. **Propre** : migrer vers `AsyncSession` SQLAlchemy + `await db.execute(select(...))` partout → nécessite refactor des models
3. **Hybride** : wrapper `asyncio.to_thread(db.query(...))` pour les endpoints critiques

**Recommandation** : option 1 pour la majorité + option 2 pour le pipeline d'exécution critique (execution_routes, sds_v3_routes). Voir Briefing A.

#### P6 — LLM router / duplications

Résolu par le **chantier de consolidation Opus/Sonnet multi-profile** (voir Briefing C). Supprime d'un coup :
- V1 LLMService hardcoded (200 LOC)
- AGENT_TIER_MAP V1 + OPENAI_MODELS
- Fallback OpenAI dead path
- Duplication MODEL_PRICING / pricing YAML
- Bypass Router V3 dans change_request_service + hitl_routes

Simplification nette : **-250 LOC de routing/tiers/fallback**.

#### P7 — Transactions non-atomiques (5 services)

**Sites confirmés** :
- `budget_service.py::record_cost` L112-122 — docstring explicite "Does NOT commit"
- `change_request_service.py` — commits inline multiples dans `analyze_impact` + `process_change_request`
- `artifact_service.py` — chaque méthode CRUD commit
- `deliverable_service.py` — idem
- `audit_service.py::increment_retry` — ne commit pas

**Effet** : flows composites peuvent laisser un état partiel. Cause probable du "app tracking $0.86 vs Anthropic $3.43" : coûts écrits en DB mais jamais committés, session close → rollback silencieux.

**Solution** : introduire un pattern `UnitOfWork` ou utiliser `db.begin_nested()` + commit explicite en fin de chain.

#### P10 — BaseAgent class manquante

Les 11 agents dupliquent 80% de leur code :
- `_call_llm` avec fallback OpenAI
- `_get_rag_context` avec try/except
- `_log_interaction` INFRA-002
- `_parse_response` / `_parse_review_json`
- Patterns `LLM_SERVICE_AVAILABLE`, `RAG_AVAILABLE`, `LLM_LOGGER_AVAILABLE`
- Classe `run()` avec dispatch mode

Résultat : quand un bug est fixé dans un agent (ex: fix Lucas agent_type commit `66a9efc`), il faut le repliquer dans 10 autres. **11 agents × ~100 LOC de boilerplate dupliqué = ~1 100 LOC supprimables** avec une BaseAgent.

#### P11 — RAG silent failure

`rag_service.py::query_collection` L185-187 :
```python
except Exception as e:
    logger.warning(f"Erreur query collection {coll_key}: {e}")
    return [], []
```

Toute erreur devient "pas de résultats". Les agents reçoivent `context=""` sans savoir que c'est une panne plutôt qu'une absence légitime de contexte.

**De plus** : aucun check `collection.count() > 0` au boot. Si les ingestions ont échoué (ce qui est le cas selon user memory), l'API tourne silencieusement sans alerter.

**Solution** : health check au boot + log ERROR (pas WARNING) sur les échecs de query + indicateur `"rag_healthy": bool` dans les metadata des réponses agents.

#### P12 — BUILD cascade cassée (nouveau — cause racine identifiée)

**Chaîne de la boucle BUILD morte** :

1. `phased_build_executor._elena_review` L567 appelle `generate_test(code_files, execution_id)`
2. `generate_test` L413 crash immédiatement : `NameError: name 'response' is not defined` (response utilisée avant définition)
3. L622-624 catch l'exception et retourne `{"verdict": "PASS", "error": str(e)}` avec commentaire explicite "Default to PASS on error to not block BUILD"
4. Le code généré est "validé" en silence
5. Phase 6 (Aisha) : `from agents.roles.salesforce_data_migration import generate_build` → ImportError (fonction absente) → également avalée par try/except L454
6. Pipeline BUILD avance sans aucune validation effective jusqu'au gate SFDX

**Effet** : seule la `structural_validation` pré-LLM (XML parsing, accolades Apex) fait office de garde-fou. Tout le reste passe.

**Fix minimum (urgent)** : corriger les 5 F821 d'Elena + rétablir `generate_build` module-level chez Aisha + retirer le `return PASS on exception` de phased_build_executor (ou au moins faire un FAIL visible).

**Fix structurel (refonte)** : BaseAgent (P10) + contracts formalisés entre phased_build_executor et les agents (Briefing B).

---

## 4. Findings détaillés — session 3 (N17-N96)

### 4.1 Bugs runtime (F821 + conditional NameError)

| ID | Fichier | Loc | Gravité | Description |
|----|---------|-----|---------|-------------|
| **N17a** | salesforce_qa_tester.py | L413 | 🔥 | `response.get(...)` avant définition L429 → NameError systématique dans `generate_test` |
| **N17b** | salesforce_qa_tester.py | L492 | 🔥 | `getattr(self, ...)` dans fonction module-level (masqué par N17a) |
| **N17c** | salesforce_qa_tester.py | L418-423 | 🔥 | `criteria_text` undefined si `validation_criteria` est str (cas par défaut L403). Bug conditionnel non détecté par ruff |
| **N8** | salesforce_developer_lwc.py | L373 | 🔥 | Zara : `response` undefined L373 |
| — | salesforce_developer_lwc.py | L450 | 🔥 | Zara : `self` undefined dans fonction module-level |
| — | salesforce_developer_apex.py | L225, L277, L438 | 🔥 | Diego : 3 F821 `self` dans `generate_build` |
| — | salesforce_admin.py | L252, L291, L349, L769 | 🔥 | Raj : 4 F821 `self` dans generate_build / generate_build_v2 |
| — | salesforce_admin.py | L797 | 🔥 | Raj : `model_used` undefined |
| — | sfdx_service.py | L796, L798, L860, L862 | 🟠 | 4x `time` undefined — manque `import time` |
| — | pm_orchestrator_service_v2.py | L1301 | 🟠 | `sf_cfg` undefined |
| — | pm_orchestrator_service_v2.py | L2097, L2350 | 🟠 | `ChangeRequest` undefined (import manquant) |
| — | pm_orchestrator_service_v2.py | L2364 | 🟠 | `SDSVersion` undefined (import manquant) |

### 4.2 Dispatch `run()` incomplets (pattern systémique)

| ID | Agent | Fichier | Mode muet | Effet |
|----|-------|---------|-----------|-------|
| **N17d** | Elena | salesforce_qa_tester.py L693-703 | `"test"` | Retourne `None` si `QATesterAgent.run({"mode":"test"})` |
| **N18a** | Aisha | salesforce_data_migration.py L260-270 | `"build"` | Retourne `None` |
| **N20a** | Jordan | salesforce_devops.py L168-186 | `"deploy"` | Retourne `None` (latent — deploy passe par autre service) |
| **N18b** 🔥🔥 | Aisha | — | — | `generate_build` **module-level ABSENTE** → `phased_build_executor` L487 `ImportError` silencieusement avalée → Phase 6 data_migration jamais exécutée |
| **N17e** | Elena | salesforce_qa_tester.py L752-770 | — | `_execute_test` dead code (jamais appelé depuis `run()`) |

**Pattern P3 bâclé** : la classe a été ajoutée mais le dispatch n'a été câblé que pour le premier mode rencontré. Les fonctions module-level "pour compat backward" contiennent des références `self`/`response` qui n'étaient valides que dans la méthode de classe d'origine.

### 4.3 Tracking coût biaisé (cause probable 4x discrepancy)

| ID | Fichier | Description | Effet sur tracking |
|----|---------|-------------|---------------------|
| **N21** | llm_service.py L92-96 | `ANTHROPIC_MODELS` hardcodé (Opus 4.5 ancien) | Fallback V1 figé |
| **N25** | llm_service.py L273-281 | Budget tracking V1 skippé si V3 réussit | Tracking incohérent entre paths |
| **N29** | llm_router + budget | Double tracking V1 (DB) + V3 (mémoire) | Non réconciliés |
| **N35** | budget_service.py L17-31 | `MODEL_PRICING` dict dupliqué avec YAML | Peut diverger |
| **N36** | budget_service.py L112-122 | `record_cost` **ne commit pas** + try/except avale errors | ⚠️ Cost perdus sur session close |
| **N41** | YAML L65 | `claude-opus-4-6` sans date — si API renvoie avec date stamp, fallback sur `default`=Sonnet pricing (3.0/15.0 au lieu de 5.0/25.0) | Sous-estimation ~2x Opus |
| **N51** | change_request_service.py L24-34 | `AGENT_COSTS` obsolètes depuis CRIT-02 (experts sur Sonnet) | Sous-estimé ~3x pour experts |
| **N52** | change_request_service.py L169 | `estimated_cost += 0.50` magique pour SDS regen | Off par 10-20x |

**Analyse cumulative du 4x discrepancy** :
- Opus 4.6 sous-tracké (N41) : ~2x
- record_cost rollback silencieux (N36) : 20-50% perte
- CRIT-02 Sonnet tracké en Haiku (N23, N43) : ~3x
- **Cumul cohérent avec ratio observé $0.86 / $3.43 ≈ 4x**

### 4.4 Router LLM — architecture & fallback

| ID | Fichier | Description |
|----|---------|-------------|
| **N22** | llm_service + YAML | `AGENT_TIER_MAP` (21 entrées) vs `agent_complexity_map` (15 entrées) — duplication |
| **N23** | llm_service L127-137 | CRIT-02 a upgraded tous experts en ANALYST, mais `qa_tester` reste WORKER → Elena appelle avec Haiku alors que `elena`/`qa` pointent ANALYST |
| **N24** | llm_service L450-460 | `force_provider` construit puis jamais utilisé (dead logic) |
| **N26** | llm_service | Mapping `model`/`model_override`/`force_provider` inutilement complexe |
| **N27** | llm_service L594 | `generate_json_response` déclarée après `if __name__ == "__main__":` |
| **N28** ✅ | llm_router L248-260 | `_get_model_id` est le **point d'injection idéal** pour alias resolver |
| **N30** | llm_service L450 | `response.get("success") is not False` fragile si dict sans clé |
| **N31** | llm_router | Dépend totalement du YAML — validation YAML critique |
| **N32** | llm_router L579-600 | `complete_sync` ThreadPoolExecutor par call — anti-pattern |
| **N33** 🔥 | llm_router L332-404 | **Router V3 n'a PAS la continuation CRIT-02** de V1 → régression : réponses tronquées sans retry |
| **N34** | llm_router L73-76 | `task_type` default `SIMPLE` → Ollama → fail pour agents sans mapping |
| **N42** 🔥 | YAML | Alias prénom (`sophie`, `emma`, `marcus`) **absents du YAML** → tombent sur `simple` → Ollama → double appel (fail + V1 fallback silencieux) |
| **N43** | YAML | Tous experts sur `complex` = Sonnet (cohérent CRIT-02) |
| **N44** ✅ | YAML | Commit `2e48a19` "Olivia → Opus 4.6" bien présent |
| **N37** | budget_service | `CircuitBreaker.increment_retry()` ne commit pas non plus |
| **N38** | budget_service | `MAX_TOTAL_LLM_CALLS=80` peut être insuffisant avec continuations + retries |
| **N39** | budget_service | `DEFAULT_MONTHLY_LIMIT_USD=500` défini mais jamais utilisé |
| **N40** | budget_service | `total_tokens_used` accumulé sans reset périodique |

### 4.5 Lucas & Jordan — bugs latents

| ID | Fichier | Description |
|----|---------|-------------|
| **N19a** | salesforce_trainer.py L46-57, L156-166 | Dead code fallback : `return PROMPT_SERVICE.render(...)` suivi d'un `return f'''...'''` jamais atteint |
| **N19b** | salesforce_trainer.py L424-437 | `_call_llm` sans `else` : si `LLM_SERVICE_AVAILABLE=False`, retourne `None` → ValueError au tuple unpacking |
| **N20b** | salesforce_devops.py L346-354 | Idem N19b sur Jordan |

### 4.6 Change Request Service

| ID | Loc | Description |
|----|-----|-------------|
| **N45** 🔥 | L54 | Bypass Router V3 : `self.llm_service = LLMService()` direct → Sophie sur Opus 4.5 ancien |
| **N46** | Plusieurs | P7 : commits inline non-atomiques dans `analyze_impact` + `process_change_request` |
| **N47** | L175 | `agents_to_rerun` stocké sans validation — LLM peut halluciner noms |
| **N48** | L237-247 | `_parse_impact_json` écrase blocs ``` (fragile) |
| **N49** | L36-44 | `CATEGORY_AGENT_MAP` utilise noms courts (`ba`, `apex`) incompatibles avec YAML V3 |
| **N50** | L462 | Chaîne `execute_cr` → `process_change_request` → `execute_targeted_regeneration` (design lasagna) |
| **N51** | L24-34 | `AGENT_COSTS` obsolètes (cf. 4.3) |
| **N52** | L169 | `estimated_cost` magique (cf. 4.3) |

### 4.7 SDS Synthesis Service

| ID | Loc | Description |
|----|-----|-------------|
| **N53** | L298 | `force_provider="anthropic/claude-sonnet"` confirmé (redondant) |
| **N54** 🔥 | — | Appelé uniquement par `sds_v3_routes.py` — orphelin sans frontend actif |
| **N55** | L36-48 | `DOMAIN_KEYWORDS` hardcodé 11 domaines |
| **N56** | L213-232 | Classification par keyword scoring, tie-breaking absent |
| **N57** 🔥 | Docstring L6 | **PASS 1 Mistral local absent du fichier** (la docstring ment) |
| **N58** | L301 | `max_tokens=4000` insuffisant pour section SDS complète |
| **N59** | — | `synthesize_sds` retourne en mémoire, pas de persistence DB |
| **N60** | L373-389 | `generate_erd_mermaid` heuristique faux-positifs |
| **N61** | L419 | `permissions_matrix` hardcodée raj=R+C+M (absurde) |

### 4.8 RAG Service — silent failure

| ID | Loc | Description |
|----|-----|-------------|
| **N62** | L72 | `_collections = {}` cache global mutable, pas d'invalidation |
| **N63** | L95-103 | Fallback API key lu depuis file path (pattern risqué) |
| **N64** | L115-123 | `get_nomic_model()` 30-60s au premier chargement → timeouts |
| **N65** 🔥 | — | **Pas de check `collection.count() > 0`** au boot → empty ingestion invisible |
| **N66** | L179 | `project_id` filter avec `str()` cast — mismatch si ingestion sans cast |
| **N67** | L10 | `import chromadb` sans try/except — crash au boot si absent |
| **N68** | — | N/A (ChromaDB commit auto) |
| **N69** | L58-70 | `AGENT_COLLECTIONS` manque `sophie`, `emma` → tombent sur `default` |
| **N70** 🔥 | L185-187 | `except Exception: return [], []` → masque tous les échecs RAG |
| **N71** | L129-131 | `_reranker = False` sentinel pattern complexe |

### 4.9 Audit Service

| ID | Loc | Description |
|----|-----|-------------|
| **N72** | L37 | `self._request_context` dict singleton — **pas thread-safe** malgré docstring. À remplacer par `contextvars.ContextVar` |
| **N73** | L144-147 | Audit DB down → 1000 logs silencieusement perdus (pas de circuit breaker) |
| **N74** | L114 | `SessionLocal()` par call → 150+ sessions ouvertes/closes par BUILD |
| **N75** | L174-197 | `timed_operation` success="true" par défaut si `set_result()` oublié |
| **N76** | L215 | Pas de max cap sur `limit` dans `get_logs` |

### 4.10 Artifact Service + Deliverable Service (P7 + race conditions)

| ID | Fichier | Description |
|----|---------|-------------|
| **N77** | artifact_service | `commit` dans chaque méthode CRUD — P7 |
| **N78** | artifact_service | `synchronize_session=False` sur bulk updates → objets stale |
| **N79** | artifact_service L367-378, L440-451 | Race condition : `get_next_artifact_code` / `get_next_question_code` (count+1 sans lock) |
| **N80** | artifact_service L148-157 | `agent_artifact_needs` utilise noms courts → retourne `[]` si caller passe `"business_analyst"` |
| **N81** | artifact_service | Import `ArtifactType` jamais utilisé |
| **N82** | deliverable_service | Pas d'update `updated_at` dans `update_deliverable` |
| **N84** | deliverable_service | Pas de versioning — `get_by_type` retourne le premier, pas le plus récent |
| **N85** | deliverable_service | P7 : commits inline |

### 4.11 HITL Routes

| ID | Loc | Description |
|----|-----|-------------|
| **N86** 🔥 | L266 | Bypass Router V3 : `LLMService()` direct (même bug N45) — **disparaît avec l'uniformisation Opus/Sonnet** |
| **N87** | L80-180 | `AGENT_CHAT_PROFILES` = **6ᵉ dict de mapping agent**. À consolider |
| **N88** ✅ | — | Correction rapport v2 : routes sont sync (PAS de P0 dans hitl_routes) |
| **N89** | L213-280 | Pas de RAG dans chat Sophie |
| **N90** | L411-423 | Background `_run_cr` ne rollback pas le status CR si échec |
| **N91** | L217-225 vs L480+ | `deliverable_id` ambigu : pointe vers `AgentDeliverable.id` dans `/chat`, `ExecutionArtifact.id` dans `/versions` |
| **N92** 🔥 | L730 vs L295-304 | **Bug pratique** : `get_agent_chat_history` filtre sur `ProjectConversation.agent_id` mais `chat_with_sophie_contextual` **ne sauve PAS** `agent_id` → historique toujours vide |
| **N93** | L250-260 vs L80-95 | `system_prompt` Sophie écrit inline **en parallèle** de `AGENT_CHAT_PROFILES` → 2 sources divergentes |

### 4.12 Routes globales & YAML

| ID | Description |
|----|-------------|
| **N94** 🔥🔥 | P0 grande ampleur : ~30-50 endpoints `async def` + `db.query` sync (bien au-delà des 17 annoncés v2). Liste : `change_requests.py` (9), `projects.py` (6), `sds_v3_routes.py` (5), `execution_routes.py` (5), `business_requirements.py` (8), `wizard.py` (10), `deployment.py` (10), `environments.py` (9). **`execution_routes.py::start_execution` est le plus critique** |
| **N95** 🔥 | 3 YAML stubs de 15 lignes : `diego_apex.yaml`, `zara_lwc.yaml`, `raj_admin.yaml` — les 3 BUILD agents critiques (phases 1,2,3) n'ont PAS de prompts externalisés |
| **N96** ✅ | 8 autres YAML chargés : Sophie 227, Olivia 132, Emma 470, Marcus 697, Elena 198, Aisha 214, Jordan 243, Lucas 248 |

### 4.13 Méta-findings

| ID | Description |
|----|-------------|
| **Méta-1** | `phased_build_executor.py` L622-624 : `except Exception: return {"verdict": "PASS", "error": str(e)}` avec commentaire explicite "Default to PASS on error to not block BUILD" → **fail-open by design** qui masque les crashes Elena |
| **Méta-2** | SDS V3 : 6/8 endpoints orphelins côté frontend (seuls `/generate-sds-v3` et `/download-sds-v3` sont appelés). Combiné avec N54+N57, le pipeline SDS V3 est **effectivement non-fonctionnel** en prod |
| **Méta-3** | 2 fichiers `.backup_*` traînants non nettoyés : `pm_orchestrator_service.py.backup_artifacts` (43K), `rag_service.py.backup_pre_bug043` (12K) — dans app/services/ |
| **Méta-4** | 6 dicts de mapping agent divergents à consolider en `agents_registry.yaml` : AGENT_TIER_MAP, agent_complexity_map, AGENT_COLLECTIONS, CATEGORY_AGENT_MAP, agent_artifact_needs, AGENT_CHAT_PROFILES |
| **Méta-5** | 64 fichiers `CONTEXT_*.md` dans archives/ untracked (pas bloquant mais suggère git flow à nettoyer) |


---

## 5. Cartographie fichier × finding (Top 15 fichiers à risque)

| Rang | Fichier | Findings | Gravité cumulée | Priorité refonte |
|------|---------|----------|-----------------|------------------|
| 1 | `agents/roles/salesforce_qa_tester.py` | N17a-e + F821x2 | 🔥🔥🔥 | **Briefing A — Fix immédiat** |
| 2 | `agents/roles/salesforce_data_migration.py` | N18a-b | 🔥🔥🔥 | **Briefing A — Fix immédiat** |
| 3 | `app/services/phased_build_executor.py` | Méta-1 | 🔥🔥 | Briefing A |
| 4 | `app/services/llm_service.py` | N21-N27 (7) | 🔥 | Briefing C (suppression totale) |
| 5 | `app/services/llm_router_service.py` | N28-N34 (7) | 🔥 | Briefing C (enrichissement) |
| 6 | `app/services/budget_service.py` | N35-N40 (6) | 🔥 | Briefing C + Briefing A (commit) |
| 7 | `app/api/routes/execution_routes.py` | N94 (P0 × 5) | 🔥🔥 | Briefing A (P0 start_execution) |
| 8 | `app/api/routes/change_requests.py` | N94 (P0 × 9) | 🔥 | Briefing A (P0 batch) |
| 9 | `app/services/rag_service.py` | N62-N71 (9) | 🔥 | Briefing A (P11) |
| 10 | `app/api/routes/hitl_routes.py` | N86-N93 (8) | 🟠 | Briefing A + B |
| 11 | `agents/roles/salesforce_admin.py` (Raj) | F821 × 5 | 🔥 | Briefing A |
| 12 | `agents/roles/salesforce_developer_apex.py` (Diego) | F821 × 3 + YAML stub | 🔥 | Briefing A |
| 13 | `agents/roles/salesforce_developer_lwc.py` (Zara) | F821 × 2 + YAML stub | 🔥 | Briefing A |
| 14 | `app/services/change_request_service.py` | N45-N52 (8) | 🟠 | Briefing A + C |
| 15 | `app/services/artifact_service.py` | N77-N81 (5) | 🟠 | Briefing B (P7) |

---

## 6. Métriques finales

### Par sévérité

| Niveau | Count | % |
|---|---|---|
| 🔥🔥 Critique bloquant | ~15 | 15% |
| 🔥 Critique | ~30 | 29% |
| 🟠 Majeur | ~28 | 27% |
| 🟡 Moyen | ~20 | 19% |
| 🟢 Mineur/info | ~10 | 10% |
| **Total** | **103** | 100% |

### Par catégorie

| Catégorie | Count |
|---|---|
| Runtime bugs (F821 + conditional) | 17 |
| LLM routing / tiers / pricing | 24 |
| Transactions (P7) | 5 |
| Dispatch/run() incomplet | 5 |
| RAG | 10 |
| Services métier (autres) | 20 |
| Routes / P0 async | 10 |
| YAML stubs + duplications agent | 8 |
| Hygiene (backups, dead code) | 4 |

### Disparition attendue avec l'uniformisation Opus/Sonnet multi-profile

**9 findings LLM consolidés** : N21, N22, N23, N28, N31, N35, N41, N42, N43 → supprimés par l'adoption du YAML unique + 2 tiers + deployment profiles.

**3 findings de bypass** : N45, N86, N33 (bridge V1/V3) → supprimés par la suppression de `LLMService` V1.

**Total : 12/103 findings éliminés mécaniquement par le chantier LLM.**

---

## 7. Commandes rejouables

### Validation F821 persistants
```bash
cd /root/workspace/digital-humans-production/backend
. venv/bin/activate
ruff check --select F821 --exclude venv,__pycache__,.pytest_cache,migrations,alembic,tests,debug_exec_87 . 2>&1 | grep -E "^F821|^\s+-->"
```

### Compte des async def + db.query sync
```bash
cd /root/workspace/digital-humans-production/backend
for f in app/api/routes/*.py app/api/routes/orchestrator/*.py; do
  async_count=$(grep -cE "^async def|^    async def" "$f" 2>/dev/null)
  query_count=$(grep -cE "\bdb\.query\(" "$f" 2>/dev/null)
  if [ "$async_count" -gt 0 ] && [ "$query_count" -gt 0 ]; then
    echo "$f: async_def=$async_count, db.query()=$query_count"
  fi
done
```

### Validation absence de `generate_build` chez Aisha
```bash
cd /root/workspace/digital-humans-production/backend
grep -nE "^def (generate_build|generate_build_v2|generate_test|generate_deploy)" \
  agents/roles/salesforce_data_migration.py \
  || echo "CONFIRMED: no module-level generate_build in Aisha"
```

### Test impact N92 (chat history vide)
```bash
psql -h localhost -U digitalhumans -d digital_humans \
  -c "SELECT agent_id, COUNT(*) FROM project_conversations GROUP BY agent_id;"
# Si toutes les lignes ont agent_id=NULL → N92 confirmé en prod
```

### Vérification health RAG
```bash
cd /root/workspace/digital-humans-production/backend
python -c "
from app.services.rag_service import get_stats
import json
print(json.dumps(get_stats(), indent=2))
"
# Si count=0 partout → N65 confirmé (RAG empty)
```

### Test 4x discrepancy cost tracking
```bash
cd /root/workspace/digital-humans-production/backend
journalctl -u digital-humans-backend --since "1 hour ago" | grep -E "model|cost" | head -30
# Comparer avec Anthropic console
```

### Vérification fallback V1 activé
```bash
cd /root/workspace/digital-humans-production/backend
journalctl -u digital-humans-backend --since "1 day ago" | grep -iE "router v3|v1 fallback|fallback to"
# Compter les "falling back to V1" — chacun = double appel LLM
```

---

## 8. Annexes

### 8.1 Stratégie refonte — 4 Agent Teams + 1 QA

| Team | Mission | Livrables | Nb findings couverts |
|------|---------|-----------|----------------------|
| **A — Backend Bloquants** | P0, P7, P11, P12, F821 | Code fix + tests | ~35 |
| **B — Contracts inter-agents** | Consolidation 6 dicts → agents_registry.yaml, P9, N91-93 | YAML + interface types | ~15 |
| **C — LLM Modernization** | P6 — suppression V1, multi-profile, YAML unique | llm_service.py simplifié + config | ~25 |
| **D — Hygiene & Cleanup** | P2, P5, P8, dead code, backups | Nettoyage + docs | ~15 |
| **QA Agent** | Validation multi-profile + regression | Suite de tests | ~13 |

### 8.2 Ordre de merge recommandé

1. **A** (branches séparées par fichier : elena, aisha, diego, zara, raj) → fix runtime en priorité
2. **C** en parallèle (pas de dépendance cross avec A après fix F821)
3. **B** après A+C (a besoin du agent_type stabilisé)
4. **D** à la fin (cleanup post-refactor)
5. **QA** valide chaque merge

### 8.3 Fichiers critiques à préserver

- `config/llm_routing.yaml` → sera refondu mais reste la source de vérité
- `prompts/agents/*.yaml` (8 remplis) → à fusionner avec stubs Diego/Zara/Raj
- `docs/audits/session3_20260418/` → ce rapport + 5 briefings

### 8.4 Dépendances non résolues dans cet audit

- **Frontend** (~11 000 LOC) non absorbé exhaustivement — seul point d'entrée sds_v3 vérifié
- **Models** (~3 000 LOC, 30 fichiers) non absorbés en détail — à valider dans briefing B pour les contrats
- **Tests** existants (if any) non audités — à auditer dans briefing QA

---

*Rapport v3 clôturé le 18 avril 2026 — session 3 complète.*
*Livrables connexes : BRIEFING_AGENT_A.md, BRIEFING_AGENT_B.md, BRIEFING_AGENT_C.md, BRIEFING_AGENT_D.md, BRIEFING_QA_AGENT.md, MAITRE_OEUVRE_PLAN.md*
