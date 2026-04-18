# BRIEFING QA AGENT — Validation & Regression

**Date** : 18 avril 2026
**Basé sur** : `AUDIT_REPORT_20260418_v3.md` + 4 briefings (A, B, C, D)
**Branches Claude Code** : `test/qa-validation-suite`

---

## 1. Mission

Construire la **suite de validation** qui garde les 4 Agent Teams dans des rails quand ils travaillent en parallèle, puis valide l'ensemble au moment du merge final. Le QA Agent n'écrit pas de code fonctionnel — il écrit du code **qui détecte les régressions** introduites par les autres.

**Objectif concret** : après ce chantier :
- Chaque Agent Team a une **commande unique** (`pytest -m agent_a_smoke`, `pytest -m agent_b_smoke`, etc.) qui valide son périmètre en < 30 secondes
- Un **test de régression inter-teams** détecte les conflits (ex: briefing B casse un contrat utilisé par briefing A)
- **3 test suites de profile** (`cloud`, `on-premise` mocked, `freemium`) valident le routing LLM
- **E2E #146** post-refonte dispose d'un playbook clair avec critères d'acceptance

**NON-objectif** : coverage 100% du codebase. On cible **ce qui change** dans la refonte et **ce qui a cassé historiquement** dans les E2E #140-145.

---

## 2. Périmètre

### Ce qu'on valide

| Zone | Teams | Tests |
|------|-------|-------|
| **Runtime agents** (F821, dispatch) | A | `test_agents_runtime.py` |
| **phased_build_executor fail-fast** | A | `test_phased_build_fails_visibly.py` |
| **P0 async/sync** | A | `test_routes_no_sync_queries_in_async.py` |
| **RAG health** | A | `test_rag_health_check.py` |
| **Budget atomicity** | A | `test_budget_commits.py` |
| **LLM router profile** | C | `test_llm_router_profiles.py` |
| **Build-enabled middleware** | C | `test_middleware_build_disabled_freemium.py` |
| **Continuation CRIT-02** | C | `test_router_continuation.py` |
| **Pricing from YAML** | C | `test_budget_pricing_yaml.py` |
| **Agents registry** | B | `test_agents_registry.py` |
| **Alias resolution** | B | `test_alias_resolution.py` |
| **HITL artifact_id rename** | B | `test_routes_hitl_contract.py` |
| **Chat history N92** | B | `test_hitl_chat_history.py` |
| **No hardcoded paths** | D | `test_no_hardcoded_paths.py` (lint) |
| **No backup files** | D | `test_repo_hygiene.py` (lint) |
| **Ruff F401/F821** | D+A | pre-commit + CI |

### Ce qu'on ne valide pas (hors scope)

- Qualité sémantique des prompts LLM (évaluée par les E2E réels)
- Coverage score Emma (métrique métier, pas test unitaire)
- Tests d'intégration UI frontend (autre chantier)

---

## 3. Structure de la suite

**Nouveau dossier** : `backend/tests/session3_regression/`

```
backend/tests/session3_regression/
├── conftest.py                           # fixtures globales + markers
├── agent_a/
│   ├── test_agents_runtime.py           # Elena, Aisha, Diego, Zara, Raj
│   ├── test_phased_build_fails_visibly.py
│   ├── test_routes_no_sync_in_async.py
│   ├── test_rag_health_check.py
│   └── test_budget_commits.py
├── agent_b/
│   ├── test_agents_registry.py
│   ├── test_alias_resolution.py
│   ├── test_routes_hitl_contract.py
│   └── test_hitl_chat_history.py
├── agent_c/
│   ├── test_llm_router_profiles.py
│   ├── test_middleware_build_disabled_freemium.py
│   ├── test_router_continuation.py
│   └── test_budget_pricing_yaml.py
├── agent_d/
│   ├── test_no_hardcoded_paths.py
│   └── test_repo_hygiene.py
├── cross/
│   ├── test_agent_b_c_integration.py    # registry tier matches router profile
│   ├── test_agent_a_c_integration.py    # agent call → router → cost tracked
│   └── test_e2e_146_playbook.py         # orchestration high-level
└── fixtures/
    ├── mock_llm_responses.py
    ├── sample_execution.py
    └── mock_ollama.py
```

### `conftest.py` — markers & fixtures

