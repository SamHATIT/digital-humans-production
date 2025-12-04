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
    """Submit a CR for impact analysis by Sophie (using Claude)."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[CR Route] Submit CR {cr_id} for project {project_id}")
    
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "draft":
        raise HTTPException(status_code=400, detail="CR already submitted")
    
    # Update status to submitted
    cr.status = "submitted"
    cr.submitted_at = datetime.utcnow()
    db.commit()
    logger.info(f"[CR Route] CR {cr.cr_number} status updated to submitted")
    
    # Run real impact analysis with Claude
    from app.services.change_request_service import ChangeRequestService
    service = ChangeRequestService(db)
    
    logger.info(f"[CR Route] Starting impact analysis for CR {cr.cr_number}")
    result = service.analyze_impact(cr_id)
    
    if result.get("success"):
        logger.info(f"[CR Route] Impact analysis complete for CR {cr.cr_number}")
        return {
            "message": "CR submitted and analyzed",
            "cr_number": result["cr_number"],
            "status": "analyzed",
            "impact_analysis": result["impact_analysis"],
            "estimated_cost": result["estimated_cost"],
            "agents_to_rerun": result["agents_to_rerun"]
        }
    else:
        logger.error(f"[CR Route] Impact analysis failed: {result.get('error')}")
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))


@router.post("/{project_id}/change-requests/{cr_id}/approve")
async def approve_change_request(
    project_id: int,
    cr_id: int,
    approval: ChangeRequestApprove,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve a CR and trigger targeted re-generation."""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[CR Route] Approve CR {cr_id} for project {project_id}")
    
    cr = db.query(ChangeRequest).filter(
        ChangeRequest.id == cr_id,
        ChangeRequest.project_id == project_id
    ).first()
    
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    
    if cr.status != "analyzed":
        raise HTTPException(status_code=400, detail="CR must be analyzed before approval")
    
    # Update status to approved
    cr.status = "approved"
    cr.approved_at = datetime.utcnow()
    if approval.notes:
        cr.resolution_notes = approval.notes
    db.commit()
    logger.info(f"[CR Route] CR {cr.cr_number} approved")
    
    # Trigger re-generation in background
    from app.services.change_request_service import ChangeRequestService
    
    async def process_cr_background(cr_id: int):
        """Background task for CR processing."""
        from app.database import SessionLocal
        db_session = SessionLocal()
        try:
            service = ChangeRequestService(db_session)
            result = await service.process_change_request(cr_id)
            logger.info(f"[CR Route] Background processing complete: {result}")
        except Exception as e:
            logger.error(f"[CR Route] Background processing failed: {e}")
        finally:
            db_session.close()
    
    background_tasks.add_task(process_cr_background, cr_id)
    logger.info(f"[CR Route] Background task scheduled for CR {cr.cr_number}")
    
    return {
        "message": "CR approved - re-generation started in background",
        "cr_number": cr.cr_number,
        "status": "approved",
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
