"""
VAGUE 1 / FILE C — l'enfilage doit etre identifie (PROD-04) et la file
memorisee (CAL-07).

PROD-04 : le correctif du demarrage (`_reconcilier_executions_actives`) juge
chaque execution RUNNING sur son `arq_job_id`. Tant que les routes ne le
posent pas, toutes les executions tombent dans le cas « sans identifiant » :
plus rien n'est reconcilie, et le dispositif est declare sans etre operant
(regle 6). Il doit etre pose **avant** l'enfilage : entre les deux, une
execution RUNNING sans job connu n'est rattrapable par personne.

CAL-07 : mesure du 15/09 — `/resume` et la reprise d'architecture enfilent
toujours sur `digital-humans`, si bien que l'execution 174 a ete reprise sur
Muse au lieu de DeepSeek Flash. La file utilisee au lancement doit etre
memorisee sur l'execution et reutilisee par les reprises.

Ces tests observent ce que les routes passent reellement a `enqueue_job` : le
pool est remplace par un double qui enregistre `_job_id` et `_queue_name`, et
qui relit la base au moment de l'appel pour verifier l'ordre des ecritures.
"""
import pytest

from app.main import app
from app.models.business_requirement import BusinessRequirement, BRStatus
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.workers.arq_config import ARQ_QUEUE_NAME

EXECUTE_URL = "/api/pm-orchestrator/execute"
RESUME_URL = "/api/pm-orchestrator/execute/{eid}/resume"
RETRY_URL = "/api/pm-orchestrator/execute/{eid}/retry"

MODULES_QUI_ENFILENT = (
    "app.api.routes.orchestrator.execution_routes",
    "app.api.routes.orchestrator.retry_routes",
    "app.api.routes.orchestrator.validation_gate_routes",
)


