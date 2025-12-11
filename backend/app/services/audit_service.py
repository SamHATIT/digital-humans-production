"""
Audit Service - Centralized logging for all system activities.
CORE-001: Foundation for debugging, security compliance, and incremental execution.

Usage:
    from app.services.audit_service import audit_service
    
    # Simple logging (sync)
    audit_service.log(
        actor_type=ActorType.AGENT,
        actor_id="diego",
        action=ActionCategory.TASK_COMPLETE,
        entity_type="task",
        entity_id="TASK-005",
        project_id=42,
        execution_id=111
    )
    
    # With database session
    audit_service.log(..., db=db)
"""
import uuid
import time
from datetime import datetime
from typing import Optional, Any, Dict
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy import select, desc, and_

from app.database import SessionLocal
from app.models.audit import AuditLog, ActorType, ActionCategory
import logging

logger = logging.getLogger(__name__)


class AuditService:
    """
    Centralized audit logging service.
    Thread-safe design for synchronous operations.
    """
    
    def __init__(self):
        self._request_context: Dict[str, Any] = {}
    
    def set_request_context(
        self,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[str] = None
    ):
        """Set context for the current request (called by middleware)"""
        self._request_context = {
            "request_id": request_id or str(uuid.uuid4()),
            "ip_address": ip_address,
            "user_agent": user_agent,
            "user_id": user_id
        }
    
    def clear_request_context(self):
        """Clear request context after request completes"""
        self._request_context = {}
    
    def log(
        self,
        actor_type: ActorType,
        actor_id: Optional[str],
        action: ActionCategory,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_name: Optional[str] = None,
        actor_name: Optional[str] = None,
        action_detail: Optional[str] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        project_id: Optional[int] = None,
        execution_id: Optional[int] = None,
        task_id: Optional[str] = None,
        extra_data: Optional[Dict] = None,
        success: str = "true",
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Optional[int]:
        """
        Log an audit entry.
        
        Returns:
            ID of the created audit log entry, or None if failed
        """
        try:
            # Use provided session or create new one
            if db:
                return self._insert_log(
                    db=db,
                    actor_type=actor_type,
                    actor_id=actor_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    entity_name=entity_name,
                    actor_name=actor_name,
                    action_detail=action_detail,
                    old_value=old_value,
                    new_value=new_value,
                    project_id=project_id,
                    execution_id=execution_id,
                    task_id=task_id,
                    extra_data=extra_data,
                    success=success,
                    error_message=error_message,
                    duration_ms=duration_ms
                )
            else:
                db = SessionLocal()
                try:
                    result = self._insert_log(
                        db=db,
                        actor_type=actor_type,
                        actor_id=actor_id,
                        action=action,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        entity_name=entity_name,
                        actor_name=actor_name,
                        action_detail=action_detail,
                        old_value=old_value,
                        new_value=new_value,
                        project_id=project_id,
                        execution_id=execution_id,
                        task_id=task_id,
                        extra_data=extra_data,
                        success=success,
                        error_message=error_message,
                        duration_ms=duration_ms
                    )
                    db.commit()
                    return result
                finally:
                    db.close()
                    
        except Exception as e:
            # Never let audit logging break the main flow
            logger.error(f"Failed to write audit log: {e}")
            return None
    
    def _insert_log(
        self,
        db: Session,
        actor_type: ActorType,
        actor_id: Optional[str],
        action: ActionCategory,
        **kwargs
    ) -> int:
        """Insert a single audit log entry"""
        audit_log = AuditLog(
            actor_type=actor_type.value if isinstance(actor_type, ActorType) else actor_type,
            actor_id=actor_id,
            action=action.value if isinstance(action, ActionCategory) else action,
            request_id=self._request_context.get("request_id"),
            ip_address=self._request_context.get("ip_address"),
            user_agent=self._request_context.get("user_agent"),
            **kwargs
        )
        db.add(audit_log)
        db.flush()
        return audit_log.id
    
    @contextmanager
    def timed_operation(
        self,
        actor_type: ActorType,
        actor_id: Optional[str],
        action: ActionCategory,
        **kwargs
    ):
        """
        Context manager for timed operations.
        
        Usage:
            with audit_service.timed_operation(...) as audit:
                # do work
                audit.set_result(success=True, new_value={...})
        """
        start_time = time.time()
        result_holder = {"success": "true", "error_message": None, "new_value": None}
        
        class AuditContext:
            def set_result(self, success: bool = True, error_message: str = None, new_value: Dict = None):
                result_holder["success"] = "true" if success else "false"
                result_holder["error_message"] = error_message
                result_holder["new_value"] = new_value
        
        try:
            yield AuditContext()
        except Exception as e:
            result_holder["success"] = "false"
            result_holder["error_message"] = str(e)
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            self.log(
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                duration_ms=duration_ms,
                success=result_holder["success"],
                error_message=result_holder["error_message"],
                new_value=result_holder["new_value"],
                **kwargs
            )
    
    # ========== Query methods ==========
    
    def get_logs(
        self,
        project_id: Optional[int] = None,
        execution_id: Optional[int] = None,
        task_id: Optional[str] = None,
        actor_type: Optional[ActorType] = None,
        action: Optional[ActionCategory] = None,
        entity_type: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        db: Optional[Session] = None
    ) -> list[AuditLog]:
        """Query audit logs with filters"""
        def _query(session: Session):
            query = session.query(AuditLog)
            
            if project_id:
                query = query.filter(AuditLog.project_id == project_id)
            if execution_id:
                query = query.filter(AuditLog.execution_id == execution_id)
            if task_id:
                query = query.filter(AuditLog.task_id == task_id)
            if actor_type:
                query = query.filter(AuditLog.actor_type == (actor_type.value if isinstance(actor_type, ActorType) else actor_type))
            if action:
                query = query.filter(AuditLog.action == (action.value if isinstance(action, ActionCategory) else action))
            if entity_type:
                query = query.filter(AuditLog.entity_type == entity_type)
            if since:
                query = query.filter(AuditLog.timestamp >= since)
            if until:
                query = query.filter(AuditLog.timestamp <= until)
            
            return query.order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset).all()
        
        if db:
            return _query(db)
        else:
            db = SessionLocal()
            try:
                return _query(db)
            finally:
                db.close()
    
    def get_execution_timeline(
        self,
        execution_id: int,
        db: Optional[Session] = None
    ) -> list[AuditLog]:
        """Get complete timeline for an execution"""
        return self.get_logs(execution_id=execution_id, limit=1000, db=db)
    
    def get_task_history(
        self,
        task_id: str,
        db: Optional[Session] = None
    ) -> list[AuditLog]:
        """Get history for a specific BUILD task"""
        return self.get_logs(task_id=task_id, limit=100, db=db)
    
    # ========== Convenience methods ==========
    
    def log_agent_start(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: int,
        project_id: int,
        task_id: Optional[str] = None,
        extra_data: Optional[Dict] = None,
        db: Optional[Session] = None
    ):
        """Log agent starting work"""
        return self.log(
            actor_type=ActorType.AGENT,
            actor_id=agent_id,
            actor_name=agent_name,
            action=ActionCategory.AGENT_START,
            entity_type="execution" if not task_id else "task",
            entity_id=str(execution_id) if not task_id else task_id,
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            extra_data=extra_data,
            db=db
        )
    
    def log_agent_complete(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: int,
        project_id: int,
        task_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        extra_data: Optional[Dict] = None,
        db: Optional[Session] = None
    ):
        """Log agent completing work"""
        return self.log(
            actor_type=ActorType.AGENT,
            actor_id=agent_id,
            actor_name=agent_name,
            action=ActionCategory.AGENT_COMPLETE,
            entity_type="execution" if not task_id else "task",
            entity_id=str(execution_id) if not task_id else task_id,
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            duration_ms=duration_ms,
            extra_data=extra_data,
            db=db
        )
    
    def log_agent_fail(
        self,
        agent_id: str,
        agent_name: str,
        execution_id: int,
        project_id: int,
        error_message: str,
        task_id: Optional[str] = None,
        extra_data: Optional[Dict] = None,
        db: Optional[Session] = None
    ):
        """Log agent failure"""
        return self.log(
            actor_type=ActorType.AGENT,
            actor_id=agent_id,
            actor_name=agent_name,
            action=ActionCategory.AGENT_FAIL,
            entity_type="execution" if not task_id else "task",
            entity_id=str(execution_id) if not task_id else task_id,
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            success="false",
            error_message=error_message,
            extra_data=extra_data,
            db=db
        )
    
    def log_llm_interaction(
        self,
        agent_id: str,
        execution_id: int,
        project_id: int,
        model: str,
        tokens_input: int,
        tokens_output: int,
        duration_ms: int,
        success: bool = True,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None,
        db: Optional[Session] = None
    ):
        """Log LLM API call"""
        return self.log(
            actor_type=ActorType.AGENT,
            actor_id=agent_id,
            action=ActionCategory.LLM_RESPONSE if success else ActionCategory.LLM_ERROR,
            entity_type="llm_call",
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            duration_ms=duration_ms,
            success="true" if success else "false",
            error_message=error_message,
            extra_data={
                "model": model,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output
            },
            db=db
        )
    
    def log_sfdx_operation(
        self,
        operation: str,
        execution_id: int,
        project_id: int,
        task_id: Optional[str] = None,
        component_type: Optional[str] = None,
        component_name: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        extra_data: Optional[Dict] = None,
        db: Optional[Session] = None
    ):
        """Log SFDX operation"""
        action_map = {
            "deploy": ActionCategory.SFDX_DEPLOY,
            "test": ActionCategory.SFDX_TEST,
            "retrieve": ActionCategory.SFDX_RETRIEVE,
        }
        return self.log(
            actor_type=ActorType.SYSTEM,
            actor_id="sfdx_service",
            actor_name="SFDX CLI",
            action=action_map.get(operation, ActionCategory.OTHER),
            entity_type=component_type,
            entity_id=component_name,
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            success="true" if success else "false",
            error_message=error_message,
            duration_ms=duration_ms,
            extra_data=extra_data,
            db=db
        )
    
    def log_git_operation(
        self,
        operation: str,
        execution_id: int,
        project_id: int,
        task_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
        branch: Optional[str] = None,
        pr_url: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        db: Optional[Session] = None
    ):
        """Log Git operation"""
        action_map = {
            "clone": ActionCategory.GIT_CLONE,
            "commit": ActionCategory.GIT_COMMIT,
            "push": ActionCategory.GIT_PUSH,
            "pr_create": ActionCategory.GIT_PR_CREATE,
            "pr_merge": ActionCategory.GIT_PR_MERGE,
        }
        return self.log(
            actor_type=ActorType.SYSTEM,
            actor_id="git_service",
            actor_name="Git Service",
            action=action_map.get(operation, ActionCategory.OTHER),
            entity_type="repository",
            execution_id=execution_id,
            project_id=project_id,
            task_id=task_id,
            success="true" if success else "false",
            error_message=error_message,
            duration_ms=duration_ms,
            extra_data={
                "commit_sha": commit_sha,
                "branch": branch,
                "pr_url": pr_url
            },
            db=db
        )


# Singleton instance
audit_service = AuditService()