```python
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "agent_a_smoke: TASK A smoke tests")
    config.addinivalue_line("markers", "agent_b_smoke: TASK B smoke tests")
    config.addinivalue_line("markers", "agent_c_smoke: TASK C smoke tests")
    config.addinivalue_line("markers", "agent_d_smoke: TASK D hygiene lint")
    config.addinivalue_line("markers", "cross: cross-team integration")
    config.addinivalue_line("markers", "profile_cloud: requires cloud profile")
    config.addinivalue_line("markers", "profile_onprem: requires on-premise profile (mocked ollama)")
    config.addinivalue_line("markers", "profile_freemium: requires freemium profile")
    config.addinivalue_line("markers", "requires_db: needs test DB")
    config.addinivalue_line("markers", "slow: takes > 5s")

@pytest.fixture(scope="session")
def test_db():
    """Isolated test DB fixture — teardown after session."""
    # ... sqlite in-memory or pg_tmp
    pass

@pytest.fixture
def mock_anthropic_client(monkeypatch):
    """Patch anthropic.Anthropic to return deterministic responses."""
    # ... cf. fixtures/mock_llm_responses.py
    pass

@pytest.fixture
def cloud_profile(monkeypatch):
    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", "cloud")

@pytest.fixture
def onprem_profile(monkeypatch):
    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", "on-premise")

@pytest.fixture
def freemium_profile(monkeypatch):
    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", "freemium")
```

---

## 4. Tests détaillés par Agent Team

### 4.1 Agent A — Backend Bloquants

#### `test_agents_runtime.py`

```python
"""
Validates that all 11 agents can be imported and their module-level
generate_* functions execute without F821 NameErrors.
"""
import pytest

@pytest.mark.agent_a_smoke
class TestAgentImports:
    def test_elena_generate_test_importable(self):
        from agents.roles.salesforce_qa_tester import generate_test
        assert callable(generate_test)

    def test_aisha_generate_build_importable(self):
        from agents.roles.salesforce_data_migration import generate_build
        assert callable(generate_build), "Phase 6 BUILD requires this function"

    def test_all_builders_importable(self):
        # Must not raise ImportError
        from agents.roles.salesforce_developer_apex import generate_build as diego
        from agents.roles.salesforce_developer_lwc import generate_build as zara
        from agents.roles.salesforce_admin import generate_build as raj
        assert all(callable(f) for f in [diego, zara, raj])


@pytest.mark.agent_a_smoke
class TestAgentDispatch:
    """Validates run() dispatches all documented modes without returning None."""

    def test_elena_run_test_mode_returns_dict(self, mock_anthropic_client):
        from agents.roles.salesforce_qa_tester import QATesterAgent
        result = QATesterAgent().run({
            "mode": "test",
            "input_content": '{"code_files":{"t.cls":"public class T{}"}}',
            "execution_id": 1, "project_id": 1,
        })
        assert result is not None, "run() returned None — dispatch broken"
        assert "verdict" in result or "success" in result

    def test_aisha_run_build_mode_returns_dict(self, mock_anthropic_client):
        from agents.roles.salesforce_data_migration import DataMigrationAgent
        result = DataMigrationAgent().run({
            "mode": "build",
            "input_content": '{"task":{"id":"TSK-1"}}',
            "execution_id": 1, "project_id": 1,
        })
        assert result is not None


@pytest.mark.agent_a_smoke
@pytest.mark.parametrize("validation_criteria", [
    "Code should be functional",              # str
    ["Criterion A", "Criterion B"],           # list
    "",                                       # empty str
])
def test_elena_accepts_both_str_and_list_criteria(validation_criteria, mock_anthropic_client):
    """N17c regression: criteria_text undefined if str."""
    from agents.roles.salesforce_qa_tester import generate_test
    result = generate_test({
        "code_files": {"t.cls": "public class T{}"},
        "validation_criteria": validation_criteria,
    }, execution_id="1")
    assert result is not None
    assert "verdict" in result
```

#### `test_phased_build_fails_visibly.py`

