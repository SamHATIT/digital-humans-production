"""ARQ worker entry point.

Run with: python -m arq app.workers.worker.WorkerSettings
"""
from app.workers.arq_config import REDIS_SETTINGS
from app.workers.tasks import execute_sds_task, resume_architecture_task, execute_build_task


class WorkerSettings:
    """ARQ worker settings."""
    redis_settings = REDIS_SETTINGS
    functions = [execute_sds_task, resume_architecture_task, execute_build_task]
    max_jobs = 3  # Max concurrent executions
    job_timeout = 3600  # 1 hour max per execution
    health_check_interval = 30
    queue_name = "digital-humans"
