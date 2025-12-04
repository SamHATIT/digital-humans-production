"""API routes for Change Request management."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.models.change_request import ChangeRequest
from app.models.business_requirement import BusinessRequirement
from app.schemas.change_request import (
    ChangeRequestCreate,
    ChangeRequestUpdate,
    ChangeRequestResponse,
    ChangeRequestList,
    ChangeRequestSubmit,
    ChangeRequestApprove
)

router = APIRouter(prefix="/api/projects", tags=["change-requests"])


def get_next_cr_number(db: Session, project_id: int) -> str:
    """Generate next CR number for a project."""
    count = db.query(func.count(ChangeRequest.id)).filter(
        ChangeRequest.project_id == project_id
    ).scalar()
    return f"CR-{str(count + 1).zfill(3)}"


@router.get("/{project_id}/change-requests", response_model=ChangeRequestList)
async def list_change_requests(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all change requests for a project."""
    # Verify project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Build query
    query = db.query(ChangeRequest).filter(ChangeRequest.project_id == project_id)
    
    if status:
        query = query.filter(ChangeRequest.status == status)
    
    crs = query.order_by(ChangeRequest.created_at.desc()).all()
    
    # Build responses with related BR text
    responses = []
    for cr in crs:
        resp = ChangeRequestResponse.model_validate(cr)
        if cr.related_br_id:
            br = db.query(BusinessRequirement).filter(
                BusinessRequirement.id == cr.related_br_id
            ).first()
            if br:
                resp.related_br_text = f"{br.br_id}: {br.requirement[:100]}..."
        responses.append(resp)
    
    # Count by status
    pending_count = sum(1 for cr in crs if cr.status in ['draft', 'submitted', 'analyzed', 'approved', 'processing'])
    completed_count = sum(1 for cr in crs if cr.status == 'completed')
    
    return ChangeRequestList(
        change_requests=responses,
        total_count=len(crs),
        pending_count=pending_count,
        completed_count=completed_count
    )


@router.post("/{project_id}/change-requests", response_model=ChangeRequestResponse)
async def create_change_request(
    project_id: int,
    cr_data: ChangeRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new change request."""
    # Verify project
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get latest execution
    execution = db.query(Execution).filter(
        Execution.project_id == project_id
    ).order_by(Execution.created_at.desc()).first()
    
    # Create CR
    cr_number = get_next_cr_number(db, project_id)
    
    cr = ChangeRequest(
        project_id=project_id,
        execution_id=execution.id if execution else None,
        cr_number=cr_number,
        category=cr_data.category,
        title=cr_data.title,
        description=cr_data.description,
        priority=cr_data.priority,
        related_br_id=cr_data.related_br_id,
        status="draft",
        created_by=current_user.id
    )
    
    db.add(cr)
    db.commit()
    db.refresh(cr)
    
    return ChangeRequestResponse.model_validate(cr)


@router.get("/{project_id}/change-requests/{cr_id}", response_model=ChangeRequestResponse)
async def get_change_request(
    project_id: int,
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific change request."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    # Verify access
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    
    resp = ChangeRequestResponse.model_validate(cr)
    if cr.related_br_id:
        br = db.query(BusinessRequirement).filter(
            BusinessRequirement.id == cr.related_br_id
        ).first()
        if br:
            resp.related_br_text = f"{br.br_id}: {br.requirement}"
    
    return resp


@router.put("/{project_id}/change-requests/{cr_id}", response_model=ChangeRequestResponse)
async def update_change_request(
    project_id: int,
    cr_id: int,
    cr_data: ChangeRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a change request (only if in draft status)."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "draft":
        raise HTTPException(status_code=400, detail="Can only update draft CRs")
    
    # Update fields
    if cr_data.title is not None:
        cr.title = cr_data.title
    if cr_data.description is not None:
        cr.description = cr_data.description
    if cr_data.priority is not None:
        cr.priority = cr_data.priority
    if cr_data.category is not None:
        cr.category = cr_data.category
    if cr_data.related_br_id is not None:
        cr.related_br_id = cr_data.related_br_id
    
    db.commit()
    db.refresh(cr)
    
    return ChangeRequestResponse.model_validate(cr)


@router.post("/{project_id}/change-requests/{cr_id}/submit")
async def submit_change_request(
    project_id: int,
    cr_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a CR for impact analysis by Sophie."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "draft":
        raise HTTPException(status_code=400, detail="CR already submitted")
    
    # Update status
    cr.status = "submitted"
    cr.submitted_at = datetime.utcnow()
    db.commit()
    
    # TODO: Trigger impact analysis in background
    # background_tasks.add_task(analyze_impact, cr.id)
    
    # For now, mock the analysis
    cr.status = "analyzed"
    cr.analyzed_at = datetime.utcnow()
    cr.impact_analysis = {
        "affected_brs": [cr.related_br_id] if cr.related_br_id else [],
        "affected_use_cases": [],
        "affected_architecture": [cr.category],
        "affected_agents": ["ba", "architect"] if cr.category in ["business_rule", "data_model", "process"] else ["architect"],
        "summary": f"Cette modification impacte la catégorie {cr.category}. Re-génération partielle nécessaire.",
        "risk_level": "medium" if cr.priority in ["high", "critical"] else "low"
    }
    cr.estimated_cost = 2.50
    cr.agents_to_rerun = cr.impact_analysis["affected_agents"]
    db.commit()
    
    return {
        "message": "CR submitted and analyzed",
        "cr_number": cr.cr_number,
        "status": cr.status,
        "impact_analysis": cr.impact_analysis
    }


@router.post("/{project_id}/change-requests/{cr_id}/approve")
async def approve_change_request(
    project_id: int,
    cr_id: int,
    approval: ChangeRequestApprove,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a CR and trigger re-generation."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "analyzed":
        raise HTTPException(status_code=400, detail="CR must be analyzed before approval")
    
    # Update status
    cr.status = "approved"
    cr.approved_at = datetime.utcnow()
    if approval.notes:
        cr.resolution_notes = approval.notes
    db.commit()
    
    # TODO: Trigger re-generation workflow
    # background_tasks.add_task(process_change_request, cr.id)
    
    return {
        "message": "CR approved - re-generation will start",
        "cr_number": cr.cr_number,
        "status": cr.status,
        "agents_to_rerun": cr.agents_to_rerun
    }


@router.post("/{project_id}/change-requests/{cr_id}/reject")
async def reject_change_request(
    project_id: int,
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Reject a CR."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status in ["completed", "rejected"]:
        raise HTTPException(status_code=400, detail="CR already finalized")
    
    cr.status = "rejected"
    db.commit()
    
    return {"message": "CR rejected", "cr_number": cr.cr_number}


@router.delete("/{project_id}/change-requests/{cr_id}")
async def delete_change_request(
    project_id: int,
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a draft CR."""
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "draft":
        raise HTTPException(status_code=400, detail="Can only delete draft CRs")
    
    db.delete(cr)
    db.commit()
    
    return {"message": "CR deleted"}
