"""
LOT-A bis — kim:SEC-07 : authentification du flux SSE de progression.

`GET /api/pm-orchestrator/execute/{id}/progress/stream` exigeait le JWT en
paramètre d'URL (`token: str = Query(...)`, obligatoire), ce qui forçait le
frontend à le poser dans l'URL — donc dans les journaux d'accès nginx, valide
24 h. La dépendance `get_current_user_from_token_or_header` existait déjà et
essaie l'en-tête `Authorization` AVANT le paramètre d'URL ; elle n'était pas
utilisée ici.

Portée réelle du correctif : le verrou est levé côté serveur. L'en-tête est
désormais accepté, le paramètre d'URL reste accepté (EventSource ne sait pas
envoyer d'en-tête). Tant que le frontend passe le jeton en query string, le
jeton continue d'apparaître dans les journaux. L'exposition est débloquée,
pas refermée.

Second défaut trouvé en vérifiant : la validation manuelle importait
`app.services.auth_service`, module ABSENT du dépôt (seule occurrence dans tout
le code). Le `except Exception` convertissait le ModuleNotFoundError en 401 :
ce flux SSE refusait tout le monde, jeton valide compris.
"""
import pytest

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.auth import create_access_token

STREAM_URL = "/api/pm-orchestrator/execute/{eid}/progress/stream"


def _make_user(db, email: str) -> User:
    user = User(
        email=email,
        hashed_password="not-a-real-hash",
        name="LOT-A bis SSE",
        subscription_tier="pro",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user: User) -> Execution:
    """Exécution en statut terminal : le générateur SSE se ferme aussitôt."""
    project = Project(user_id=user.id, name="LOT-A bis SSE")
    db.add(project)
    db.commit()
    db.refresh(project)

    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.FAILED,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _token_for(user: User) -> str:
    return create_access_token(data={"sub": str(user.id), "email": user.email})


@pytest.fixture
def owner_and_execution(db_session):
    user = _make_user(db_session, "lot-a-bis-sse-owner@example.test")
    return user, _make_execution(db_session, user)


# --------------------------------------------------------------------------
# Les trois chemins demandés
# --------------------------------------------------------------------------

def test_stream_accepts_the_authorization_header(client, owner_and_execution):
    """Le chemin nouveau : plus besoin de mettre le jeton dans l'URL."""
    user, execution = owner_and_execution

    r = client.get(
        STREAM_URL.format(eid=execution.id),
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    # Le flux émet réellement : statut 200 seul ne prouverait que l'en-tête.
    assert "data: " in r.text
    assert f'"execution_id": {execution.id}' in r.text


def test_stream_still_accepts_the_token_query_param(client, owner_and_execution):
    """Non-régression : useExecutionProgress.ts:73 passe toujours ?token=..."""
    user, execution = owner_and_execution

    r = client.get(
        STREAM_URL.format(eid=execution.id),
        params={"token": _token_for(user)},
    )

    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    assert "data: " in r.text
    assert f'"execution_id": {execution.id}' in r.text


def test_stream_rejects_a_request_without_any_credential(client, owner_and_execution):
    """Aucun jeton, ni en-tête ni URL → 401."""
    _, execution = owner_and_execution

    r = client.get(STREAM_URL.format(eid=execution.id))

    assert r.status_code == 401, r.text


# --------------------------------------------------------------------------
# Ce que la substitution ne doit pas perdre
# --------------------------------------------------------------------------

def test_stream_rejects_a_forged_token(client, owner_and_execution):
    _, execution = owner_and_execution

    r = client.get(
        STREAM_URL.format(eid=execution.id),
        headers={"Authorization": "Bearer pas-un-jwt"},
    )

    assert r.status_code == 401, r.text


def test_stream_refuses_another_tenants_execution(client, db_session, owner_and_execution):
    """La vérification de propriété est conservée (404, pas 200)."""
    _, victim_execution = owner_and_execution
    stranger = _make_user(db_session, "lot-a-bis-sse-stranger@example.test")

    r = client.get(
        STREAM_URL.format(eid=victim_execution.id),
        headers={"Authorization": f"Bearer {_token_for(stranger)}"},
    )

    assert r.status_code == 404, r.text


def test_stream_rejects_an_inactive_user(client, db_session, owner_and_execution):
    """Gain de la dépendance commune : elle refuse un compte désactivé."""
    user, execution = owner_and_execution
    user.is_active = False
    db_session.commit()

    r = client.get(
        STREAM_URL.format(eid=execution.id),
        headers={"Authorization": f"Bearer {_token_for(user)}"},
    )

    assert r.status_code == 403, r.text
