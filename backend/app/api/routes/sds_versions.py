"""API routes for SDS version management."""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from pathlib import Path as _Path
import os
import sys
import logging

from app.database import get_db
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.models.sds_version import SDSVersion
from app.schemas.sds_version import (
    SDSVersionResponse,
    SDSVersionList
)

logger = logging.getLogger(__name__)

# Build_sds path setup (extracted to public function in iter 7)
_REPO_ROOT = _Path(__file__).resolve().parents[4]
_TOOLS_PATH = str(_REPO_ROOT / "tools")
if _TOOLS_PATH not in sys.path:
    sys.path.insert(0, _TOOLS_PATH)
_OUTPUTS_DIR = _REPO_ROOT / "outputs"
_OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/api/projects", tags=["sds-versions"])


@router.get("/{project_id}/sds-versions", response_model=SDSVersionList)
def get_sds_versions(
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
def download_current_sds(
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
def get_sds_version(
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
def download_sds_version(
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
def approve_sds(
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


@router.post("/{project_id}/sds-versions", response_model=SDSVersionResponse, status_code=status.HTTP_201_CREATED)
def create_sds_version_from_execution(
    project_id: int,
    payload: dict = Body(..., example={"execution_id": 146, "notes": "Snapshot pre-merge"}),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Snapshot freeze d'un SDS depuis une execution.
    
    Build le SDS depuis la DB via build_sds(), ecrit dans outputs/SDS_<project>_v<n>.html,
    cree une row sds_versions immuable. Le fichier ne doit JAMAIS etre modifie apres
    creation (immutabilite garantie par convention + pas de PUT/PATCH sur cette ressource).
    """
    execution_id = payload.get("execution_id")
    notes = payload.get("notes", "")
    if not execution_id:
        raise HTTPException(status_code=400, detail="execution_id is required")
    
    # Verify project belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Verify execution belongs to this project
    execution = db.query(Execution).filter(
        Execution.id == execution_id,
        Execution.project_id == project_id
    ).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found in this project")
    
    # Compute next version_number
    max_v = db.query(sa_func.max(SDSVersion.version_number)).filter(
        SDSVersion.project_id == project_id
    ).scalar() or 0
    version_number = max_v + 1
    
    # Build SDS
    try:
        from build_sds import build_sds
        html = build_sds(execution_id)
    except Exception as e:
        logger.error(f"build_sds failed for execution {execution_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"SDS rendering failed: {type(e).__name__}: {e}"
        )
    
    # Ecrire dans outputs/
    safe_name = project.name.replace(" ", "_").replace("/", "_")
    file_name = f"SDS_{safe_name}_v{version_number}.html"
    file_path = _OUTPUTS_DIR / file_name
    file_path.write_text(html, encoding="utf-8")
    file_size = file_path.stat().st_size
    
    # Persist DB row
    sds_version = SDSVersion(
        project_id=project_id,
        execution_id=execution_id,
        version_number=version_number,
        file_path=str(file_path),
        file_name=file_name,
        file_size=file_size,
        notes=notes or None,
    )
    db.add(sds_version)
    db.commit()
    db.refresh(sds_version)
    
    logger.info(f"SDS version v{version_number} created for project {project_id} from execution {execution_id} ({file_size:,} bytes)")
    
    resp = SDSVersionResponse.model_validate(sds_version)
    resp.download_url = f"/api/projects/{project_id}/sds-versions/{version_number}/view"
    return resp


@router.get("/{project_id}/sds-versions/{version_number}/view", response_class=HTMLResponse)
def view_sds_version_inline(
    project_id: int,
    version_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Retourne le HTML d'une version frozen inline (vs /download qui force le DL).
    
    Lit le fichier outputs/SDS_<project>_v<n>.html et retourne HTMLResponse.
    Le fichier est immuable depuis sa creation par POST /sds-versions.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    sds_version = db.query(SDSVersion).filter(
        SDSVersion.project_id == project_id,
        SDSVersion.version_number == version_number
    ).first()
    if not sds_version:
        raise HTTPException(status_code=404, detail=f"SDS version v{version_number} not found")
    
    if not sds_version.file_path or not os.path.exists(sds_version.file_path):
        raise HTTPException(status_code=410, detail="SDS version file is no longer available on disk")
    
    with open(sds_version.file_path, "r", encoding="utf-8") as f:
        html = f.read()
    
    return HTMLResponse(content=html, status_code=200)
