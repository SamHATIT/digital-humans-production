"""
Business Requirements API routes for BR validation workflow.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import csv
import io

from app.database import get_db
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.models.business_requirement import (
    BusinessRequirement,
    BRStatus,
    BRPriority,
    BRSource,
)
from app.schemas.business_requirement import (
    BusinessRequirementCreate,
    BusinessRequirementUpdate,
    BusinessRequirementResponse,
    BusinessRequirementListResponse,
    BRValidateAllResponse,
    BRReorderRequest,
    BRReorderResponse,
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/br", tags=["Business Requirements"])


# ==================== LIST BRs ====================

@router.get("/{project_id}", response_model=BusinessRequirementListResponse)
async def list_business_requirements(
    project_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all business requirements for a project.
    
    Returns BRs with statistics (pending, validated, modified, deleted).
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Query BRs
    query = db.query(BusinessRequirement).filter(
        BusinessRequirement.project_id == project_id
    )
    
    if not include_deleted:
        query = query.filter(BusinessRequirement.status != BRStatus.DELETED)
    
    brs = query.order_by(BusinessRequirement.order_index).all()
    
    # Calculate stats
    all_brs = db.query(BusinessRequirement).filter(
        BusinessRequirement.project_id == project_id
    ).all()
    
    stats = {
        "pending": sum(1 for br in all_brs if br.status == BRStatus.PENDING),
        "validated": sum(1 for br in all_brs if br.status == BRStatus.VALIDATED),
        "modified": sum(1 for br in all_brs if br.status == BRStatus.MODIFIED),
        "deleted": sum(1 for br in all_brs if br.status == BRStatus.DELETED),
    }
    
    return BusinessRequirementListResponse(
        brs=brs,
        total=len(brs),
        **stats
    )


# ==================== GET SINGLE BR ====================

@router.get("/item/{br_id}", response_model=BusinessRequirementResponse)
async def get_business_requirement(
    br_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a single business requirement by ID."""
    br = db.query(BusinessRequirement).join(Project).filter(
        BusinessRequirement.id == br_id,
        Project.user_id == current_user.id
    ).first()
    
    if not br:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business requirement not found"
        )
    
    return br


# ==================== CREATE BR (MANUAL) ====================

@router.post("/{project_id}", response_model=BusinessRequirementResponse, status_code=status.HTTP_201_CREATED)
async def create_business_requirement(
    project_id: int,
    br_data: BusinessRequirementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Manually add a new business requirement.
    
    This creates a BR with source='manual' (vs 'extracted' from Sophie).
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get next BR ID
    max_br = db.query(func.max(BusinessRequirement.order_index)).filter(
        BusinessRequirement.project_id == project_id
    ).scalar() or 0
    
    next_index = max_br + 1
    br_id = f"BR-{next_index:03d}"
    
    # Create BR
    br = BusinessRequirement(
        project_id=project_id,
        br_id=br_id,
        category=br_data.category,
        requirement=br_data.requirement,
        priority=br_data.priority,
        client_notes=br_data.client_notes,
        source=BRSource.MANUAL,
        status=BRStatus.VALIDATED,  # Manual BRs are auto-validated
        validated_at=datetime.utcnow(),
        validated_by=current_user.id,
        order_index=next_index,
    )
    
    db.add(br)
    db.commit()
    db.refresh(br)
    
    return br


# ==================== UPDATE BR ====================

@router.put("/item/{br_id}", response_model=BusinessRequirementResponse)
async def update_business_requirement(
    br_id: int,
    br_data: BusinessRequirementUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a business requirement.
    
    If the requirement text is changed, status becomes 'modified'.
    """
    br = db.query(BusinessRequirement).join(Project).filter(
        BusinessRequirement.id == br_id,
        Project.user_id == current_user.id
    ).first()
    
    if not br:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business requirement not found"
        )
    
    # Track if requirement text changed
    text_changed = False
    
    # Update fields
    update_data = br_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "requirement" and value != br.requirement:
            text_changed = True
        setattr(br, field, value)
    
    # If text changed, mark as modified
    if text_changed and br.source == BRSource.EXTRACTED:
        br.status = BRStatus.MODIFIED
    
    br.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(br)
    
    return br


# ==================== DELETE BR ====================

@router.delete("/item/{br_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business_requirement(
    br_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Soft delete a business requirement.
    
    Sets status to 'deleted' instead of actually removing from DB.
    """
    br = db.query(BusinessRequirement).join(Project).filter(
        BusinessRequirement.id == br_id,
        Project.user_id == current_user.id
    ).first()
    
    if not br:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business requirement not found"
        )
    
    br.status = BRStatus.DELETED
    br.updated_at = datetime.utcnow()
    db.commit()
    
    return None


# ==================== VALIDATE ALL BRs ====================

@router.post("/{project_id}/validate-all", response_model=BRValidateAllResponse)
async def validate_all_requirements(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Validate all pending business requirements.
    
    Marks all non-deleted BRs as validated and ready for agent processing.
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get all non-deleted BRs
    brs = db.query(BusinessRequirement).filter(
        BusinessRequirement.project_id == project_id,
        BusinessRequirement.status != BRStatus.DELETED
    ).all()
    
    now = datetime.utcnow()
    validated_count = 0
    
    for br in brs:
        if br.status == BRStatus.PENDING:
            br.status = BRStatus.VALIDATED
            br.validated_at = now
            br.validated_by = current_user.id
            validated_count += 1
    
    db.commit()
    
    return BRValidateAllResponse(
        validated_count=validated_count,
        message=f"Validated {validated_count} requirements. Ready for agent processing."
    )


# ==================== EXPORT CSV ====================

@router.get("/{project_id}/export")
async def export_requirements_csv(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export all business requirements as CSV.
    
    Returns a downloadable CSV file.
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Get all BRs (including deleted for audit)
    brs = db.query(BusinessRequirement).filter(
        BusinessRequirement.project_id == project_id
    ).order_by(BusinessRequirement.order_index).all()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "BR_ID",
        "Category",
        "Requirement",
        "Priority",
        "Status",
        "Source",
        "Client_Notes",
        "Original_Text",
        "Created_At"
    ])
    
    # Data rows
    for br in brs:
        writer.writerow([
            br.br_id,
            br.category or "",
            br.requirement,
            br.priority.value if br.priority else "should",
            br.status.value if br.status else "pending",
            br.source.value if br.source else "extracted",
            br.client_notes or "",
            br.original_text or "",
            br.created_at.isoformat() if br.created_at else ""
        ])
    
    output.seek(0)
    
    # Create filename
    safe_name = project.name.replace(" ", "_").replace("/", "-")[:30]
    filename = f"BR_{safe_name}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ==================== REORDER BRs ====================

@router.post("/{project_id}/reorder", response_model=BRReorderResponse)
async def reorder_requirements(
    project_id: int,
    reorder_data: BRReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reorder business requirements.
    
    Accepts a list of BR IDs in the new order.
    """
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    # Update order_index for each BR
    for index, br_id in enumerate(reorder_data.order):
        br = db.query(BusinessRequirement).filter(
            BusinessRequirement.id == br_id,
            BusinessRequirement.project_id == project_id
        ).first()
        
        if br:
            br.order_index = index
            br.updated_at = datetime.utcnow()
    
    db.commit()
    
    return BRReorderResponse(
        success=True,
        message=f"Reordered {len(reorder_data.order)} requirements"
    )
