"""API routes for SDS version management."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os

from app.database import get_db
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header
from app.models.user import User
from app.models.project import Project
from app.models.sds_version import SDSVersion
from app.schemas.sds_version import (
    SDSVersionCreate,
    SDSVersionResponse,
    SDSVersionList
)

router = APIRouter(prefix="/api/projects", tags=["sds-versions"])


@router.get("/{project_id}/sds-versions", response_model=SDSVersionList)
async def get_sds_versions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all SDS versions for a project."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get versions
    versions = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id
    ).order_by(SDSVersion.version_number.desc()).all()
    
    # Build response with download URLs
    version_responses = []
    for v in versions:
        resp = SDSVersionResponse.model_validate(v)
        if v.file_path:
            resp.download_url = f"/api/projects/{project_id}/sds-versions/{v.version_number}/download"
        version_responses.append(resp)
    
    return SDSVersionList(
        versions=version_responses,
        current_version=project.current_sds_version or 1,
        total_count=len(versions)
    )


# IMPORTANT: /current routes MUST be defined BEFORE /{version_number} routes
# otherwise FastAPI will try to parse "current" as an integer

@router.get("/{project_id}/sds-versions/current/download")
async def download_current_sds(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """Download the current (latest) SDS version."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    current_version = project.current_sds_version or 1
    
    # Get version
    version = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id,
        SDSVersion.version_number == current_version
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="Current SDS version not found")
    
    if not version.file_path or not os.path.exists(version.file_path):
        raise HTTPException(status_code=404, detail="SDS file not found")
    
    filename = version.file_name or f"SDS_v{current_version}.docx"
    
    return FileResponse(
        path=version.file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/{project_id}/sds-versions/{version_number}")
async def get_sds_version(
    project_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific SDS version."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get version
    version = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id,
        SDSVersion.version_number == version_number
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="SDS version not found")
    
    resp = SDSVersionResponse.model_validate(version)
    if version.file_path:
        resp.download_url = f"/api/projects/{project_id}/sds-versions/{version_number}/download"
    
    return resp


@router.get("/{project_id}/sds-versions/{version_number}/download")
async def download_sds_version(
    project_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """Download an SDS version file."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get version
    version = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id,
        SDSVersion.version_number == version_number
    ).first()
    
    if not version:
        raise HTTPException(status_code=404, detail="SDS version not found")
    
    if not version.file_path or not os.path.exists(version.file_path):
        raise HTTPException(status_code=404, detail="SDS file not found")
    
    filename = version.file_name or f"SDS_v{version_number}.docx"
    
    return FileResponse(
        path=version.file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.post("/{project_id}/approve-sds")
async def approve_sds(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve SDS and move to BUILD_READY status."""
    from app.models.project import ProjectStatus
    
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check there's at least one SDS version
    version_count = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id
    ).count()
    
    if version_count == 0:
        raise HTTPException(status_code=400, detail="No SDS version available to approve")
    
    # Check no pending CRs
    from app.models.change_request import ChangeRequest
    pending_crs = db.query(ChangeRequest).filter(
        ChangeRequest.project_id == project_id,
        ChangeRequest.status.in_(['draft', 'submitted', 'analyzed', 'approved', 'processing'])
    ).count()
    
    if pending_crs > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot approve SDS with {pending_crs} pending change request(s)"
        )
    
    # Update project status
    project.status = ProjectStatus.SDS_APPROVED
    db.commit()
    
    return {
        "message": "SDS approved successfully",
        "project_id": project_id,
        "status": "sds_approved",
        "current_sds_version": project.current_sds_version
    }
