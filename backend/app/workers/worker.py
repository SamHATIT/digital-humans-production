"""ARQ worker entry point.

Run with: python -m arq app.workers.worker.WorkerSettings
"""
import logging
from arq import cron
from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus
from app.workers.arq_config import ARQ_QUEUE_NAME, REDIS_SETTINGS
from app.workers.job_timeout import job_timeout_seconds
from app.workers.retention import (
    purge_chat_logs_task,
    purge_conversations_projet_task,
)
from app.workers.tasks import execute_sds_task, resume_architecture_task, execute_build_task

logger = logging.getLogger("arq.worker")


async def _job_absent_de_redis(redis, job_id: str, queue_name: str):
    """Le job `job_id` est-il absent de Redis ?

    VAGUE 1 / FILE C (PROD-04 = CAL-11). Rend `(absent, statut)`. `absent` ne
    vaut True que pour `JobStatus.not_found` : ni resultat, ni cle
    `arq:in-progress:` (un worker l'execute), ni entree en file. Un job
    `complete`, `in_progress` ou `queued` n'est PAS un fantome — c'est
    precisement ce que le nettoyage global detruisait.

    Rend `(False, None)` si Redis ne repond pas : sans reponse, pas de
    decision (regle 6 — on ne devine pas).
    """
    try:
        statut = await Job(job_id, redis, _queue_name=queue_name).status()
    except Exception as e:  # Redis injoignable, file inconnue...
        logger.warning(
            f"[Startup] Statut du job {job_id} illisible ({e}) — aucune decision prise"
        )
        return False, None
    return statut == JobStatus.not_found, statut


def _marquer_echouee(db, execution, job_id: str, statut) -> None:
    """Passe une execution abandonnee en FAILED, statut ET etat de la machine.

    L'ancien nettoyage n'ecrivait que `status` : `execution_state` restait a
    `sds_phase3_running`, si bien que l'ecran de suivi et la machine a etats se
    contredisaient (CAL-02/CAL-04).
    """
    from app.models.execution import ExecutionStatus
    from app.services.execution_state import ExecutionStateMachine

    motif = (
        f"[Worker restart] Job ARQ {job_id} absent de Redis (statut={statut}) — "
        f"execution abandonnee, reprenez-la avec /resume."
    )
    try:
        ExecutionStateMachine(db, execution.id).transition_to(
            "failed", metadata={"raison": "job_arq_absent", "job_id": job_id}
        )
    except Exception as e:
        logger.warning(
            f"[Startup] Transition vers 'failed' refusee pour l'execution "
            f"{execution.id} ({e}) — statut et etat poses directement"
        )
        execution.status = ExecutionStatus.FAILED
        execution.execution_state = "failed"
    execution.logs = (execution.logs or "") + "\n" + motif
    db.commit()
    logger.warning(f"[Startup] Execution {execution.id} → FAILED : {motif}")


async def _reconcilier_executions_actives(ctx: dict, redis) -> dict:
    """Ne nettoie que les executions dont le job ARQ est reellement absent.

    PROD-04 = CAL-11 (rapport Astra L422 ; mesure de calibration du 15/09
    18:0x). Avant : le demarrage marquait FAILED **toutes** les executions
    RUNNING, sans propriete ni preuve d'abandon — le redemarrage des trois
    workers de calibration a tue l'execution 179, qui tournait dans le worker
    principal. Avec plusieurs workers ou un redeploiement pendant un run,
    l'incoherence etait garantie.

    Desormais chaque execution RUNNING est jugee sur son job :

    - job en cours, en file ou termine   -> on ne touche a rien ;
    - job absent de Redis                -> FAILED, avec le motif dans `logs` ;
    - pas d'`arq_job_id` (execution d'avant la colonne, ou enfilage manuel)
      -> aucune decision possible, WARNING nomme l'execution ;
    - enfilee sur une AUTRE file que celle de ce worker -> pas notre travail.

    Rend un compte par categorie, pour le journal et pour les tests.
    """
    from app.database import SessionLocal
    from app.models.execution import Execution, ExecutionStatus

    comptes = {"vivantes": 0, "echouees": 0, "sans_job": 0, "autre_file": 0}
    db = SessionLocal()
    try:
        actives = db.query(Execution).filter(
            Execution.status == ExecutionStatus.RUNNING
        ).all()
        for execution in actives:
            job_id = execution.arq_job_id
            if not job_id:
                comptes["sans_job"] += 1
                logger.warning(
                    f"[Startup] Execution {execution.id} est RUNNING sans "
                    f"arq_job_id : impossible de dire si son job vit. Laissee "
                    f"en l'etat — le statut seul n'est pas une preuve "
                    f"d'abandon (PROD-04)."
                )
                continue

            file_execution = execution.arq_queue_name or ARQ_QUEUE_NAME
            if file_execution != ARQ_QUEUE_NAME:
                comptes["autre_file"] += 1
                logger.info(
                    f"[Startup] Execution {execution.id} enfilee sur "
                    f"{file_execution!r}, ce worker sert {ARQ_QUEUE_NAME!r} — "
                    f"pas de decision."
                )
                continue

            absent, statut = await _job_absent_de_redis(redis, job_id, file_execution)
            if absent:
                comptes["echouees"] += 1
                _marquer_echouee(db, execution, job_id, statut)
            else:
                comptes["vivantes"] += 1
                logger.info(
                    f"[Startup] Execution {execution.id} laissee intacte : "
                    f"job {job_id} statut={statut}"
                )
    finally:
        db.close()
    return comptes


