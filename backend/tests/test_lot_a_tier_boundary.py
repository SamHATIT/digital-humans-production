"""
LOT-A — Frontière payante (audit croisé 21/08/2026).

Constats couverts :
  cla:TIER-01 / kim:TIER-01 — un compte Free pouvait lancer la séquence SDS
      complète via POST /api/pm-orchestrator/execute (aucun check de palier).
  cla:TIER-02 / gem:BIZ-01 / kim:TIER-01 — un compte Free ou Pro pouvait
      déclencher le BUILD via POST /api/pm-orchestrator/projects/{id}/start-build.
  ope:TIER-01 — le masquage était purement frontend ; ces tests attaquent
      directement l'API, comme le ferait un appel DevTools/curl.

Le décorateur `require_feature` existait déjà (feature_access.py) mais n'était
appliqué nulle part : sa seule occurrence était son propre exemple de docstring.
"""
import asyncio

import pytest
from fastapi import HTTPException

from app.main import app
from app.models.user import User
from app.models.subscription import SubscriptionTier
from app.rate_limiter import limiter
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.utils.feature_access import (
    FeatureAccessError,
    ensure_feature,
    require_feature,
    resolve_tier,
)

EXECUTE_URL = "/api/pm-orchestrator/execute"
START_BUILD_URL = "/api/pm-orchestrator/projects/1/start-build"
RESUME_URL = "/api/pm-orchestrator/execute/1/resume"


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Les quotas slowapi (10/h SDS, 5/h BUILD) sont partagés par process."""
    limiter.reset()
    yield
    limiter.reset()


def _make_user(db, tier: str) -> User:
    user = User(
        email=f"lot-a-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name=f"LOT-A {tier}",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _authenticate_as(user: User):
    """Injecte `user` comme utilisateur authentifié.

    L'objet du test est la frontière de palier, pas le JWT : on court-circuite
    l'authentification pour attaquer la route avec un compte au palier voulu.
    """
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


def _tier_denied(response) -> bool:
    """True si la réponse est bien un refus de palier (403 structuré)."""
    if response.status_code != 403:
        return False
    detail = response.json().get("detail")
    return isinstance(detail, dict) and detail.get("error") == "feature_not_available"


# --------------------------------------------------------------------------
# Critère de fin #1 — Free → 403 sur POST /api/pm-orchestrator/execute
# --------------------------------------------------------------------------

def test_free_user_cannot_start_sds_execution(client, db_session):
    """cla:TIER-01 — le palier gratuit ne peut pas déclencher la séquence SDS."""
    _authenticate_as(_make_user(db_session, "free"))

    r = client.post(EXECUTE_URL, json={"project_id": 1, "selected_agents": ["pm", "ba"]})

    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "feature_not_available"
    assert detail["feature"] == "sds_document"
    assert detail["required_tier"] == "pro"
    assert detail["upgrade_url"] == "/pricing"


def test_free_user_cannot_resume_sds_execution(client, db_session):
    """kim:TIER-01 — sinon la frontière se contourne par re-exécution."""
    _authenticate_as(_make_user(db_session, "free"))

    r = client.post(RESUME_URL, json={})

    assert _tier_denied(r), r.text


def test_pro_user_passes_the_sds_gate(client, db_session):
    """Contrôle positif : Pro franchit la porte (404 = projet inexistant, pas 403)."""
    _authenticate_as(_make_user(db_session, "pro"))

    r = client.post(EXECUTE_URL, json={"project_id": 999999, "selected_agents": ["pm", "ba"]})

    assert not _tier_denied(r), "le palier Pro doit franchir la porte SDS"
    assert r.status_code == 404, r.text


# --------------------------------------------------------------------------
# Critère de fin #2 — Pro → 403 sur déclenchement BUILD
# --------------------------------------------------------------------------

def test_pro_user_cannot_start_build(client, db_session):
    """cla:TIER-02 / gem:BIZ-01 — Pro = SDS seul, le BUILD est Team (1 490 €)."""
    _authenticate_as(_make_user(db_session, "pro"))

    r = client.post(START_BUILD_URL, json={})

    assert r.status_code == 403, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "feature_not_available"
    assert detail["feature"] == "build_phase"
    assert detail["required_tier"] == "team"


def test_free_user_cannot_start_build(client, db_session):
    """kim:TIER-01 — le scénario cité : un compte gratuit poste start-build."""
    _authenticate_as(_make_user(db_session, "free"))

    r = client.post(START_BUILD_URL, json={})

    assert _tier_denied(r), r.text
    assert r.json()["detail"]["feature"] == "build_phase"


def test_team_user_passes_the_build_gate(client, db_session):
    """Contrôle positif : Team franchit la porte de palier.

    Ce qui se passe ensuite (projet inexistant, dépendance absente de
    l'environnement de test) ne regarde pas LOT-A : un refus de palier serait
    une FeatureAccessError, donc une réponse 403 structurée, jamais une
    exception brute remontée depuis le corps de l'endpoint.
    """
    _authenticate_as(_make_user(db_session, "team"))

    try:
        r = client.post(START_BUILD_URL, json={})
    except HTTPException as exc:
        assert exc.status_code != 403, "Team ne doit pas être refusé par le palier"
        return
    except Exception:
        # Exception levée en aval de la porte : la porte a donc été franchie.
        return

    assert not _tier_denied(r), "le palier Team doit franchir la porte BUILD"


def test_require_feature_lets_an_entitled_user_through():
    """Contrôle positif déterministe, sans dépendance d'environnement."""

    @require_feature("build_phase")
    async def endpoint(current_user=None):
        return "reached"

    team = type("U", (), {"subscription_tier": "team"})()
    assert asyncio.run(endpoint(current_user=team)) == "reached"

    pro = type("U", (), {"subscription_tier": "pro"})()
    with pytest.raises(FeatureAccessError):
        asyncio.run(endpoint(current_user=pro))


# --------------------------------------------------------------------------
# Le garde-fou lui-même
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "tier,feature,allowed",
    [
        ("free", "sds_document", False),
        ("pro", "sds_document", True),
        ("team", "sds_document", True),
        ("enterprise", "sds_document", True),
        ("free", "build_phase", False),
        ("pro", "build_phase", False),
        ("team", "build_phase", True),
        ("enterprise", "build_phase", True),
    ],
)
def test_ensure_feature_matches_the_declared_tier_policy(tier, feature, allowed):
    user = type("U", (), {"subscription_tier": tier})()
    if allowed:
        ensure_feature(user, feature)
    else:
        with pytest.raises(FeatureAccessError) as exc:
            ensure_feature(user, feature)
        assert exc.value.status_code == 403


