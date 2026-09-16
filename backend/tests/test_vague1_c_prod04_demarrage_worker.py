"""
VAGUE 1 / FILE C — PROD-04 = CAL-11 : le demarrage d'un worker ne doit toucher
qu'aux executions dont le job ARQ est reellement absent.

Constat (rapport Astra L422, calibration 15/09 18:0x) : `worker.startup`
marquait FAILED **toutes** les executions RUNNING, sans verifier que leur job
etait mort — y compris celles d'un autre worker (179 tuee par le redemarrage
des workers de calibration alors que son job continuait). Il annulait aussi
tous les jobs en file, qui sont pourtant du travail legitime en attente.

Methode : Redis reel (DB et file posees par le bootstrap hermetique), quatre
executions RUNNING dans quatre situations distinctes, et l'appel de
`startup()` tel que le worker l'appelle. Ce qui compte est **qui** est marque
FAILED et qui ne l'est pas :

- `vivante`  : job en cours dans un autre worker (cle `arq:in-progress:` posee)
               -> ne doit pas bouger ;
- `en_file`  : job enfile, pas encore pris -> ne doit pas bouger, et le job
               doit rester en file (pas d'abort) ;
- `morte`    : job identifie mais absent de Redis -> FAILED, avec le motif ;
- `legacy`   : aucun `arq_job_id` (execution d'avant la colonne) -> pas de
               decision possible sur le job : on ne la tue plus, on le dit.
"""
import asyncio
import logging

import pytest
from arq.constants import in_progress_key_prefix, job_key_prefix
from arq.jobs import Job, JobStatus

from app.models.execution import Execution, ExecutionStatus
from app.models.project import Project
from app.models.user import User
from app.workers.arq_config import ARQ_QUEUE_NAME, get_redis_pool
from app.workers.worker import startup


