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
    # WBS assignee -> agent_id (must match AGENT_CONFIG keys in agent_executor.py)
    "Diego": "diego",
    "Zara": "zara", 
    "Raj": "raj",
    "Aisha": "aisha",
    "Elena": "elena",
    "Jordan": "jordan",
    "Lucas": "lucas",
    "Marcus": "marcus",
    # Lowercase variants
    "diego": "diego",
    "zara": "zara",
    "raj": "raj",
    "aisha": "aisha",
    "elena": "elena",
    "jordan": "jordan",
    "lucas": "lucas",
    "marcus": "marcus",
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
    
    def is_paused(self) -> bool:
        """Check if build is paused via execution metadata."""
        self.db.refresh(self.execution)
        if self.execution and self.execution.metadata:
            return self.execution.metadata.get("build_paused", False)
        return False
    
    def get_next_task(self) -> Optional[TaskExecution]:
        """
        Get the next task that can be executed.
        Returns None if no tasks are available (all done, blocked, or paused).
        """
        # Check if paused
        if self.is_paused():
            logger.info("[IncrementalExecutor] BUILD is paused")
            return None
        
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
        from app.services.agent_executor import run_agent_task
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
            # STEP 3: Validate code with Elena (QA)
            # ════════════════════════════════════════════════════════════════
            logger.info(f"[Step 3] Validating code with Elena...")
            self.update_task_status(task, TaskStatus.TESTING)
            
            # Call Elena in test mode
            elena_input = {
                "task": {
                    "task_id": task.task_id,
                    "name": task.task_name
                },
                "code_files": generated_files
            }
            
            elena_result = await run_agent_task(
                agent_id="elena",
                mode="test",
                input_data=elena_input,
                execution_id=self.execution_id,
                timeout=180
            )
            
            task.test_result = elena_result.get("content", {})
            self.db.commit()
            
            if not elena_result.get("success") or elena_result.get("verdict") == "FAIL":
                feedback = elena_result.get("feedback", "Code validation failed")
                logger.warning(f"[Step 3] ❌ Elena FAIL: {feedback[:100]}")
                return await self._handle_task_failure(task, feedback, "testing")
            
            logger.info(f"[Step 3] ✅ Elena PASS - code validated")
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
        Call the appropriate agent (via run_agent_task) to generate code for this task.
        Uses agent scripts in BUILD mode.
        
        Returns:
            Dict with 'success' and 'files': {path: content} mapping
        """
        from app.services.agent_executor import run_agent_task
        
        logger.info(f"[CodeGen] Calling {task.assigned_agent} in BUILD mode for task {task.task_id}")
        
        # Get architecture context from previous agents
        architecture_context = self._get_architecture_context()
        
        # Build input data for the agent
        input_data = {
            "task": {
                "task_id": task.task_id,
                "name": task.task_name,
                "title": task.task_name,
                "description": task.task_name,
                "phase": task.phase_name,
                "validation_criteria": []
            },
            "architecture_context": architecture_context,
            "execution_id": self.execution_id
        }
        
        # If retry, include Elena's feedback for correction
        if task.attempt_count > 0 and task.last_error:
            logger.info(f"[CodeGen] Retry #{task.attempt_count} - including Elena feedback")
            input_data["previous_feedback"] = task.last_error
            input_data["task"]["correction_needed"] = True
        
        # Map to agent scripts (diego, zara, raj, aisha have build mode)
        build_agents = ["diego", "zara", "raj", "aisha"]
        
        if task.assigned_agent not in build_agents:
            logger.info(f"[CodeGen] {task.assigned_agent} is not a build agent, skipping")
            return {"success": True, "files": {}, "message": f"No code generation for {task.assigned_agent}"}
        
        try:
            result = await run_agent_task(
                agent_id=task.assigned_agent,
                mode="build",
                input_data=input_data,
                execution_id=self.execution_id,
                project_id=0,
                timeout=300
            )
            
            if not result.get("success"):
                return {
                    "success": False,
                    "error": result.get("error", "Agent failed"),
                    "files": {}
                }
            
            files = result.get("content", {}).get("files", {})
            logger.info(f"[CodeGen] {task.assigned_agent} generated {len(files)} file(s)")
            
            return {"success": True, "files": files, "agent_result": result}
            
        except Exception as e:
            logger.error(f"[CodeGen] Error calling {task.assigned_agent}: {str(e)}")
            return {"success": False, "error": str(e), "files": {}}
    
    def _get_architecture_context(self) -> str:
        """Get architecture context from Marcus/Olivia artifacts."""
        try:
            from app.models.execution_artifact import ExecutionArtifact
            
            artifacts = self.db.query(ExecutionArtifact).filter(
                ExecutionArtifact.execution_id == self.execution_id,
                ExecutionArtifact.producer_agent.in_(["marcus", "olivia"])
            ).all()
            
            context_parts = []
            for artifact in artifacts:
                content = artifact.content
                if isinstance(content, dict):
                    content = json.dumps(content, indent=2)
                context_parts.append(f"### {artifact.producer_agent.upper()}:\n{content[:5000]}")
            
            return "\n\n".join(context_parts) if context_parts else ""
        except Exception as e:
            logger.warning(f"[CodeGen] Could not get context: {e}")
            return ""

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


    # ════════════════════════════════════════════════════════════════════════════
    # ORCH-03e: Jordan - Package Final et Déploiement UAT
    # ════════════════════════════════════════════════════════════════════════════
    
    async def finalize_build(self, uat_org: str = None) -> Dict[str, Any]:
        """
        Finalize build phase: Jordan prepares package and optionally deploys to UAT.
        
        Called when all tasks are completed.
        
        Args:
            uat_org: Target UAT org alias (for FULL_AUTO mode)
            
        Returns:
            Dict with package info and deployment result
        """
        from app.services.sfdx_service import get_sfdx_service
        from app.services.agent_executor import run_agent_task, SFDXService
        import zipfile
        import tempfile
        
        logger.info(f"[Jordan] ══════════════════════════════════════")
        logger.info(f"[Jordan] Finalizing build - Preparing deployment package")
        
        # Check if build is complete
        if not self.is_build_complete():
            incomplete = self.get_task_summary()
            return {
                "success": False,
                "error": "Build not complete",
                "pending_tasks": incomplete["by_status"].get("pending", 0),
                "failed_tasks": incomplete["by_status"].get("failed", 0)
            }
        
        # Get all completed tasks with their generated files
        completed_tasks = self.db.query(TaskExecution).filter(
            TaskExecution.execution_id == self.execution_id,
            TaskExecution.status == TaskStatus.COMPLETED
        ).all()
        
        logger.info(f"[Jordan] {len(completed_tasks)} tasks completed")
        
        # Collect all deployed components
        all_components = []
        for task in completed_tasks:
            if task.generated_files:
                for file_path in task.generated_files:
                    component_type = self._get_metadata_type(file_path)
                    component_name = Path(file_path).stem
                    all_components.append({
                        "type": component_type,
                        "name": component_name,
                        "file": file_path,
                        "task_id": task.task_id
                    })
        
        logger.info(f"[Jordan] {len(all_components)} components to package")
        
        # Generate package.xml
        package_xml = self._generate_package_xml(all_components)
        
        # Generate deployment report
        report = self._generate_deployment_report(completed_tasks, all_components)
        
        result = {
            "success": True,
            "total_tasks": len(completed_tasks),
            "total_components": len(all_components),
            "package_xml": package_xml,
            "report": report,
        }
        
        if self.mode == "FULL_AUTO" and uat_org:
            # Deploy to UAT
            logger.info(f"[Jordan] FULL_AUTO: Deploying to UAT org '{uat_org}'...")
            
            sfdx_uat = SFDXService(target_org=uat_org)
            
            # Check UAT connection
            conn = await sfdx_uat.check_connection()
            if not conn.get("connected"):
                result["uat_deploy"] = {
                    "success": False,
                    "error": f"Cannot connect to UAT org: {conn.get('error')}"
                }
            else:
                # Retrieve from dev and deploy to UAT
                # This is a simplified approach - real implementation would:
                # 1. Create a temp project with retrieved source
                # 2. Deploy that source to UAT
                
                sfdx_dev = get_sfdx_service()
                
                # Get metadata types to retrieve
                metadata_types = list(set(c["type"] for c in all_components))
                
                with tempfile.TemporaryDirectory(prefix="jordan_deploy_") as temp_dir:
                    # Retrieve from dev
                    retrieve_result = await sfdx_dev.retrieve_source(
                        metadata_types=metadata_types,
                        output_dir=temp_dir
                    )
                    
                    if retrieve_result.get("success"):
                        # Deploy to UAT
                        deploy_result = await sfdx_uat.deploy_source(
                            source_path=temp_dir,
                            test_level="RunLocalTests"
                        )
                        
                        result["uat_deploy"] = {
                            "success": deploy_result.get("success"),
                            "target_org": uat_org,
                            "components_deployed": deploy_result.get("components_deployed", 0),
                            "details": deploy_result
                        }
                    else:
                        result["uat_deploy"] = {
                            "success": False,
                            "error": "Failed to retrieve source from dev"
                        }
                
                if result["uat_deploy"].get("success"):
                    logger.info(f"[Jordan] ✅ Deployed to UAT: {result['uat_deploy']['components_deployed']} components")
                else:
                    logger.warning(f"[Jordan] ⚠️ UAT deploy failed: {result['uat_deploy'].get('error')}")
        
        elif self.mode == "SEMI_AUTO":
            # Create downloadable package
            logger.info(f"[Jordan] SEMI_AUTO: Creating downloadable package...")
            
            package_path = await self._create_deployment_package(all_components, package_xml)
            
            result["package_path"] = package_path
            result["package_ready"] = True
            logger.info(f"[Jordan] ✅ Package ready: {package_path}")
        
        logger.info(f"[Jordan] ══════════════════════════════════════")
        return result
    
    def _generate_package_xml(self, components: List[Dict]) -> str:
        """Generate package.xml content"""
        # Group by type
        by_type = {}
        for comp in components:
            comp_type = comp["type"]
            if comp_type not in by_type:
                by_type[comp_type] = []
            by_type[comp_type].append(comp["name"])
        
        # Build XML
        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Package xmlns="http://soap.sforce.com/2006/04/metadata">',
        ]
        
        for comp_type, members in sorted(by_type.items()):
            lines.append('    <types>')
            for member in sorted(set(members)):
                lines.append(f'        <members>{member}</members>')
            lines.append(f'        <name>{comp_type}</name>')
            lines.append('    </types>')
        
        lines.append('    <version>59.0</version>')
        lines.append('</Package>')
        
        return '\n'.join(lines)
    
    def _generate_deployment_report(
        self, 
        tasks: List[TaskExecution], 
        components: List[Dict]
    ) -> Dict[str, Any]:
        """Generate deployment report"""
        # Group tasks by agent
        by_agent = {}
        for task in tasks:
            agent = task.assigned_agent or "unknown"
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append({
                "task_id": task.task_id,
                "name": task.task_name,
                "files": task.generated_files or [],
                "commit": task.git_commit_sha,
            })
        
        # Group components by type
        by_type = {}
        for comp in components:
            comp_type = comp["type"]
            if comp_type not in by_type:
                by_type[comp_type] = 0
            by_type[comp_type] += 1
        
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "execution_id": self.execution_id,
            "project_id": self.execution.project_id,
            "summary": {
                "total_tasks": len(tasks),
                "total_components": len(components),
                "by_agent": {k: len(v) for k, v in by_agent.items()},
                "by_component_type": by_type,
            },
            "tasks_by_agent": by_agent,
        }
    
    async def _create_deployment_package(
        self, 
        components: List[Dict], 
        package_xml: str
    ) -> str:
        """Create a ZIP package for manual deployment"""
        import zipfile
        
        # Create package directory
        package_dir = Path(f"/tmp/deployment_package_{self.execution_id}")
        package_dir.mkdir(exist_ok=True)
        
        # Write package.xml
        (package_dir / "package.xml").write_text(package_xml)
        
        # Create ZIP
        zip_path = f"/tmp/deployment_{self.execution_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add package.xml
            zf.write(package_dir / "package.xml", "package.xml")
            
            # Add deployment report
            report = self._generate_deployment_report(
                self.db.query(TaskExecution).filter(
                    TaskExecution.execution_id == self.execution_id,
                    TaskExecution.status == TaskStatus.COMPLETED
                ).all(),
                components
            )
            zf.writestr("deployment_report.json", json.dumps(report, indent=2))
            
            # Note: In a real implementation, we would also include
            # the actual source files retrieved from the org
        
        # Cleanup
        import shutil
        shutil.rmtree(package_dir, ignore_errors=True)
        
        return zip_path
