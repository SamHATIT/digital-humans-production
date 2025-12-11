"""
Audit API - Endpoints for querying audit logs.
CORE-001: Enables debugging and compliance review.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.services.audit_service import audit_service
from app.models.audit import AuditLog, ActorType, ActionCategory

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogResponse(BaseModel):
    """Response model for audit log entries"""
    id: int
    timestamp: datetime
    actor_type: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    action: str
    action_detail: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None
    project_id: Optional[int] = None
    execution_id: Optional[int] = None
    task_id: Optional[str] = None
    success: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    extra_data: Optional[dict] = None
    
    class Config:
        from_attributes = True


class AuditLogListResponse(BaseModel):
    """Response model for list of audit logs"""
    logs: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


@router.get("/logs", response_model=AuditLogListResponse)
def get_audit_logs(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    execution_id: Optional[int] = Query(None, description="Filter by execution ID"),
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    since: Optional[datetime] = Query(None, description="Filter logs since datetime"),
    until: Optional[datetime] = Query(None, description="Filter logs until datetime"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Query audit logs with various filters."""
    actor_type_enum = None
    if actor_type:
        try:
            actor_type_enum = ActorType(actor_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid actor_type: {actor_type}")
    
    action_enum = None
    if action:
        try:
            action_enum = ActionCategory(action)
        except ValueError:
            pass  # Allow raw strings
    
    logs = audit_service.get_logs(
        project_id=project_id,
        execution_id=execution_id,
        task_id=task_id,
        actor_type=actor_type_enum,
        action=action_enum,
        entity_type=entity_type,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
        db=db
    )
    
    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=len(logs),
        limit=limit,
        offset=offset
    )


@router.get("/executions/{execution_id}/timeline", response_model=AuditLogListResponse)
def get_execution_timeline(
    execution_id: int,
    db: Session = Depends(get_db)
):
    """Get complete audit timeline for an execution."""
    logs = audit_service.get_execution_timeline(execution_id=execution_id, db=db)
    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=len(logs),
        limit=1000,
        offset=0
    )


@router.get("/tasks/{task_id}/history", response_model=AuditLogListResponse)
def get_task_history(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get audit history for a BUILD task."""
    logs = audit_service.get_task_history(task_id=task_id, db=db)
    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=len(logs),
        limit=100,
        offset=0
    )


@router.get("/actions", response_model=List[str])
def list_action_categories():
    """List available action categories."""
    return [action.value for action in ActionCategory]


@router.get("/actor-types", response_model=List[str])
def list_actor_types():
    """List available actor types."""
    return [actor.value for actor in ActorType]