```python
"""
Validates that phased_build_executor no longer returns verdict=PASS
when Elena crashes (Méta-1 fix).
"""
import pytest
from unittest.mock import patch

@pytest.mark.agent_a_smoke
def test_phased_build_fails_when_elena_crashes():
    """After A-4 fix: Elena exception → verdict=FAIL, not PASS."""
    from app.services.phased_build_executor import PhasedBuildExecutor

    with patch("app.services.phased_build_executor.generate_test") as mock_test:
        mock_test.side_effect = RuntimeError("Simulated Elena crash")

        executor = PhasedBuildExecutor(db=None, execution_id=1)
        result = executor._elena_review(
            code_files={"t.cls": "public class T{}"},
            task={"id": "TSK-1"},
        )

    assert result["verdict"] == "FAIL", \
        "phased_build_executor still fails-open (Méta-1 regression)"
    assert "infrastructure_error" in str(result).lower()
```

#### `test_routes_no_sync_in_async.py`

```python
"""
AST-level lint: no async def routes should contain db.query() without to_thread wrapper.
"""
import ast
import pathlib
import pytest

ROUTES_DIR = pathlib.Path(__file__).parent.parent.parent.parent / "app" / "api" / "routes"

def _find_violations(py_file: pathlib.Path):
    tree = ast.parse(py_file.read_text())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            for child in ast.walk(node):
                if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "query"
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "db"):
                    # Check ancestor is `await asyncio.to_thread(...)`
                    # Simple version: flag all, manual review
                    violations.append((py_file.name, node.name, child.lineno))
    return violations

@pytest.mark.agent_a_smoke
def test_no_sync_query_in_async_routes():
    total_violations = []
    for py_file in ROUTES_DIR.rglob("*.py"):
        total_violations.extend(_find_violations(py_file))

    # Allowlist for SSE endpoints wrapped in to_thread (manual review exception)
    ALLOWLIST = {
        ("execution_routes.py", "stream_execution_progress"),
        # add others after manual review
    }
    real_violations = [v for v in total_violations
                       if (v[0], v[1]) not in ALLOWLIST]

    assert len(real_violations) == 0, (
        f"P0 regression: {len(real_violations)} async routes still have sync db.query()\n"
        + "\n".join(f"  {f}:{line} in {fn}" for f, fn, line in real_violations[:20])
    )
```

#### `test_rag_health_check.py`

```python
@pytest.mark.agent_a_smoke
def test_rag_query_logs_error_on_failure(caplog):
    """P11 fix: rag failures log ERROR, not WARNING."""
    from app.services.rag_service import query_collection

    with patch("app.services.rag_service._get_collection") as mock:
        mock.side_effect = Exception("ChromaDB down")
        texts, metas = query_collection("invalid_key", "test query")

    assert texts == [] and metas == []
    error_logs = [r for r in caplog.records if r.levelname == "ERROR"]
    assert len(error_logs) > 0, "RAG failure must log ERROR, not swallow silently"
```

#### `test_budget_commits.py`

```python
@pytest.mark.agent_a_smoke
@pytest.mark.requires_db
def test_record_cost_persists_to_db(test_db):
    """P7 fix: record_cost must commit by default."""
    from app.services.budget_service import BudgetService
    from app.models.execution import Execution

    # Setup
    execution = Execution(id=9999, total_cost=0.0)
    test_db.add(execution); test_db.commit()

    # Record cost (new signature has commit=True default)
    service = BudgetService(test_db)
    service.record_cost(9999, "anthropic/opus-latest",
                        input_tokens=1000, output_tokens=500)

    # Reopen session to verify persistence (not just in-session state)
    test_db.expire_all()
    refreshed = test_db.query(Execution).filter_by(id=9999).first()
    assert refreshed.total_cost > 0, "record_cost did not commit (P7 regression)"
```

---

### 4.2 Agent B — Contracts

#### `test_agents_registry.py`

```python
@pytest.mark.agent_b_smoke
class TestAgentsRegistry:
    def test_loads_11_agents(self):
        from app.services.agents_registry import list_agents
        agents = list_agents()
        assert len(agents) == 11, f"Expected 11 agents, got {len(agents)}"

    def test_canonical_ids(self):
        from app.services.agents_registry import list_agents
        expected = {"sophie", "olivia", "marcus", "emma", "diego", "zara",
                    "raj", "elena", "aisha", "jordan", "lucas"}
        actual = set(list_agents().keys())
        assert actual == expected, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_every_agent_has_required_fields(self):
        from app.services.agents_registry import list_agents
        for aid, agent in list_agents().items():
            for field in ["name", "role", "tier", "aliases",
                          "rag_collections", "deliverable_types"]:
                assert field in agent, f"{aid} missing {field}"
            assert agent["tier"] in ("orchestrator", "worker")

    def test_tier_distribution(self):
        """SDS pipeline agents are orchestrator, experts are worker."""
        from app.services.agents_registry import list_agents
        orchestrators = {aid for aid, a in list_agents().items()
                         if a["tier"] == "orchestrator"}
        assert orchestrators == {"sophie", "olivia", "marcus", "emma"}
```

