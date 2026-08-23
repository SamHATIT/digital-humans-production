"""
VAGUE 3 — §6 : `validation_gate_routes` enfilait un job que la tache refuse.

Le defaut : la branche de rejet passait `annotations=submission.annotations` a
`execute_sds_task`, qui n'a pas ce parametre (`workers/tasks.py:9`). ARQ
serialise les kwargs sans les valider : **l'enfilage reussit, le job meurt en
`TypeError` dans le worker**. Cote client, la porte est rejetee, la reponse est
200, et rien ne redemarre. Le rejet avec commentaires ne relancait donc rien.

Ce que la verification des consommateurs a montre (regle 2) : **personne ne lit
ces annotations**. Aucun agent, aucun prompt ; `execute_workflow` n'a pas de
parametre `annotations` ; `execution.validation_history` est ecrit et jamais
relu ailleurs que dans le service de portes. Le kwarg etait un passe-plat vers
un consommateur inexistant.

Le brancher jusqu'a `execute_workflow` creerait donc un parametre inerte de
plus — meme famille que `BuildEnabledMiddleware` et `require_feature` avant la
vague 1. On retire le passe-plat, on garde la trace : les annotations restent
durablement en base, ecrites par `ValidationGateService`.
"""
import inspect

import pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.workers import tasks as worker_tasks

GATE_URL = "/api/pm-orchestrator/execute/{eid}/validation-gate/submit"


def _make_user(db):
    user = User(
        email="vague3-annot@example.test",
        hashed_password="not-a-real-hash",
        name="Vague3 annotations",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, status):
    project = Project(user_id=user.id, name="Vague3 annotations")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=status,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def _authenticate_as(user):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def enfiles(monkeypatch):
    calls = []

    class _Job:
        job_id = "test-job"

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            calls.append({"name": name, "kwargs": kw})
            return _Job()

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.validation_gate_routes.get_redis_pool",
        _get_pool,
        raising=False,
    )
    return calls


@pytest.fixture
def porte(monkeypatch):
    def _fabrique(nom):
        def _submit(self, execution_id, approved, annotations=None):
            return {"success": True, "gate": nom}

        from app.services.validation_gate_service import ValidationGateService

        monkeypatch.setattr(ValidationGateService, "submit_validation", _submit)

    return _fabrique


def _parametres_acceptes(fonction) -> set:
    """Noms de parametres que la tache ARQ accepte, `ctx` exclu."""
    return {
        nom
        for nom in inspect.signature(fonction).parameters
        if nom != "ctx"
    }


# --------------------------------------------------------------------------
# Le job enfile doit etre appelable par la tache qui le recevra
# --------------------------------------------------------------------------

def test_un_rejet_avec_annotations_enfile_un_job_appelable(
    client, db_session, enfiles, porte
):
    """Le coeur du defaut. ARQ ne valide pas les kwargs : le job partait, et
    mourait dans le worker."""
    porte("after_expert_specs")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_EXPERT_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id),
        json={"approved": False, "annotations": "il manque la regle de gestion 4"},
    )
    assert r.status_code == 200, r.text
    assert len(enfiles) == 1

    job = enfiles[0]
    accepte = _parametres_acceptes(worker_tasks.execute_sds_task)
    passes = set(job["kwargs"]) - {"_queue_name"}
    refuses = passes - accepte
    assert not refuses, (
        f"le job {job['name']!r} porte des kwargs que la tache refuse : "
        f"{sorted(refuses)}. Il mourra en TypeError dans le worker, et le rejet "
        f"ne relancera rien."
    )


@pytest.mark.parametrize(
    "gate, statut",
    [
        ("after_expert_specs", ExecutionStatus.WAITING_EXPERT_VALIDATION),
        ("after_sds_generation", ExecutionStatus.WAITING_SDS_VALIDATION),
        ("after_build_code", ExecutionStatus.WAITING_BUILD_VALIDATION),
    ],
)
def test_aucune_porte_n_enfile_de_kwarg_refuse(
    client, db_session, enfiles, porte, gate, statut
):
    """Les trois portes, en rejet — le cas qui portait le defaut."""
    porte(gate)
    user = _make_user(db_session)
    execution = _make_execution(db_session, user, statut)
    execution.execution_state = "sds_phase4_complete"
    db_session.commit()
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id),
        json={"approved": False, "annotations": "a revoir"},
    )
    assert r.status_code == 200, r.text

    for job in enfiles:
        tache = getattr(worker_tasks, job["name"])
        refuses = (set(job["kwargs"]) - {"_queue_name"}) - _parametres_acceptes(tache)
        assert not refuses, (
            f"porte {gate} -> {job['name']} : kwargs refuses {sorted(refuses)}"
        )


def test_le_rejet_dit_ce_qu_il_advient_des_annotations(
    client, db_session, enfiles, porte
):
    """Regle 5 : les annotations ne sont relues par aucun agent — c'est un
    constat, pas un correctif a faire ici. Mais le taire laisserait croire au
    client que son commentaire va etre pris en compte."""
    porte("after_expert_specs")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_EXPERT_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(
        GATE_URL.format(eid=execution.id),
        json={"approved": False, "annotations": "il manque la regle 4"},
    )
    assert r.status_code == 200, r.text
    corps = r.json()

    assert corps["annotations"] == "il manque la regle 4", (
        "l'annotation doit revenir au client, elle est conservee"
    )
    assert "annotations_applied" in corps, (
        "la reponse doit dire si les annotations sont relues par les agents"
    )
    assert corps["annotations_applied"] is False


def test_une_approbation_ne_parle_pas_d_annotations(
    client, db_session, enfiles, porte
):
    """Controle : pas de bruit sur le chemin ou il n'y a rien a signaler."""
    porte("after_expert_specs")
    user = _make_user(db_session)
    execution = _make_execution(
        db_session, user, ExecutionStatus.WAITING_EXPERT_VALIDATION
    )
    _authenticate_as(user)

    r = client.post(GATE_URL.format(eid=execution.id), json={"approved": True})
    assert r.status_code == 200, r.text
    assert "annotations_applied" not in r.json()


# --------------------------------------------------------------------------
# Le constat qui justifie de ne pas cabler plus loin
# --------------------------------------------------------------------------

def test_aucun_consommateur_d_annotations_cote_workflow():
    """Regle 2 — verifier les appelants avant de proposer une architecture.

    Si `execute_workflow` acquerait un parametre `annotations`, il faudrait le
    cabler. Tant qu'il n'en a pas, brancher un passe-plat jusqu'a lui
    creerait un dispositif inerte de plus.

    Ce test rougira le jour ou quelqu'un ajoutera ce parametre : c'est
    exactement le moment de rebrancher la chaine, et de relire §6.
    """
    from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2

    parametres = inspect.signature(
        PMOrchestratorServiceV2.execute_workflow
    ).parameters
    assert "annotations" not in parametres, (
        "execute_workflow accepte desormais des annotations : rebrancher la "
        "chaine depuis validation_gate_routes et relire SPEC_VAGUE3 §6."
    )