def _make_user(db, tier="team"):
    user = User(
        email=f"vague1c-enfilage-{tier}@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C enfilage",
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_project(db, user):
    project = Project(user_id=user.id, name="Enfilage identifie")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _authenticate_as(user):
    async def _override():
        return user

    app.dependency_overrides[get_current_user] = _override
    app.dependency_overrides[get_current_user_from_token_or_header] = _override


@pytest.fixture
def enfiles(monkeypatch, db_session):
    """Double du pool ARQ. Relit la base a l'instant de l'enfilage : ce que la
    route a deja ecrit y est visible, ce qu'elle ecrirait apres ne l'est pas."""
    calls = []

    class _Job:
        def __init__(self, job_id):
            self.job_id = job_id

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            job_id = kw.get("_job_id")
            eid = kw.get("execution_id")
            vu_en_base = None
            if eid is not None:
                db_session.expire_all()
                execution = db_session.query(Execution).get(eid)
                if execution is not None:
                    vu_en_base = (execution.arq_job_id, execution.arq_queue_name)
            calls.append({
                "name": name,
                "kwargs": kw,
                "job_id": job_id,
                "queue": kw.get("_queue_name"),
                "en_base_a_l_enfilage": vu_en_base,
            })
            return _Job(job_id or "double-sans-id")

    async def _get_pool():
        return _Pool()

    for module in MODULES_QUI_ENFILENT:
        monkeypatch.setattr(f"{module}.get_redis_pool", _get_pool, raising=False)
    return calls


# --------------------------------------------------------------------------
# PROD-04 — l'identifiant de job est pose, et pose avant l'enfilage
# --------------------------------------------------------------------------

def test_le_lancement_pose_un_identifiant_de_job_sur_l_execution(
    client, db_session, enfiles
):
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    _authenticate_as(user)

    r = client.post(
        EXECUTE_URL, json={"project_id": project.id, "selected_agents": ["pm", "ba"]}
    )
    assert r.status_code == 202, r.text

    execution = db_session.query(Execution).get(r.json()["execution_id"])
    assert execution.arq_job_id, (
        "l'execution n'a pas d'arq_job_id : le demarrage d'un worker ne peut "
        "pas savoir si son job vit (PROD-04)"
    )
    assert enfiles[0]["job_id"] == execution.arq_job_id, (
        f"le job enfile ({enfiles[0]['job_id']!r}) n'est pas celui note sur "
        f"l'execution ({execution.arq_job_id!r})"
    )


def test_l_identifiant_est_ecrit_avant_l_enfilage(client, db_session, enfiles):
    """Ordre des ecritures : sans lui, une panne entre les deux laisse une
    execution RUNNING dont aucun worker ne connait le job."""
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    _authenticate_as(user)

    r = client.post(
        EXECUTE_URL, json={"project_id": project.id, "selected_agents": ["pm", "ba"]}
    )
    assert r.status_code == 202, r.text

    job_id = enfiles[0]["job_id"]
    assert job_id, "aucun _job_id passe a enqueue_job : rien a verifier"
    vu = enfiles[0]["en_base_a_l_enfilage"]
    assert vu is not None and vu[0] == job_id, (
        f"a l'instant de l'enfilage, la base portait {vu!r} — l'identifiant "
        f"est donc ecrit apres coup, ou pas du tout"
    )


def test_le_lancement_memorise_la_file(client, db_session, enfiles):
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    _authenticate_as(user)

    r = client.post(
        EXECUTE_URL, json={"project_id": project.id, "selected_agents": ["pm", "ba"]}
    )
    assert r.status_code == 202, r.text

    execution = db_session.query(Execution).get(r.json()["execution_id"])
    assert execution.arq_queue_name == ARQ_QUEUE_NAME
    assert enfiles[0]["queue"] == ARQ_QUEUE_NAME


# --------------------------------------------------------------------------
# CAL-07 — la reprise reutilise la file memorisee
# --------------------------------------------------------------------------

def _execution_echouee_reprenable(db, user, project, file):
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={"pm": {"state": "completed"}},
        status=ExecutionStatus.FAILED,
        last_completed_phase="phase1_pm",
        arq_job_id="ancien-job",
        arq_queue_name=file,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    db.add(
        BusinessRequirement(
            project_id=project.id,
            execution_id=execution.id,
            br_id="BR-001",
            requirement="Une exigence validee",
            order_index=0,
            status=BRStatus.VALIDATED,
        )
    )
    db.commit()
    return execution


def test_resume_reprend_sur_la_file_memorisee(client, db_session, enfiles):
    """CAL-07 : l'execution 174 a ete reprise sur le mauvais worker parce que
    la route enfilait toujours sur la file par defaut."""
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    execution = _execution_echouee_reprenable(
        db_session, user, project, "file-du-profil-gpu"
    )
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["queue"] == "file-du-profil-gpu", (
        f"la reprise a enfile sur {enfiles[0]['queue']!r} au lieu de la file "
        f"memorisee sur l'execution"
    )


def test_resume_sans_file_memorisee_prend_celle_du_worker(
    client, db_session, enfiles
):
    """Controle negatif : sans file memorisee (executions d'avant la colonne),
    la reprise ne doit pas inventer une file — elle prend celle du worker."""
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    execution = _execution_echouee_reprenable(db_session, user, project, None)
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["queue"] == ARQ_QUEUE_NAME


def test_resume_pose_un_nouvel_identifiant_de_job(client, db_session, enfiles):
    """Une reprise est une nouvelle tentative : elle ne doit pas garder
    l'identifiant du job mort, sinon le demarrage suivant jugerait la reprise
    sur un job qui n'existe plus."""
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    execution = _execution_echouee_reprenable(db_session, user, project, None)
    _authenticate_as(user)

    r = client.post(RESUME_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.arq_job_id not in (None, "ancien-job")
    assert relue.arq_job_id == enfiles[0]["job_id"]


def test_retry_pose_un_identifiant_et_reprend_la_file(client, db_session, enfiles):
    user = _make_user(db_session)
    project = _make_project(db_session, user)
    execution = _execution_echouee_reprenable(
        db_session, user, project, "file-du-profil-gpu"
    )
    _authenticate_as(user)

    r = client.post(RETRY_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert enfiles[0]["queue"] == "file-du-profil-gpu"

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.arq_job_id == enfiles[0]["job_id"]


# --------------------------------------------------------------------------
# La file n'est plus ecrite en dur (regression de la vague 0 / AS-02)
# --------------------------------------------------------------------------

def test_aucune_route_orchestrator_n_ecrit_le_nom_de_file_en_dur():
    """AS-02 avait ramene les sept sites a `arq_config.ARQ_QUEUE_NAME`.
    `validation_gate_routes.py` porte encore `_queue_name="digital-humans"` :
    une porte validee en test enfilerait sur la file de production."""
    import inspect

    from app.api.routes.orchestrator import (
        execution_routes,
        retry_routes,
        validation_gate_routes,
    )

    for module in (execution_routes, retry_routes, validation_gate_routes):
        source = inspect.getsource(module)
        lignes = [
            ligne
            for ligne in source.splitlines()
            if '"digital-humans"' in ligne and not ligne.strip().startswith("#")
        ]
        assert not lignes, (
            f"{module.__name__} ecrit le nom de file en dur : {lignes}"
        )