#### `test_alias_resolution.py`

```python
@pytest.mark.agent_b_smoke
@pytest.mark.parametrize("alias,expected", [
    ("ba", "olivia"),
    ("business_analyst", "olivia"),
    ("olivia", "olivia"),
    ("qa_tester", "elena"),
    ("qa", "elena"),
    ("elena", "elena"),
    ("apex_developer", "diego"),
    ("apex", "diego"),
    ("diego", "diego"),
    ("pm", "sophie"),
    ("architect", "marcus"),
    ("solution_architect", "marcus"),
    ("Sophie", "sophie"),      # case insensitive
    ("UNKNOWN", None),
])
def test_alias_resolution(alias, expected):
    from app.services.agents_registry import resolve_agent_id
    assert resolve_agent_id(alias) == expected
```

#### `test_routes_hitl_contract.py`

```python
@pytest.mark.agent_b_smoke
def test_artifact_id_route_exists(test_client):
    """N91 fix: /artifacts/{artifact_id}/versions is the new canonical route."""
    response = test_client.get("/api/pm-orchestrator/artifacts/999999/versions")
    assert response.status_code in (200, 404), \
        f"Expected 200 or 404, got {response.status_code} — route not migrated?"

def test_deliverable_id_backward_compat_with_deprecation(test_client):
    """Old route still works but emits DeprecationWarning."""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        response = test_client.get("/api/pm-orchestrator/deliverables/999999/versions")
    assert any(issubclass(wi.category, DeprecationWarning) for wi in w) \
        or response.status_code == 301, "backward compat not properly set"
```

#### `test_hitl_chat_history.py`

```python
@pytest.mark.agent_b_smoke
@pytest.mark.requires_db
def test_chat_history_persists_agent_id(test_db, test_client):
    """N92 fix: agent_id is saved on chat insert and filtered on fetch."""
    # Post a message
    response = test_client.post("/api/pm-orchestrator/executions/1/chat-sophie", json={
        "message": "Hello Sophie",
        "agent_id": "sophie",
    })
    assert response.status_code == 200

    # Fetch history
    history = test_client.get("/api/pm-orchestrator/executions/1/chat-history?agent_id=sophie")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert len(messages) > 0, "N92 regression: history empty"
    assert all(m.get("agent_id") == "sophie" for m in messages)
```

---

### 4.3 Agent C — LLM

#### `test_llm_router_profiles.py`

```python
@pytest.mark.agent_c_smoke
@pytest.mark.parametrize("profile,agent,expected_provider", [
    ("cloud", "sophie", "anthropic/opus-latest"),
    ("cloud", "marcus", "anthropic/opus-latest"),
    ("cloud", "diego",  "anthropic/sonnet-latest"),
    ("cloud", "elena",  "anthropic/sonnet-latest"),
    ("on-premise", "sophie", "local/llama-3.3-70b"),
    ("on-premise", "diego",  "local/llama-3.1-8b"),
    ("freemium", "sophie", "local/mistral-7b"),
    ("freemium", "marcus", "local/mistral-7b"),
])
def test_profile_routing(profile, agent, expected_provider, monkeypatch):
    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", profile)
    # Force reload
    from app.services import llm_router_service
    llm_router_service._router_instance = None

    from app.services.llm_router_service import get_llm_router, LLMRequest
    router = get_llm_router()
    provider = router._select_provider(LLMRequest(prompt="", agent_type=agent))
    assert provider == expected_provider, (
        f"profile={profile}, agent={agent} → {provider} (expected {expected_provider})"
    )
```

#### `test_middleware_build_disabled_freemium.py`

```python
@pytest.mark.agent_c_smoke
def test_freemium_blocks_build_endpoints(test_client, freemium_profile):
    response = test_client.post("/api/pm-orchestrator/execute/1/build")
    assert response.status_code == 403
    body = response.json()
    assert body["error"] == "build_disabled"
    assert "upgrade" in body["message"].lower()

def test_cloud_allows_build_endpoints(test_client, cloud_profile):
    response = test_client.post("/api/pm-orchestrator/execute/1/build")
    # Can be 400 / 422 / 404 but NOT 403
    assert response.status_code != 403

def test_config_capabilities_endpoint(test_client, freemium_profile):
    response = test_client.get("/api/config/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["profile"] == "freemium"
    assert body["build_enabled"] is False
```