def _make_execution(db, user, project, nom, job_id):
    execution = Execution(
        project_id=project.id,
        user_id=user.id,
        selected_agents=["pm", "ba"],
        agent_execution_status={},
        status=ExecutionStatus.RUNNING,
        execution_state="sds_phase3_running",
        arq_job_id=job_id,
        arq_queue_name=ARQ_QUEUE_NAME if job_id else None,
        logs=f"[{nom}]",
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


@pytest.fixture
def montage(db_session):
    user = User(
        email="vague1c-prod04@example.test",
        hashed_password="not-a-real-hash",
        name="Vague1 C",
        subscription_tier="team",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    project = Project(user_id=user.id, name="PROD-04")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    suffixe = f"{ARQ_QUEUE_NAME}-prod04"
    execs = {
        "vivante": _make_execution(db_session, user, project, "vivante", f"{suffixe}-vivante"),
        "en_file": _make_execution(db_session, user, project, "en_file", f"{suffixe}-en-file"),
        "morte": _make_execution(db_session, user, project, "morte", f"{suffixe}-morte"),
        "legacy": _make_execution(db_session, user, project, "legacy", None),
    }
    return {"user": user, "project": project, "execs": execs}


async def _poser_le_contexte_redis(montage):
    """Pose dans Redis l'etat que le worker verrait : un job en cours chez un
    autre worker, un job en file. Rend le pool (a fermer) et les cles a purger."""
    pool = await get_redis_pool()
    execs = montage["execs"]
    vivante = execs["vivante"]
    en_file = execs["en_file"]

    # Un autre worker execute `vivante` : arq pose cette cle a la prise du job.
    await pool.psetex(in_progress_key_prefix + vivante.arq_job_id, 120_000, b"1")

    # `en_file` attend un worker : enfilage reel, identifiant deterministe.
    job = await pool.enqueue_job(
        "execute_sds_task",
        execution_id=en_file.id,
        project_id=montage["project"].id,
        _queue_name=ARQ_QUEUE_NAME,
        _job_id=en_file.arq_job_id,
    )
    assert job is not None and (await job.status()) == JobStatus.queued

    cles = [
        in_progress_key_prefix + vivante.arq_job_id,
        job_key_prefix + en_file.arq_job_id,
    ]
    return pool, cles


async def _purger(pool, cles, montage):
    for cle in cles:
        await pool.delete(cle)
    await pool.zrem(ARQ_QUEUE_NAME, montage["execs"]["en_file"].arq_job_id)
    await pool.aclose()


def _relire(db_session, execution):
    db_session.expire_all()
    return db_session.query(Execution).get(execution.id)


@pytest.mark.asyncio
async def test_le_demarrage_ne_tue_pas_une_execution_dont_le_job_tourne_ailleurs(
    db_session, montage
):
    """Le cas de la calibration : un job en cours dans un autre worker."""
    pool, cles = await _poser_le_contexte_redis(montage)
    try:
        await startup({"redis": pool})
        vivante = _relire(db_session, montage["execs"]["vivante"])
        assert vivante.status == ExecutionStatus.RUNNING, (
            f"execution vivante marquee {vivante.status.value} par le demarrage "
            f"alors que son job est en cours dans Redis"
        )
    finally:
        await _purger(pool, cles, montage)


@pytest.mark.asyncio
async def test_le_demarrage_ne_tue_pas_une_execution_en_file_et_garde_son_job(
    db_session, montage
):
    """Un job en file est du travail en attente, pas un fantome."""
    pool, cles = await _poser_le_contexte_redis(montage)
    try:
        await startup({"redis": pool})
        en_file = _relire(db_session, montage["execs"]["en_file"])
        assert en_file.status == ExecutionStatus.RUNNING
        statut_job = await Job(en_file.arq_job_id, pool, _queue_name=ARQ_QUEUE_NAME).status()
        assert statut_job == JobStatus.queued, (
            f"le job en file a ete retire par le demarrage : {statut_job}"
        )
    finally:
        await _purger(pool, cles, montage)


@pytest.mark.asyncio
async def test_le_demarrage_marque_failed_une_execution_dont_le_job_est_absent(
    db_session, montage
):
    """Controle positif : le nettoyage doit encore faire son travail quand le
    job a vraiment disparu (worker tue en plein vol, cle expiree)."""
    pool, cles = await _poser_le_contexte_redis(montage)
    try:
        await startup({"redis": pool})
        morte = _relire(db_session, montage["execs"]["morte"])
        assert morte.status == ExecutionStatus.FAILED
        assert morte.execution_state == "failed", (
            "le statut et l'etat de la machine doivent dire la meme chose"
        )
        assert "absent" in (morte.logs or "").lower() and morte.arq_job_id in (morte.logs or ""), (
            f"le motif doit nommer le job absent : {morte.logs!r}"
        )
    finally:
        await _purger(pool, cles, montage)


@pytest.mark.asyncio
async def test_le_demarrage_ne_decide_pas_sans_identifiant_de_job(
    db_session, montage, caplog
):
    """Regle 6 — sans `arq_job_id`, rien ne permet de dire si le job vit. On ne
    tue pas sur le seul statut ; on le dit en WARNING, avec l'identifiant."""
    pool, cles = await _poser_le_contexte_redis(montage)
    try:
        with caplog.at_level(logging.WARNING, logger="arq.worker"):
            await startup({"redis": pool})
        legacy = _relire(db_session, montage["execs"]["legacy"])
        assert legacy.status == ExecutionStatus.RUNNING
        assert any(
            str(legacy.id) in r.getMessage() and "arq_job_id" in r.getMessage()
            for r in caplog.records
        ), "l'execution sans identifiant de job doit etre nommee dans le journal"
    finally:
        await _purger(pool, cles, montage)


@pytest.mark.asyncio
async def test_sans_redis_le_demarrage_ne_touche_a_rien(db_session, montage):
    """Sans connexion Redis, aucune decision n'est possible : rien ne bouge."""
    await startup({})
    for nom, execution in montage["execs"].items():
        relue = _relire(db_session, execution)
        assert relue.status == ExecutionStatus.RUNNING, nom
