"""
BUILD V2 executor function.

P4: Extracted from pm_orchestrator.py — Background BUILD execution.
"""
import logging

from app.database import SessionLocal

logger = logging.getLogger(__name__)


async def execute_build_v2(project_id: int, execution_id: int):
    """Execute BUILD v2 with PhasedBuildExecutor."""
    from app.services.phased_build_executor import PhasedBuildExecutor
    from app.models.task_execution import TaskExecution

    db = SessionLocal()
    try:
        logger.info(f"[BUILD v2] Starting PhasedBuildExecutor for project {project_id}, execution {execution_id}")

        tasks = db.query(TaskExecution).filter(
            TaskExecution.execution_id == execution_id
        ).all()

        wbs_tasks = []
        for task in tasks:
            wbs_tasks.append({
                "task_id": task.task_id,
                "task_name": task.task_name,
                "name": task.task_name,
                "target_object": task.task_name,
                "task_type": task.task_type,
                "assigned_agent": task.assigned_agent,
                "description": task.description or task.task_name,
                "phase_name": task.phase_name,
            })

        logger.info(f"[BUILD v2] Found {len(wbs_tasks)} tasks")

        executor = PhasedBuildExecutor(project_id, execution_id, db)
        result = await executor.execute_build(wbs_tasks)

        logger.info(f"[BUILD v2] Execution completed: {result}")
        return result

    except Exception as e:
        logger.error(f"[BUILD v2] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()