#### `test_router_continuation.py`

```python
@pytest.mark.agent_c_smoke
def test_continuation_on_max_tokens(mock_anthropic_client):
    """N33 fix: Router V3 must auto-continue on stop_reason=max_tokens."""
    # Mock returns truncated then completion
    responses = [
        {"content": [{"text": "Part 1 "}], "stop_reason": "max_tokens",
         "usage": {"input_tokens": 100, "output_tokens": 100}},
        {"content": [{"text": "Part 2"}], "stop_reason": "end_turn",
         "usage": {"input_tokens": 50, "output_tokens": 50}},
    ]
    mock_anthropic_client.messages.create.side_effect = responses

    from app.services.llm_router_service import get_llm_router, LLMRequest
    router = get_llm_router()
    resp = router._call_anthropic(
        LLMRequest(prompt="continue please", agent_type="marcus", max_tokens=16000),
        "claude-opus-4-7-XXX",
        "anthropic/opus-latest"
    )
    assert resp.content == "Part 1 \nPart 2"
    assert resp.metadata.get("continuations") == 1
```

#### `test_budget_pricing_yaml.py`

```python
@pytest.mark.agent_c_smoke
def test_pricing_loaded_from_yaml():
    from app.services.budget_service import MODEL_PRICING
    assert "anthropic/opus-latest" in MODEL_PRICING
    assert "anthropic/sonnet-latest" in MODEL_PRICING
    assert MODEL_PRICING["anthropic/opus-latest"]["output"] > \
           MODEL_PRICING["anthropic/sonnet-latest"]["output"]
```

---

### 4.4 Agent D — Hygiene

#### `test_no_hardcoded_paths.py`

```python
"""Lint: no /root/ or /home/ paths in source (outside tests and venv)."""
import pathlib
import re
import pytest

BACKEND = pathlib.Path(__file__).parent.parent.parent.parent
IGNORE_DIRS = {"venv", "__pycache__", "tests", "migrations", ".git"}
PATH_PATTERN = re.compile(r'"(/root/|/home/)')

@pytest.mark.agent_d_smoke
def test_no_absolute_paths_in_source():
    violations = []
    for py_file in (BACKEND / "app").rglob("*.py"):
        if any(d in py_file.parts for d in IGNORE_DIRS):
            continue
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            if PATH_PATTERN.search(line) and "# allow-hardcoded-path" not in line:
                violations.append(f"{py_file.name}:{i} {line.strip()[:80]}")
    assert not violations, f"P2 regression:\n" + "\n".join(violations[:20])
```

#### `test_repo_hygiene.py`

```python
@pytest.mark.agent_d_smoke
def test_no_backup_files():
    import pathlib
    backend = pathlib.Path(__file__).parent.parent.parent.parent
    backups = list(backend.rglob("*.backup*"))
    backups = [b for b in backups if "venv" not in b.parts]
    assert not backups, f"Backup files found: {backups}"

def test_gitignore_covers_archives():
    import pathlib
    gitignore = pathlib.Path(__file__).parent.parent.parent.parent.parent / ".gitignore"
    content = gitignore.read_text()
    assert "archives/CONTEXT_" in content, "archives/CONTEXT_*.md not gitignored"
```

---

### 4.5 Cross-team integration

#### `test_agent_b_c_integration.py`

```python
@pytest.mark.cross
def test_registry_tier_matches_router_profile(cloud_profile):
    """
    Every agent's tier in agents_registry.yaml must correspond to an entry
    in profiles.cloud (either orchestrator or worker).
    """
    from app.services.agents_registry import list_agents
    from app.services.llm_router_service import get_llm_router

    router = get_llm_router()
    profile = router.get_active_profile()

    for agent_id, agent in list_agents().items():
        tier = agent["tier"]
        assert tier in profile, \
            f"Agent {agent_id} has tier '{tier}' but profile has no such key"
```

#### `test_agent_a_c_integration.py`

