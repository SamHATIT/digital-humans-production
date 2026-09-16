"""
VAGUE 1 / FILE C — CAL-01 (delai du job fixe pour tous les profils) et CAL-07
(aucune annulation possible autrement qu'en redemarrant le worker).

CAL-01, mesure du 15/09 : `job_timeout = 3600` est une constante globale de
`WorkerSettings`. Le job de reprise de l'execution 172, demarre a 09:24:31, a
ete annule a 10:24:31 en plein appel de Marcus. Un 30B local a 12,4 tok/s ne
tient pas dans une heure ; un profil cloud, si. Le delai doit dependre du
profil de routage du worker.

CAL-07 : « aucune annulation de job (`allow_abort_jobs` absent), aucun point
d'arret cooperatif dans `execute_workflow` : seul un redemarrage du worker
interrompt une execution, et il tue toutes les autres ». Le redemarrage etait
donc le seul bouton d'arret — celui-la meme que PROD-04 vient de desarmer.

L'annulation cooperative se lit entre deux phases : le travail deja produit est
conserve, l'execution se ferme en CANCELLED, et aucun agent supplementaire
n'est appele.
"""
import logging

import pytest

from app.main import app
from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.services.pm_orchestrator_service_v2 import PMOrchestratorServiceV2
from app.utils.dependencies import (
    get_current_user,
    get_current_user_from_token_or_header,
)
from app.workers.worker import WorkerSettings

CANCEL_URL = "/api/pm-orchestrator/execute/{eid}/cancel"


def _make_user(db, suffixe=""):
    user = User(
        email=f"vague1c-cal07{suffixe}@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C CAL-07",
        subscription_tier="team",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_execution(db, user, status=ExecutionStatus.RUNNING, etat="sds_phase2_running"):
    project = Project(user_id=user.id, name="CAL-07")
    db.add(project)
    db.commit()
    db.refresh(project)
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=status,
        execution_state=etat,
        arq_job_id="job-cal07",
        arq_queue_name="file-du-worker",
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


# --------------------------------------------------------------------------
# CAL-01 — le delai du job depend du profil de routage
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "profil, attendu, pourquoi",
    [
        ("cloud", 3600, "une heure suffit a Sonnet/Opus"),
        ("freemium", 3600, "profil cloud lui aussi"),
        (
            "gpu_local",
            21600,
            "12,4 tok/s mesures le 15/09 : une phase depasse l'heure",
        ),
        ("test_gpu_complet", 21600, "meme materiel, meme ordre de grandeur"),
    ],
)
def test_le_delai_du_job_suit_le_profil(monkeypatch, profil, attendu, pourquoi):
    from app.workers.job_timeout import job_timeout_seconds

    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", profil)
    monkeypatch.delenv("DH_JOB_TIMEOUT_SECONDS", raising=False)
    assert job_timeout_seconds() == attendu, pourquoi


def test_le_delai_du_job_est_surchargeable(monkeypatch):
    """Un exploitant doit pouvoir trancher sans modifier le code — c'est ce que
    la calibration a fait a la main le 15/09 (3600 -> 21600, commentaire dans
    `worker.py`), puis defait le 16/09."""
    from app.workers.job_timeout import job_timeout_seconds

    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", "cloud")
    monkeypatch.setenv("DH_JOB_TIMEOUT_SECONDS", "7200")
    assert job_timeout_seconds() == 7200


def test_un_profil_inconnu_prend_le_delai_cloud_et_le_dit(monkeypatch, caplog):
    """Regle 6 : pas de repli silencieux. Le worker demarre — refuser
    l'empecherait de tourner sur un profil legitime mais non liste — mais il
    dit lequel et quelle valeur il retient."""
    from app.workers.job_timeout import job_timeout_seconds

    monkeypatch.setenv("DH_DEPLOYMENT_PROFILE", "profil_maison")
    monkeypatch.delenv("DH_JOB_TIMEOUT_SECONDS", raising=False)
    with caplog.at_level(logging.WARNING):
        valeur = job_timeout_seconds()
    assert valeur == 3600
    assert any("profil_maison" in r.getMessage() for r in caplog.records)


def test_une_surcharge_illisible_est_refusee(monkeypatch):
    """Une valeur non entiere n'est pas devinee."""
    from app.workers.job_timeout import job_timeout_seconds

    monkeypatch.setenv("DH_JOB_TIMEOUT_SECONDS", "une heure")
    with pytest.raises(ValueError):
        job_timeout_seconds()


def test_le_worker_utilise_ce_delai():
    """Sur l'objet, pas sur la source : `WorkerSettings.job_timeout` etait une
    constante litterale."""
    from app.workers.job_timeout import job_timeout_seconds

    assert WorkerSettings.job_timeout == job_timeout_seconds()


def test_le_worker_accepte_les_annulations():
    """CAL-07 : sans `allow_abort_jobs`, `Job.abort()` ne fait rien — le seul
    moyen d'arreter une execution restait le redemarrage du worker, qui tuait
    toutes les autres (PROD-04)."""
    assert getattr(WorkerSettings, "allow_abort_jobs", False) is True


