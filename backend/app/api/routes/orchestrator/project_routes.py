"""
Project management routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — Project CRUD operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.execution import Execution, ExecutionStatus
from app.schemas.project import Project as ProjectSchema, ProjectCreate, ProjectUpdate
from app.utils.dependencies import get_current_user

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/projects", response_model=ProjectSchema, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project definition for PM Orchestrator."""
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        salesforce_product=project_data.salesforce_product,
        organization_type=project_data.organization_type,
        business_requirements=project_data.business_requirements,
        existing_systems=project_data.existing_systems,
        compliance_requirements=project_data.compliance_requirements,
        expected_users=project_data.expected_users,
        expected_data_volume=project_data.expected_data_volume,
        architecture_preferences=project_data.architecture_preferences,
        architecture_notes=project_data.architecture_notes,
        requirements_text=project_data.requirements_text,
        status=ProjectStatus.READY,
    )
    try:
        db.add(project)
        db.commit()
        db.refresh(project)
    except Exception:
        db.rollback()
        raise
    return project


@router.get("/projects", response_model=List[ProjectSchema])
def list_projects(
    skip: int = 0,
    limit: int = 50,
    status: Optional[ProjectStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all projects for the current user."""
    query = db.query(Project).filter(Project.user_id == current_user.id)
    if status:
        query = query.filter(Project.status == status)
    return query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get dashboard statistics for the current user."""
    from sqlalchemy import func

    total_projects = db.query(func.count(Project.id)).filter(
        Project.user_id == current_user.id
    ).scalar()

    projects_by_status = {}
    for s in ProjectStatus:
        count = db.query(func.count(Project.id)).filter(
            Project.user_id == current_user.id,
            Project.status == s,
        ).scalar()
        projects_by_status[s.value] = count

    active_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING]),
    ).scalar()

    completed_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status == ExecutionStatus.COMPLETED,
    ).scalar()

    failed_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status == ExecutionStatus.FAILED,
    ).scalar()

    recent_projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.created_at.desc()).limit(5).all()

    return {
        "total_projects": total_projects,
        "projects_by_status": projects_by_status,
        "active_executions": active_executions,
        "completed_executions": completed_executions,
        "failed_executions": failed_executions,
        "recent_projects": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "salesforce_product": p.salesforce_product,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in recent_projects
        ],
    }


@router.get("/projects/{project_id}", response_model=ProjectSchema)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific project by ID."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    return project


@router.put("/projects/{project_id}", response_model=ProjectSchema)
def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project definition."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    project.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(project)
    except Exception:
        db.rollback()
        raise
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )
    try:
        db.delete(project)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return None