```python
@pytest.mark.cross
@pytest.mark.requires_db
def test_agent_call_tracks_cost_end_to_end(test_db, mock_anthropic_client, cloud_profile):
    """
    Full chain: agent calls generate_llm_response → router calls anthropic →
    cost tracked → db commits → refetch shows non-zero total_cost.
    """
    from app.services.llm_service import generate_llm_response
    from app.models.execution import Execution

    execution = Execution(id=88888, total_cost=0.0)
    test_db.add(execution); test_db.commit()

    response = generate_llm_response(
        prompt="Hello", agent_type="marcus",
        execution_id=88888, max_tokens=100,
    )
    assert response.get("success")

    test_db.expire_all()
    refreshed = test_db.query(Execution).filter_by(id=88888).first()
    assert refreshed.total_cost > 0
```

---

## 5. Playbook E2E #146 post-refonte

**Nouveau fichier** : `docs/e2e-tests/E2E_146_PLAYBOOK.md` (à créer par le QA Agent)

### Pré-requis

```bash
# 1. Tous les briefings mergés sur main
git log --oneline | head -20 | grep -cE "agent-[abcd]" 
# Should be >= 4 recent commits

# 2. Toutes les suites smoke passent
cd backend && . venv/bin/activate
pytest -m "agent_a_smoke or agent_b_smoke or agent_c_smoke or agent_d_smoke" -q
# Exit code 0

# 3. Cross-team passe
pytest -m cross -q

# 4. Linting clean
ruff check --select F821,F401 --exclude venv,__pycache__,tests . | wc -l
# Should be 0
```

### Démarrage E2E #146

```bash
# Worker ON (contrairement à #143-145 où il était OFF pour tests offline)
sudo systemctl restart digital-humans-backend digital-humans-worker

# Vérifier health RAG
curl http://localhost:8002/api/health/rag
# Expected: {"status":"ok", "chunks": N > 0}

# Vérifier profile
curl http://localhost:8002/api/config/capabilities
# Expected: {"profile":"cloud", "build_enabled": true, ...}

# Lancer un projet de test
curl -X POST http://localhost:8002/api/projects -d @test_project_formapro.json
PROJECT_ID=...

# Démarrer une exécution SDS
curl -X POST http://localhost:8002/api/pm-orchestrator/execute \
  -d '{"project_id": $PROJECT_ID, "phase": "sds"}'
EXECUTION_ID=...

# Monitor
journalctl -u digital-humans-backend --since "5 min ago" -f
```

### Critères d'acceptance E2E #146

| Critère | Cible | Mesure |
|---------|-------|--------|
| **SDS généré** | Sophie + Olivia + Emma + Marcus + Sophie OK | `SELECT status FROM executions WHERE id=X` = 'completed' |
| **Coverage Emma** | ≥ 70% (vs 61-62% avant refonte) | Dans `research_analyst_coverage_report` |
| **Tokens continuation V3** | CRIT-02 actif (metadata.continuations ≥ 1 si Marcus génère > 16K) | Log router |
| **Cost tracking** | App tracking cohérent avec Anthropic console (± 10%) | Compare `executions.total_cost` vs Anthropic dashboard |
| **BUILD Phase 1-3** | Diego/Zara/Raj produisent du code | Artifacts en DB |
| **BUILD Phase 4 (Elena)** | Verdict PASS/FAIL visible, **jamais PASS silencieux sur exception** | Log `[PhasedBuild] Elena review` pas d'erreur |
| **BUILD Phase 6 (Aisha)** | Phase s'exécute (était morte avant refonte) | Log `[Phase 6] data_migration` présent |
| **RAG visible** | Log `[RAG HEALTH] OK — N chunks` au boot | Journalctl au démarrage |
| **No silent errors** | Aucun `WARNING: falling back to V1` ni `PASS on exception` | `journalctl | grep -iE "fallback|silent"` vide |

### Si échec E2E #146

**Triage par rapport aux chantiers** :

- Échec sur import/AttributeError dans un agent → régression A-5/A-6 (F821)
- Elena verdict toujours PASS malgré crash → A-4 non appliqué (phased_build fail-open)
- `total_cost` = 0 en DB → A-9 non appliqué (budget commit)
- Build bloqué en freemium par erreur → middleware C-4 misconfigured
- Chat history vide → B fix N92 non appliqué
- Coverage Emma toujours 61% → problème qualitatif Marcus prompt, hors scope refonte

---

## 6. Tests multi-profile

### Matrice de validation

