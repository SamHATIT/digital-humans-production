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
import os
import json
from datetime import datetime, timezone
from pathlib import Path
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
        ORCH-03d: Full integration of agent → deploy → test → commit
        
        Cycle:
        1. Agent generates code (Diego/Zara/Raj based on task)
        2. SFDX deploys to sandbox
        3. Elena tests
        4. If KO: retry up to MAX_RETRIES
        5. If OK: Git commit + PR
        6. Full auto: merge / Semi auto: pause
        
        Returns:
            Dict with success status and details
        """
        from app.services.sfdx_service import get_sfdx_service
        from app.services.git_service import GitService
        
        logger.info(f"[IncrementalExecutor] ══════════════════════════════════════")
        logger.info(f"[IncrementalExecutor] Starting task {task.task_id}: {task.task_name}")
        logger.info(f"[IncrementalExecutor] Agent: {task.assigned_agent}, Attempt: {task.attempt_count + 1}/{MAX_RETRIES}")
        
        self.update_task_status(task, TaskStatus.RUNNING)
        
        try:
            # ════════════════════════════════════════════════════════════════
            # STEP 1: Generate code with assigned agent
            # ════════════════════════════════════════════════════════════════
            logger.info(f"[Step 1] Generating code with {task.assigned_agent}...")
            
            generation_result = await self._generate_code_for_task(task)
            
            if not generation_result.get("success"):
                error = generation_result.get("error", "Code generation failed")
                logger.error(f"[Step 1] ❌ Generation failed: {error}")
                return await self._handle_task_failure(task, error, "generation")
            
            generated_files = generation_result.get("files", {})
            logger.info(f"[Step 1] ✅ Generated {len(generated_files)} file(s)")
            
            # Store generated files in task
            task.generated_files = list(generated_files.keys())
            self.db.commit()
            
            # ════════════════════════════════════════════════════════════════
            # STEP 2: Deploy to sandbox via SFDX
            # ════════════════════════════════════════════════════════════════
            logger.info(f"[Step 2] Deploying to sandbox...")
            self.update_task_status(task, TaskStatus.DEPLOYING)
            
            sfdx = get_sfdx_service()
            
            # Deploy each generated file
            deploy_results = []
            for file_path, content in generated_files.items():
                # Determine metadata type from file extension
                metadata_type = self._get_metadata_type(file_path)
                metadata_name = Path(file_path).stem
                
                deploy_result = await sfdx.deploy_metadata(
                    metadata_type=metadata_type,
                    metadata_name=metadata_name,
                    content=content
                )
                deploy_results.append(deploy_result)
                
                if not deploy_result.get("success"):
                    error = deploy_result.get("error", "Deployment failed")
                    logger.error(f"[Step 2] ❌ Deploy failed for {file_path}: {error}")
                    task.deploy_result = deploy_result
                    return await self._handle_task_failure(task, error, "deployment")
            
            task.deploy_result = {"files_deployed": len(deploy_results), "results": deploy_results}
            self.db.commit()
            logger.info(f"[Step 2] ✅ Deployed {len(deploy_results)} file(s)")
            
            # ════════════════════════════════════════════════════════════════
            # STEP 3: Run tests with Elena
            # ════════════════════════════════════════════════════════════════
            logger.info(f"[Step 3] Running tests (Elena)...")
            self.update_task_status(task, TaskStatus.TESTING)
            
            # Find related test classes
            test_classes = self._find_test_classes_for_task(task, generated_files)
            
            if test_classes:
                test_result = await sfdx.run_tests(test_classes=test_classes)
            else:
                # Run all local tests if no specific tests found
                test_result = await sfdx.run_tests()
            
            task.test_result = test_result
            self.db.commit()
            
            if not test_result.get("success") or test_result.get("failing", 0) > 0:
                error = f"Tests failed: {test_result.get('failing', 0)} failures"
                logger.warning(f"[Step 3] ⚠️ {error}")
                return await self._handle_task_failure(task, error, "testing")
            
            logger.info(f"[Step 3] ✅ Tests passed: {test_result.get('passing', 0)}/{test_result.get('tests_run', 0)}")
            self.update_task_status(task, TaskStatus.PASSED)
            
            # ════════════════════════════════════════════════════════════════
            # STEP 4: Commit to Git
            # ════════════════════════════════════════════════════════════════
            logger.info(f"[Step 4] Committing to Git...")
            self.update_task_status(task, TaskStatus.COMMITTING)
            
            git_result = await self._commit_task_to_git(task, generated_files)
            
            if git_result.get("success"):
                task.git_commit_sha = git_result.get("commit_sha")
                task.git_pr_url = git_result.get("pr_url")
                self.db.commit()
                logger.info(f"[Step 4] ✅ Committed: {task.git_commit_sha[:8] if task.git_commit_sha else 'N/A'}")
            else:
                logger.warning(f"[Step 4] ⚠️ Git commit failed (non-blocking): {git_result.get('error')}")
            
            # ════════════════════════════════════════════════════════════════
            # STEP 5: Merge or pause based on mode
            # ════════════════════════════════════════════════════════════════
            if self.mode == "FULL_AUTO" and git_result.get("pr_number"):
                logger.info(f"[Step 5] Auto-merging PR #{git_result.get('pr_number')}...")
                # TODO: Implement auto-merge
                pass
            elif self.mode == "SEMI_AUTO":
                logger.info(f"[Step 5] Semi-auto mode: PR created, waiting for manual merge")
                # TODO: Send notification
                pass
            
            # ════════════════════════════════════════════════════════════════
            # COMPLETE
            # ════════════════════════════════════════════════════════════════
            self.update_task_status(task, TaskStatus.COMPLETED)
            logger.info(f"[IncrementalExecutor] ✅ Task {task.task_id} COMPLETED")
            
            return {
                "success": True,
                "task_id": task.task_id,
                "files_generated": len(generated_files),
                "tests_passed": test_result.get("passing", 0),
                "commit_sha": task.git_commit_sha,
                "pr_url": task.git_pr_url
            }
            
        except Exception as e:
            logger.error(f"[IncrementalExecutor] ❌ Task {task.task_id} exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return await self._handle_task_failure(task, str(e), "exception")
    
    async def _generate_code_for_task(self, task: TaskExecution) -> Dict[str, Any]:
        """
        Call the appropriate agent to generate code for this task.
        
        Returns:
            Dict with 'files': {path: content} mapping
        """
        # TODO: Integrate with actual agent execution
        # For now, return placeholder
        logger.info(f"[CodeGen] Would call agent {task.assigned_agent} for task {task.task_id}")
        
        # Placeholder - actual implementation will call agent service
        return {
            "success": True,
            "files": {},  # Empty for now - agents will populate
            "message": "Placeholder - agent integration pending"
        }
    
    async def _handle_task_failure(
        self, 
        task: TaskExecution, 
        error: str, 
        stage: str
    ) -> Dict[str, Any]:
        """
        Handle task failure - retry if possible, otherwise mark as failed.
        """
        task.record_error(f"[{stage}] {error}")
        
        if self.can_retry(task):
            logger.info(f"[Retry] Task {task.task_id} will retry (attempt {task.attempt_count}/{MAX_RETRIES})")
            self.update_task_status(task, TaskStatus.PENDING)  # Reset to pending for retry
            return {
                "success": False,
                "retry": True,
                "task_id": task.task_id,
                "error": error,
                "attempt": task.attempt_count
            }
        else:
            logger.error(f"[Failed] Task {task.task_id} exhausted retries")
            self.mark_task_failed(task, error)
            return {
                "success": False,
                "retry": False,
                "task_id": task.task_id,
                "error": error,
                "attempts_exhausted": True
            }
    
    def _get_metadata_type(self, file_path: str) -> str:
        """Determine Salesforce metadata type from file path/extension"""
        path = Path(file_path)
        ext = path.suffix.lower()
        name = path.stem.lower()
        
        if ext == ".cls" or "class" in name:
            return "ApexClass"
        elif ext == ".trigger":
            return "ApexTrigger"
        elif ext in [".js", ".html", ".css"] or "lwc" in file_path.lower():
            return "LightningComponentBundle"
        elif ext == ".flow-meta.xml" or "flow" in name:
            return "Flow"
        elif ext == ".object-meta.xml" or "object" in file_path.lower():
            return "CustomObject"
        elif ext == ".permissionset-meta.xml":
            return "PermissionSet"
        else:
            return "ApexClass"  # Default
    
    def _find_test_classes_for_task(
        self, 
        task: TaskExecution, 
        generated_files: Dict[str, str]
    ) -> List[str]:
        """
        Find test classes related to the generated files.
        Convention: MyClass.cls -> MyClassTest.cls
        """
        test_classes = []
        
        for file_path in generated_files.keys():
            path = Path(file_path)
            if path.suffix == ".cls" and not path.stem.endswith("Test"):
                test_name = f"{path.stem}Test"
                test_classes.append(test_name)
        
        return test_classes
    
    async def _commit_task_to_git(
        self, 
        task: TaskExecution, 
        files: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Commit generated files to Git and create PR.
        """
        # Get Git config from project
        git_config = self._get_git_config()
        
        if not git_config.get("repo_url") or not git_config.get("token"):
            return {
                "success": False,
                "error": "Git not configured for this project"
            }
        
        from app.services.git_service import commit_and_pr
        
        branch_name = f"task/{task.task_id.lower()}"
        commit_message = f"Implement {task.task_name}"
        pr_title = f"[{task.task_id}] {task.task_name}"
        pr_body = f"""## Task Details
- **Task ID**: {task.task_id}
- **Agent**: {task.assigned_agent}
- **Phase**: {task.phase_name}

## Changes
{chr(10).join(f'- {f}' for f in files.keys())}

---
*Generated by Digital Humans*
"""
        
        return await commit_and_pr(
            repo_url=git_config["repo_url"],
            token=git_config["token"],
            files=files,
            branch_name=branch_name,
            commit_message=commit_message,
            pr_title=pr_title,
            pr_body=pr_body,
            task_id=task.task_id,
            base_branch=git_config.get("branch", "main")
        )
    
    def _get_git_config(self) -> Dict[str, Any]:
        """Get Git configuration from project settings"""
        # TODO: Get from project.git_config or similar
        return {
            "repo_url": os.environ.get("PROJECT_GIT_REPO"),
            "token": os.environ.get("PROJECT_GIT_TOKEN"),
            "branch": os.environ.get("PROJECT_GIT_BRANCH", "main")
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
