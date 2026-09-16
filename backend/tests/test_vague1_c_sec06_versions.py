"""
VAGUE 1 / FILE C — SEC-06 (diff de la file A) : l'allocation d'un numero de
version de SDS doit etre serialisee dans l'orchestrateur aussi.

La route de snapshot alloue sous verrou consultatif depuis la file A ; les deux
createurs de `SDSVersion` qui vivent dans l'orchestrateur lisaient encore
`project.current_sds_version + 1` sans verrou.

Ce test observe le verrou **pose** (l'ordre SQL emis), et non ses effets sous
concurrence reelle : deux transactions simultanees demanderaient deux
connexions et une base partagee, ce que la session de test ne fournit pas. Ce
qui est verifie ici est donc : la serialisation est demandee, sur le bon espace
de verrous, pour le bon projet, et AVANT la lecture du numero courant.
"""
import pytest
from sqlalchemy import event

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2


@pytest.fixture
def contexte(db_session):
    user = User(
        email="vague1c-sec06@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C SEC-06",
        subscription_tier="pro",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="SEC-06", current_sds_version=2)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm"],
        agent_execution_status={},
        status=ExecutionStatus.COMPLETED,
        execution_state="sds_complete",
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return {"user": user, "project": project, "execution": execution}


@pytest.fixture
def ordres_sql(db_session):
    vus = []

    def _ecouter(conn, cursor, statement, parameters, context, executemany):
        vus.append((statement, parameters))

    event.listen(db_session.bind, "before_cursor_execute", _ecouter)
    yield vus
    event.remove(db_session.bind, "before_cursor_execute", _ecouter)


def _verrous(ordres):
    return [
        (s, p) for s, p in ordres if "pg_advisory_xact_lock" in s
    ]


def test_la_creation_de_version_prend_le_verrou(db_session, contexte, ordres_sql, tmp_path):
    fichier = tmp_path / "SDS.docx"
    fichier.write_bytes(b"un livrable")

    service = PMOrchestratorServiceV2(db_session)
    service._create_sds_version(
        contexte["project"], contexte["execution"], str(fichier)
    )

    verrous = _verrous(ordres_sql)
    assert verrous, (
        "aucun verrou consultatif demande : deux creations concurrentes "
        "allouent le meme numero de version (SEC-06)"
    )
    _, params = verrous[0]
    assert 6006 in tuple(params) or 6006 in tuple(params.values() if hasattr(params, "values") else ())
    assert contexte["project"].id in tuple(
        params.values() if hasattr(params, "values") else params
    )


def test_le_verrou_precede_l_insertion(db_session, contexte, ordres_sql, tmp_path):
    """Un verrou pose apres l'insertion ne serialiserait rien.

    `_create_sds_version` fait `db.add` sans commit — c'est l'appelant qui
    valide. On force donc le flush ici pour voir l'INSERT partir, et on
    compare les positions.
    """
    fichier = tmp_path / "SDS.docx"
    fichier.write_bytes(b"un livrable")

    service = PMOrchestratorServiceV2(db_session)
    service._create_sds_version(
        contexte["project"], contexte["execution"], str(fichier)
    )
    db_session.flush()

    positions_verrou = [
        i for i, (s, _) in enumerate(ordres_sql) if "pg_advisory_xact_lock" in s
    ]
    positions_insert = [
        i for i, (s, _) in enumerate(ordres_sql)
        if "INSERT INTO sds_versions" in s or "insert into sds_versions" in s.lower()
    ]
    assert positions_verrou and positions_insert
    assert positions_verrou[0] < positions_insert[0], (
        "le verrou est demande apres l'insertion : il ne protege rien"
    )