| Profile | Test | Commande |
|---------|------|----------|
| `cloud` | Pipeline SDS complet live | `DH_DEPLOYMENT_PROFILE=cloud pytest -m cross --live` |
| `on-premise` (mocked) | Routing correct + pas de fallback cloud | `DH_DEPLOYMENT_PROFILE=on-premise pytest -m "agent_c_smoke or cross"` |
| `freemium` | BUILD bloqué + SDS avec mistral-7b | `DH_DEPLOYMENT_PROFILE=freemium pytest -m "agent_c_smoke"` |

### On-premise : POC réel

**DÉCISION SAM (2026-04-18) : POC reporté APRÈS E2E #146**. Pendant la refonte, tests multi-profile uniquement via **mocks** (`fixtures/mock_ollama.py`). Le POC réel est un chantier séparé post-release, prioritaire avant vente L'Oréal/LVMH.

**À prévoir post-E2E #146 (hors scope QA)** :
1. Installer Ollama sur VPS test (pas le VPS prod)
2. Pull Llama 3.3 70B + Llama 3.1 8B
3. `DH_DEPLOYMENT_PROFILE=on-premise` + désactivation explicite d'Anthropic (`providers.anthropic.enabled: false`)
4. E2E complet (SDS + BUILD) sur un projet Formapro équivalent
5. Mesurer latences (Llama 70B est 5-10x plus lent qu'Opus pour raisonnement long) / qualité sémantique vs cloud
6. Produire `docs/deployment/on-premise-poc-report.md`

---

## 7. Plan d'exécution QA

### Sprint 1 — Fixtures & conftest (jour 1)
- `conftest.py` + markers
- `fixtures/mock_llm_responses.py` (stub Anthropic SDK)
- `fixtures/mock_ollama.py` (stub ollama client)
- `fixtures/sample_execution.py`

### Sprint 2 — Tests par team (jour 1-3)
- Les 5 suites `agent_a/` (2 jours)
- Les 4 suites `agent_b/` (0.5 jour)
- Les 4 suites `agent_c/` (1 jour)
- Les 2 suites `agent_d/` (0.5 jour)

### Sprint 3 — Cross-team + E2E playbook (jour 3-4)
- 3 tests `cross/`
- `E2E_146_PLAYBOOK.md`

### Sprint 4 — Intégration CI (jour 4)
- GitHub Actions workflow `.github/workflows/regression.yml`
- Pre-commit hook ruff F821/F401
- Badge CI dans README

---

## 8. DoD QA global

```bash
cd backend && . venv/bin/activate

# Full suite passes
pytest tests/session3_regression/ -q
# Exit code 0

# Per-team smoke in < 30s each
for team in a b c d; do
  time pytest tests/session3_regression/ -m agent_${team}_smoke -q
done

# Cross-team
pytest tests/session3_regression/ -m cross -q

# Ruff
ruff check --select F821,F401 --exclude venv,tests . | wc -l   # == 0

# Pre-commit
pre-commit run --all-files
```

---

## 9. Risques & points d'attention

1. **Mocks vs live** : la plupart des tests utilisent des mocks Anthropic/Ollama. Ils valident la **plomberie** mais pas la **qualité sémantique**. L'E2E #146 reste nécessaire.

2. **Test DB fixture** : si test_db utilise SQLite in-memory, attention aux différences PG (JSONB, ARRAY, etc.). Préférer `pg_tmp` si possible.

3. **Parallelization** : certains tests manipulent `monkeypatch.setenv` + singleton `_router_instance`. À exécuter en série (`pytest -p no:xdist` pour le marker `agent_c_smoke`).

4. **E2E #146 live** : nécessite API key Anthropic active + budget. Prévenir avant.

5. **Tests on-premise réels** : hors scope — uniquement mocks pour l'instant. POC réel = étape séparée.

---

## 10. Livrables attendus

- `backend/tests/session3_regression/` avec 15+ fichiers de tests
- `backend/tests/session3_regression/conftest.py`
- `backend/tests/session3_regression/fixtures/` (3 fichiers)
- `docs/e2e-tests/E2E_146_PLAYBOOK.md`
- `.github/workflows/regression.yml` (CI)
- `.pre-commit-config.yaml` (ruff hook)
- README.md badge CI
- `docs/testing-strategy.md` (nouveau, doc globale)

*Fin briefing QA Agent*
