"""ARQ worker entry point.

Run with: python -m arq app.workers.worker.WorkerSettings
"""
import logging
from arq.connections import ArqRedis
from app.workers.arq_config import REDIS_SETTINGS
from app.workers.tasks import execute_sds_task, resume_architecture_task, execute_build_task

logger = logging.getLogger("arq.worker")


async def startup(ctx: dict):
    """BUG-008: Flush stale jobs on worker startup to prevent ghost execution."""
    redis: ArqRedis = ctx.get("redis") or ctx.get("pool")
    if redis:
        try:
            # BUG-008: Flush stale queued jobs from previous worker instance
            queued = await redis.queued_jobs()
            if queued:
                logger.warning(f"[Startup] Found {len(queued)} stale queued jobs — aborting them")
                for job in queued:
                    await job.abort()
                logger.info(f"[Startup] Aborted {len(queued)} stale jobs")
        except Exception as e:
            logger.warning(f"[Startup] Redis queue flush failed (non-fatal): {e}")
        try:
            # Find executions stuck in RUNNING state (from previous worker crash)
            from app.database import SessionLocal
            from app.models.execution import Execution, ExecutionStatus
            db = SessionLocal()
            try:
                # Find executions stuck in RUNNING state (from previous worker crash)
                stuck = db.query(Execution).filter(
                    Execution.status == ExecutionStatus.RUNNING
                ).all()
                for exec in stuck:
                    logger.warning(f"[Startup] Found stuck execution {exec.id} — marking as FAILED for safe resume")
                    exec.status = ExecutionStatus.FAILED
                    exec.logs = (exec.logs or "") + "\n[Worker restart] Marked as failed — use resume to continue"
                db.commit()
                if stuck:
                    logger.info(f"[Startup] Cleaned {len(stuck)} stuck executions")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"[Startup] Cleanup failed (non-fatal): {e}")
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
    max_jobs = 3  # Max concurrent executions
    job_timeout = 3600  # 1 hour max per execution
    health_check_interval = 30
    queue_name = "digital-humans"