# --------------------------------------------------------------------------
# CAL-07 — annulation cooperative
# --------------------------------------------------------------------------

@pytest.fixture
def pool_double(monkeypatch):
    abandons = []

    class _Job:
        def __init__(self, job_id, queue):
            self.job_id = job_id
            self.queue = queue

        async def abort(self, **kw):
            abandons.append((self.job_id, self.queue))
            return True

    class _Pool:
        async def enqueue_job(self, name, *a, **kw):
            return _Job(kw.get("_job_id", "double"), kw.get("_queue_name"))

    async def _get_pool():
        return _Pool()

    monkeypatch.setattr(
        "app.api.routes.orchestrator.execution_routes.get_redis_pool", _get_pool
    )
    monkeypatch.setattr(
        "app.api.routes.orchestrator.execution_routes.Job",
        lambda job_id, redis, _queue_name=None: _Job(job_id, _queue_name),
        raising=False,
    )
    return abandons


def test_une_annulation_est_enregistree_sur_l_execution(
    client, db_session, pool_double
):
    user = _make_user(db_session, "-route")
    execution = _make_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(CANCEL_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.cancel_requested_at is not None, (
        "l'annulation n'est notee nulle part : l'orchestrateur ne peut pas la lire"
    )


def test_une_annulation_abandonne_le_job_sur_sa_propre_file(
    client, db_session, pool_double
):
    """L'abandon doit viser la file sur laquelle l'execution a ete enfilee
    (CAL-07), pas celle du worker qui recoit la requete."""
    user = _make_user(db_session, "-abort")
    execution = _make_execution(db_session, user)
    _authenticate_as(user)

    r = client.post(CANCEL_URL.format(eid=execution.id))
    assert r.status_code == 202, r.text
    assert pool_double, "aucun abandon de job demande"
    assert pool_double[0] == ("job-cal07", "file-du-worker")


def test_une_execution_terminee_ne_s_annule_pas(client, db_session, pool_double):
    """Controle negatif : annuler un travail deja livre n'a pas de sens."""
    user = _make_user(db_session, "-terminee")
    execution = _make_execution(
        db_session, user, status=ExecutionStatus.COMPLETED, etat="sds_complete"
    )
    _authenticate_as(user)

    r = client.post(CANCEL_URL.format(eid=execution.id))
    assert r.status_code == 400, r.text
    assert pool_double == []


@pytest.mark.asyncio
async def test_l_orchestrateur_s_arrete_entre_deux_phases(db_session, monkeypatch):
    """Le point d'arret cooperatif : l'annulation demandee pendant la phase 1
    est lue avant la phase 2, et Olivia n'est pas appelee."""
    from datetime import datetime, timezone

    user = _make_user(db_session, "-coop")
    execution = _make_execution(db_session, user, etat="draft")
    execution.cancel_requested_at = datetime.now(timezone.utc)
    db_session.commit()

    appels = []

    async def _faux_run_agent(self, agent_id, mode=None, input_data=None, **kwargs):
        appels.append(agent_id)
        return {
            "success": True,
            "output": {
                "content": {"business_requirements": [{"br_id": "BR-001"}]},
                "metadata": {"tokens_used": 1},
            },
        }

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _faux_run_agent)
    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )

    service = PMOrchestratorServiceV2(db_session)
    resultat = await service.execute_workflow(
        execution_id=execution.id,
        project_id=execution.project_id,
        selected_agents=["pm", "ba"],
    )

    assert appels == [], f"des agents ont tourne apres l'annulation : {appels}"
    assert resultat.get("status") == "cancelled" or resultat.get("cancelled") is True, (
        f"l'annulation n'est pas dite dans le resultat : {resultat}"
    )

    db_session.expire_all()
    relue = db_session.query(Execution).get(execution.id)
    assert relue.status == ExecutionStatus.CANCELLED
    assert relue.execution_state == "cancelled"


@pytest.mark.asyncio
async def test_sans_annulation_le_workflow_avance(db_session, monkeypatch):
    """Controle negatif : le point d'arret ne doit pas arreter une execution
    que personne n'a annulee."""
    user = _make_user(db_session, "-coop2")
    execution = _make_execution(db_session, user, etat="draft")

    appels = []

    async def _faux_run_agent(self, agent_id, mode=None, input_data=None, **kwargs):
        appels.append(agent_id)
        raise RuntimeError("arret controle : la phase 1 a bien demarre")

    async def _pas_de_metadata_sf(self, execution_id, project=None):
        return {"success": False, "error": "test", "full_metadata": {}, "summary": {}}

    monkeypatch.setattr(PMOrchestratorServiceV2, "_run_agent", _faux_run_agent)
    monkeypatch.setattr(
        PMOrchestratorServiceV2, "_get_salesforce_metadata", _pas_de_metadata_sf
    )

    service = PMOrchestratorServiceV2(db_session)
    await service.execute_workflow(
        execution_id=execution.id,
        project_id=execution.project_id,
        selected_agents=["pm", "ba"],
    )
    assert appels, "le workflow ne demarre plus alors qu'aucune annulation n'est demandee"
