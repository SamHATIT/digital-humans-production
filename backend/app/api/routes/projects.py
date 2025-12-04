from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from pydantic import BaseModel
from datetime import datetime
from app.database import get_db
from app.models.project import Project
from app.models.execution import Execution
from app.models.user import User
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

# Response schemas
class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    salesforce_product: Optional[str] = None
    organization_type: Optional[str] = None

    current_sds_version: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class ExecutionSummary(BaseModel):
    id: int
    status: str
    progress: int
    created_at: datetime
    
    class Config:
        from_attributes = True

class ProjectDetailResponse(ProjectResponse):
    executions: List[ExecutionSummary] = []

# Transitions de statuts autorisées
VALID_TRANSITIONS = {
    "Draft": ["Ready"],
    "Ready": ["Active"],
    "Active": ["SDS Completed"],
    "SDS Completed": ["Building"],
    "Building": ["Deployed"],
}


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ProjectDetailResponse:
    """
    Get project details by ID with execution history.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Vérifier que l'utilisateur possède ce projet
    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this project"
        )
    
    # Get executions for this project
    executions = db.query(Execution).filter(
        Execution.project_id == project_id
    ).order_by(Execution.created_at.desc()).limit(10).all()
    
    return ProjectDetailResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        salesforce_product=project.salesforce_product,
        organization_type=project.organization_type,

        current_sds_version=project.current_sds_version,
        created_at=project.created_at,
        updated_at=project.updated_at,
        executions=[
            ExecutionSummary(
                id=e.id,
                status=e.status or "UNKNOWN",
                progress=e.progress or 0,
                created_at=e.created_at
            ) for e in executions
        ]
    )


@router.patch("/{project_id}/status")
async def update_project_status(
    project_id: int,
    status_data: Dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """
    Met à jour le statut d'un projet avec validation des transitions.
    
    Workflow de statuts :
    Draft → Ready → Active → SDS Completed → Building → Deployed
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Vérifier que l'utilisateur possède ce projet
    if project.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this project"
        )
    
    new_status = status_data.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status is required"
        )
    
    # Valider la transition
    current_status = project.status or "Draft"
    valid_next_statuses = VALID_TRANSITIONS.get(current_status, [])
    
    if new_status not in valid_next_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition: {current_status} → {new_status}. Valid transitions: {', '.join(valid_next_statuses)}"
        )
    
    # Mettre à jour le statut
    project.status = new_status
    db.commit()
    db.refresh(project)
    
    return {
        "project_id": project_id,
        "status": new_status,
        "previous_status": current_status,
        "message": f"Project status updated to {new_status}"
    }
