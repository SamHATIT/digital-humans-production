import sys
sys.path.insert(0, '/app')
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_build():
    from app.database import SessionLocal
    from app.services.incremental_executor import IncrementalExecutor
    from app.models.execution import Execution
    from app.models.task_execution import TaskExecution, TaskStatus
    
    logger.info("[BUILD] Starting BUILD phase for execution 119")
    
    db = SessionLocal()
    
    # Get pending tasks
    tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == 119,
        TaskExecution.status == TaskStatus.PENDING
    ).order_by(TaskExecution.task_id).all()
    
    logger.info(f"[BUILD] Found {len(tasks)} pending tasks")
    
    executor = IncrementalExecutor(db, execution_id=119, project_id=76)
    
    for task in tasks:
        logger.info(f"[BUILD] Executing task {task.task_id}: {task.task_name}")
        try:
            result = await executor.execute_task(task)
            logger.info(f"[BUILD] Task {task.task_id} result: {result.get('success', False)}")
        except Exception as e:
            logger.error(f"[BUILD] Task {task.task_id} failed: {e}")
    
    db.close()
    logger.info("[BUILD] BUILD phase completed")

if __name__ == "__main__":
    asyncio.run(run_build())
