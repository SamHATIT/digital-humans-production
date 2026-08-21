"""
Audit API - Endpoints for querying audit logs.
CORE-001: Enables debugging and compliance review.

LOT-B bis (kim:SEC-01) : ce routeur etait monte sur /api/audit
(`main.py:101`) sans aucune dependance d'authentification. `GET
/api/audit/logs` rendait lisible par un anonyme l'historique d'actions de
tous les clients, avec `actor_id`, `ip_address` et `user_agent` — de quoi
cartographier la clientele. Les cinq routes exigent desormais un compte, et
les trois qui rendent des donnees sont cloisonnees par client.

**Modele retenu pour /logs : journal par client, pas journal global
reserve a un role admin.** Aucune notion de role n'existe dans le produit
(`grep -rn "is_admin\|is_superuser\|role" app/models/user.py
app/utils/dependencies.py` ne renvoie rien) : un journal global supposerait
d'ajouter une colonne de role, une migration et une administration — une
fonctionnalite, alors que le perimetre est gele. Consequences assumees :

- `/logs` exige desormais `project_id`, et ce projet doit appartenir a
  l'appelant. C'est ce qui permet de deleguer a `audit_service.get_logs()`
  **sans modifier le service** (hors perimetre) tout en gardant une
  pagination juste : filtrer apres coup les lignes rendues par le service
  fausserait `limit`/`offset` et pourrait rendre des pages vides.
- Les lignes a `project_id NULL` (auth.login, auth.fail, evenements
  systeme, appels LLM hors projet) ne sont plus atteignables par l'API.
  C'est voulu : `auth.fail` porte l'`actor_id` et l'IP d'autres comptes.
  L'exploitation garde l'acces direct a la table pour le forensique.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.services.audit_service import audit_service
from app.models.audit import ActorType, ActionCategory
from app.models.execution import Execution
from app.models.project import Project
from app.models.task_execution import TaskExecution
from app.models.user import User
from app.utils.dependencies import get_current_user
from app.utils.ownership import verify_execution_access, verify_project_access

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(get_current_user)],
)


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
    project_id: int = Query(..., description="Project ID (required — audit logs are scoped to a project you own)"),
    execution_id: Optional[int] = Query(None, description="Filter by execution ID"),
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    since: Optional[datetime] = Query(None, description="Filter logs since datetime"),
    until: Optional[datetime] = Query(None, description="Filter logs until datetime"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Query audit logs of a project you own, with various filters."""
    verify_project_access(project_id, current_user.id, db)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get complete audit timeline for an execution you own."""
    verify_execution_access(execution_id, current_user.id, db)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get audit history for a BUILD task belonging to one of your executions.

    LOT-B bis : `task_id` ("TASK-001") n'est pas unique globalement — il est
    porte par chaque execution. Filtrer sur ce seul champ melangeait les
    journaux de plusieurs clients. On resout d'abord les executions de
    l'appelant qui portent ce task_id, puis on interroge le service
    execution par execution.
    """
    execution_ids = [
        row[0]
        for row in db.query(TaskExecution.execution_id)
        .join(Execution, TaskExecution.execution_id == Execution.id)
        .join(Project, Execution.project_id == Project.id)
        .filter(
            TaskExecution.task_id == task_id,
            Project.user_id == current_user.id,
        )
        .distinct()
        .all()
    ]

    if not execution_ids:
        raise HTTPException(status_code=404, detail="Task not found")

    logs = []
    for execution_id in execution_ids:
        logs.extend(
            audit_service.get_logs(
                task_id=task_id, execution_id=execution_id, limit=100, db=db
            )
        )
    logs.sort(key=lambda log: log.timestamp, reverse=True)
    logs = logs[:100]

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