def test_ensure_feature_rejects_anonymous_caller():
    with pytest.raises(HTTPException) as exc:
        ensure_feature(None, "build_phase")
    assert exc.value.status_code == 401


def test_resolve_tier_fails_closed_on_garbage():
    """Un tier corrompu en base ne doit jamais *accorder* un accès."""
    assert resolve_tier(type("U", (), {"subscription_tier": "platinum"})()) is SubscriptionTier.FREE
    assert resolve_tier(type("U", (), {"subscription_tier": None})()) is SubscriptionTier.FREE


def test_require_feature_rejects_endpoint_without_current_user():
    """Fail closed : pas de current_user injecté → 401, jamais un passage muet."""

    @require_feature("build_phase")
    async def endpoint(**kwargs):
        return "reached"

    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint())
    assert exc.value.status_code == 401


def test_build_middleware_patterns_match_the_real_routes():
    """Les regex du middleware oubliaient le préfixe /api/pm-orchestrator."""
    from app.middleware.build_enabled import _is_build_path

    for path in (
        "/api/pm-orchestrator/projects/42/start-build",
        "/api/pm-orchestrator/execute/7/build-tasks",
        "/api/pm-orchestrator/execute/7/build-phases",
        "/api/pm-orchestrator/execute/7/pause-build",
        "/api/pm-orchestrator/execute/7/resume-build",
    ):
        assert _is_build_path(path), f"{path} devrait être reconnu comme route BUILD"

    assert not _is_build_path("/api/pm-orchestrator/execute")
    assert not _is_build_path("/api/pm-orchestrator/execute/7/progress")
