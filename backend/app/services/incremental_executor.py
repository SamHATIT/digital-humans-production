"""
Incremental Executor Service - ORCH-03a
Executes WBS tasks one by one with testing and validation between each.

Workflow per task:
1. Agent generates code/config
2. SFDX deploys to sandbox
3. Elena runs tests
4. If KO: retry (max 3x)
5. If OK: Git commit + PR
6. Full auto: merge / Semi auto: pause

Author: Digital Humans Team
Created: 2025-12-08
"""
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.models.execution import Execution
from app.models.task_execution import TaskExecution, TaskStatus
from app.models.project import Project

logger = logging.getLogger(__name__)


# Configuration
MAX_RETRIES = 3
AGENT_MAPPING = {
    # WBS assignee -> agent_id
    "Diego": "apex",
    "Zara": "lwc", 
    "Raj": "admin",
    "Aisha": "data",
    "Elena": "qa",
    "Jordan": "devops",
    "Lucas": "trainer",
    "Marcus": "architect",
}


class IncrementalExecutor:
    """
    Executes WBS tasks incrementally with validation between each.
    
    Modes:
    - FULL_AUTO: Deploy, test, commit, merge automatically
    - SEMI_AUTO: Deploy, test, commit, then pause for user validation
    """
    
    def __init__(self, db: Session, execution_id: int):
        self.db = db
        self.execution_id = execution_id
        self.execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not self.execution:
            raise ValueError(f"Execution {execution_id} not found")
        
        self.project = db.query(Project).filter(Project.id == self.execution.project_id).first()
        self.mode = "FULL_AUTO"  # TODO: Get from project config
        
    def load_tasks_from_wbs(self, wbs_content: Dict) -> List[TaskExecution]:
        """
        Parse WBS and create TaskExecution records for each task.
        
        Args:
            wbs_content: WBS JSON from Marcus (architect_wbs deliverable)
            
        Returns:
            List of created TaskExecution records
        """
        tasks_created = []
        phases = wbs_content.get("phases", [])
        
        logger.info(f"[IncrementalExecutor] Loading {sum(len(p.get('tasks', [])) for p in phases)} tasks from WBS")
        
        for phase in phases:
            phase_name = phase.get("name", "Unknown Phase")
            
            for task in phase.get("tasks", []):
                task_id = task.get("id") or task.get("task_id")
                task_name = task.get("name", "Unnamed Task")
                assignee = task.get("assigned_agent") or task.get("assignee") or task.get("assigned_to")
                dependencies = task.get("dependencies", [])
                
                # Map assignee name to agent_id
                agent_id = AGENT_MAPPING.get(assignee)
                
                # Check if task already exists
                existing = self.db.query(TaskExecution).filter(
                    TaskExecution.execution_id == self.execution_id,
                    TaskExecution.task_id == task_id
                ).first()
                
                if existing:
                    logger.debug(f"Task {task_id} already exists, skipping")
                    tasks_created.append(existing)
                    continue
                
                # Create new task execution
                task_exec = TaskExecution(
                    execution_id=self.execution_id,
                    task_id=task_id,
                    task_name=task_name,
                    phase_name=phase_name,
                    assigned_agent=agent_id,
                    status=TaskStatus.PENDING,
                    depends_on=dependencies if dependencies else None,
                )
                
                self.db.add(task_exec)
                tasks_created.append(task_exec)
                logger.debug(f"Created task: {task_id} - {task_name} (agent: {agent_id})")
        
        self.db.commit()
        logger.info(f"[IncrementalExecutor] Created {len(tasks_created)} task executions")
        return tasks_created
    
    def get_next_task(self) -> Optional[TaskExecution]:
        """
        Get the next task that can be executed.
        Returns None if no tasks are available (all done or blocked).
        """
        # Get all completed task IDs
        completed_tasks = [t.task_id for t in self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status == TaskStatus.COMPLETED
        ).all()]
        
        # Find first pending task with satisfied dependencies
        pending_tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status == TaskStatus.PENDING
        ).order_by(TaskExecution.id).all()
        
        for task in pending_tasks:
            if task.can_start(completed_tasks):
                return task
        
        # Check if there are blocked tasks
        blocked_count = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status.in_([TaskStatus.PENDING, TaskStatus.BLOCKED])
        ).count()
        
        if blocked_count > 0:
            logger.warning(f"[IncrementalExecutor] {blocked_count} tasks blocked by dependencies")
        
        return None
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get summary of all tasks and their statuses"""
        tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id
        ).all()
        
        summary = {
            "total": len(tasks),
            "by_status": {},
            "by_agent": {},
            "tasks": []
        }
        
        for task in tasks:
            # Count by status
            status = task.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by agent
            agent = task.assigned_agent or "unassigned"
            summary["by_agent"][agent] = summary["by_agent"].get(agent, 0) + 1
            
            # Task details
            summary["tasks"].append({
                "task_id": task.task_id,
                "name": task.task_name,
                "status": status,
                "agent": task.assigned_agent,
                "attempts": task.attempt_count,
                "last_error": task.last_error,
            })
        
        return summary
    
    def update_task_status(
        self, 
        task: TaskExecution, 
        status: TaskStatus, 
        error: Optional[str] = None,
        **kwargs
    ):
        """Update task status and optional fields"""
        task.status = status
        
        if status == TaskStatus.RUNNING:
            task.started_at = datetime.now(timezone.utc)
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
            task.completed_at = datetime.now(timezone.utc)
        
        if error:
            task.record_error(error)
        
        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        self.db.commit()
        logger.info(f"[IncrementalExecutor] Task {task.task_id} -> {status.value}")
    
    def mark_task_failed(self, task: TaskExecution, error: str):
        """Mark task as failed after exhausting retries"""
        self.update_task_status(task, TaskStatus.FAILED, error=error)
        
        # Mark dependent tasks as blocked
        dependent_tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status == TaskStatus.PENDING
        ).all()
        
        for dep_task in dependent_tasks:
            if dep_task.depends_on and task.task_id in dep_task.depends_on:
                self.update_task_status(dep_task, TaskStatus.BLOCKED)
                logger.warning(f"[IncrementalExecutor] Task {dep_task.task_id} blocked by {task.task_id}")
    
    def can_retry(self, task: TaskExecution) -> bool:
        """Check if task can be retried"""
        return task.has_retries_left(MAX_RETRIES)
    
    def reset_task(self, task_id: str) -> bool:
        """Reset a failed/blocked task to pending for retry"""
        task = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.task_id == task_id
        ).first()
        
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        task.status = TaskStatus.PENDING
        task.attempt_count = 0
        task.last_error = None
        task.error_log = None
        task.started_at = None
        task.completed_at = None
        self.db.commit()
        
        logger.info(f"[IncrementalExecutor] Task {task_id} reset to pending")
        return True
    
    def skip_task(self, task_id: str, reason: str = "Manual skip") -> bool:
        """Skip a task"""
        task = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.task_id == task_id
        ).first()
        
        if not task:
            logger.error(f"Task {task_id} not found")
            return False
        
        self.update_task_status(task, TaskStatus.SKIPPED, error=reason)
        return True
    
    async def execute_single_task(self, task: TaskExecution) -> Dict[str, Any]:
        """
        Execute a single WBS task through the full cycle.
        
        This is a placeholder - the actual implementation will be in ORCH-03d
        when we integrate SFDX and Git services.
        
        Returns:
            Dict with success status and details
        """
        logger.info(f"[IncrementalExecutor] Starting task {task.task_id}: {task.task_name}")
        self.update_task_status(task, TaskStatus.RUNNING)
        
        # TODO: Implement in ORCH-03d
        # 1. Call agent to generate code (Diego/Zara/Raj)
        # 2. SFDX deploy to sandbox (ORCH-03b)
        # 3. Elena tests (ORCH-03b)
        # 4. Git commit + PR (ORCH-03c)
        # 5. Merge or pause based on mode
        
        return {
            "success": False,
            "error": "Not implemented - see ORCH-03d",
            "task_id": task.task_id
        }
    
    def is_build_complete(self) -> bool:
        """Check if all tasks are completed or skipped"""
        incomplete = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status.not_in([TaskStatus.COMPLETED, TaskStatus.SKIPPED])
        ).count()
        return incomplete == 0
    
    def get_progress_percentage(self) -> int:
        """Calculate build progress as percentage"""
        total = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id
        ).count()
        
        if total == 0:
            return 0
        
        done = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status.in_([TaskStatus.COMPLETED, TaskStatus.SKIPPED])
        ).count()
        
        return int((done / total) * 100)