async def startup(ctx: dict):
    """Reconcilie les executions actives avec les jobs reellement presents.

    VAGUE 1 / FILE C — PROD-04 = CAL-11. Deux comportements ont ete retires :

    1. **La purge de file.** Le demarrage appelait `job.abort()` sur tous les
       jobs en attente (« BUG-008 : flush stale jobs »), sans critere de
       vetuste : un job enfile trois secondes plus tot par un client etait
       annule au premier redemarrage. Un job en file est du travail en
       attente, pas un fantome.
    2. **Le nettoyage global des RUNNING.** Voir
       `_reconcilier_executions_actives`.
    """
    redis: ArqRedis = ctx.get("redis") or ctx.get("pool")
    if not redis:
        logger.warning(
            "[Startup] Aucune connexion Redis dans le contexte : aucune "
            "reconciliation des executions actives (aucune decision sans preuve)."
        )
        logger.info("[Startup] ARQ worker ready")
        return

    try:
        comptes = await _reconcilier_executions_actives(ctx, redis)
        logger.info(
            f"[Startup] Reconciliation : {comptes['echouees']} execution(s) "
            f"abandonnee(s) marquee(s) FAILED, {comptes['vivantes']} laissee(s) "
            f"intacte(s), {comptes['sans_job']} sans arq_job_id, "
            f"{comptes['autre_file']} sur une autre file."
        )
    except Exception as e:
        logger.warning(f"[Startup] Reconciliation impossible (non fatale) : {e}")

    logger.info("[Startup] ARQ worker ready")


async def shutdown(ctx: dict):
    """Clean shutdown."""
    logger.info("[Shutdown] ARQ worker stopping")


class WorkerSettings:
    """ARQ worker settings."""
    redis_settings = REDIS_SETTINGS
    functions = [execute_sds_task, resume_architecture_task, execute_build_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10  # Max concurrent executions (P3 done : SFDX no longer blocks event loop)
    # CAL-01 — le delai suivait un chiffre en dur, identique pour un Sonnet
    # cloud et un 30B local a 12,4 tok/s : le job de l'execution 172 a ete
    # coupe a 10:24:31 en plein appel de Marcus. Il suit desormais le profil
    # de routage (`DH_DEPLOYMENT_PROFILE`), surchargeable par
    # `DH_JOB_TIMEOUT_SECONDS`.
    job_timeout = job_timeout_seconds()
    # CAL-07 — sans ce drapeau, `Job.abort()` n'a aucun effet : le seul moyen
    # d'arreter une execution etait de redemarrer le worker, ce qui tuait
    # toutes les autres (PROD-04). L'annulation cooperative
    # (`executions.cancel_requested_at`, lue entre deux phases) le complete :
    # l'abandon ARQ arrete le job, la lecture cooperative ferme proprement
    # l'execution et conserve le travail deja produit.
    allow_abort_jobs = True
    health_check_interval = 30
    queue_name = ARQ_QUEUE_NAME  # une seule source : arq_config (vague 0 / AS-02)
    # B5 (D3, 03/09/2026) : purge des conversations Sophie au-dela de 12 mois,
    # chaque nuit a 03:17 UTC. Voir app/workers/retention.py.
    cron_jobs = [
        cron(purge_chat_logs_task, hour=3, minute=17, run_at_startup=False),
        # GL-16 (diff de la file D) : meme heure creuse, quelques minutes plus
        # tard pour ne pas tenir deux transactions de suppression en parallele.
        cron(purge_conversations_projet_task, hour=3, minute=23, run_at_startup=False),
    ]
