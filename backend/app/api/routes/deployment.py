"""
Deployment API Routes
- BLD-01: SFDX Package Generation
- DPL-04: Rollback Support
- DPL-05: Release Notes Generation
- DPL-06: Multi-Environment Support
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/deployment", tags=["Deployment"])


# ========== Request/Response Models ==========

class PackageGenerateRequest(BaseModel):
    files: Dict[str, str]  # file_path -> content
    package_name: str = "digital-humans-package"
    api_version: str = "59.0"
    execution_id: Optional[int] = None

class SnapshotRequest(BaseModel):
    deployment_id: str
    components: Optional[List[str]] = None

class RollbackRequest(BaseModel):
    snapshot_path: str
    deployment_id: Optional[str] = None

class ReleaseNotesRequest(BaseModel):
    deployment_id: str
    components: Dict[str, List[str]]
    project_name: str = "Digital Humans Deployment"

class PromoteRequest(BaseModel):
    source_path: str
    target_env: str
    test_level: str = "RunLocalTests"
    dry_run: bool = False


# ========== BLD-01: Package Generation ==========

@router.post("/package/generate")
async def generate_package(request: PackageGenerateRequest):
    """
    Generate a complete SFDX package from agent-generated files.
    Returns package path and manifest for deployment.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        result = await sfdx.generate_sfdx_package(
            files=request.files,
            package_name=request.package_name,
            api_version=request.api_version
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Package generation failed"))
        
        return {
            "success": True,
            "package_path": result["package_path"],
            "package_name": result["package_name"],
            "components": result["components"],
            "manifest_path": result["manifest_path"],
            "project_file": result["project_file"]
        }
        
    except Exception as e:
        logger.error(f"Package generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/package/{execution_id}/files")
async def get_package_files(execution_id: int):
    """
    Get all generated files for an execution ready for packaging.
    """
    from sqlalchemy import text
    from app.database import get_db_session
    
    try:
        with get_db_session() as session:
            # Get all files from task_executions for this execution
            result = session.execute(text("""
                SELECT task_id, generated_files 
                FROM task_executions 
                WHERE execution_id = :exec_id 
                AND generated_files IS NOT NULL
            """), {"exec_id": execution_id})
            
            all_files = {}
            for row in result:
                if row.generated_files:
                    files = row.generated_files if isinstance(row.generated_files, dict) else {}
                    all_files.update(files)
            
            return {
                "success": True,
                "execution_id": execution_id,
                "files_count": len(all_files),
                "files": all_files
            }
            
    except Exception as e:
        logger.error(f"Error getting package files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== DPL-04: Rollback Support ==========

@router.post("/snapshot/create")
async def create_snapshot(request: SnapshotRequest):
    """
    Create a deployment snapshot for potential rollback.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        result = await sfdx.create_deployment_snapshot(
            deployment_id=request.deployment_id,
            components=request.components
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Snapshot creation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rollback")
async def rollback_deployment(request: RollbackRequest):
    """
    Rollback to a previous deployment snapshot.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        result = await sfdx.rollback_deployment(
            snapshot_path=request.snapshot_path,
            deployment_id=request.deployment_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Rollback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshots")
async def list_snapshots():
    """
    List available deployment snapshots.
    """
    import os
    import tempfile
    
    snapshots = []
    temp_dir = tempfile.gettempdir()
    
    for item in os.listdir(temp_dir):
        if item.startswith("snapshot_"):
            snapshot_path = os.path.join(temp_dir, item)
            meta_file = os.path.join(snapshot_path, "snapshot_meta.json")
            
            if os.path.exists(meta_file):
                import json
                with open(meta_file) as f:
                    meta = json.load(f)
                snapshots.append({
                    "deployment_id": meta.get("deployment_id"),
                    "created_at": meta.get("created_at"),
                    "path": snapshot_path,
                    "components": meta.get("components", [])
                })
    
    return {"snapshots": snapshots, "count": len(snapshots)}


# ========== DPL-05: Release Notes ==========

@router.post("/release-notes/generate")
async def generate_release_notes(request: ReleaseNotesRequest):
    """
    Generate release notes for a deployment.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        result = sfdx.generate_release_notes(
            deployment_id=request.deployment_id,
            components=request.components,
            project_name=request.project_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Release notes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/release-notes/{execution_id}")
async def get_execution_release_notes(execution_id: int):
    """
    Generate release notes for a specific execution.
    """
    from app.services.sfdx_service import get_sfdx_service
    from sqlalchemy import text
    from app.database import get_db_session
    
    try:
        # Get components from execution
        with get_db_session() as session:
            result = session.execute(text("""
                SELECT task_id, generated_files 
                FROM task_executions 
                WHERE execution_id = :exec_id 
                AND generated_files IS NOT NULL
            """), {"exec_id": execution_id})
            
            components = {
                "classes": [], "triggers": [], "lwc": [], 
                "objects": [], "flows": [], "other": []
            }
            
            for row in result:
                if row.generated_files:
                    for file_path in row.generated_files.keys():
                        if "/classes/" in file_path:
                            components["classes"].append(file_path)
                        elif "/triggers/" in file_path:
                            components["triggers"].append(file_path)
                        elif "/lwc/" in file_path:
                            components["lwc"].append(file_path)
                        elif "/objects/" in file_path:
                            components["objects"].append(file_path)
                        elif "/flows/" in file_path:
                            components["flows"].append(file_path)
                        else:
                            components["other"].append(file_path)
        
        sfdx = get_sfdx_service()
        result = sfdx.generate_release_notes(
            deployment_id=f"EXEC-{execution_id}",
            components=components,
            project_name="Digital Humans Deployment"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Release notes error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== DPL-06: Multi-Environment ==========

@router.get("/environments")
async def list_environments():
    """
    List all configured Salesforce environments.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        environments = await sfdx.get_environments()
        
        return {
            "success": True,
            "environments": environments,
            "count": len(environments)
        }
        
    except Exception as e:
        logger.error(f"Error listing environments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/promote")
async def promote_to_environment(request: PromoteRequest):
    """
    Promote code to a target environment.
    """
    from app.services.sfdx_service import get_sfdx_service
    
    try:
        sfdx = get_sfdx_service()
        result = await sfdx.promote_to_environment(
            source_path=request.source_path,
            target_env=request.target_env,
            test_level=request.test_level,
            dry_run=request.dry_run
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Promotion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_deployment(request: PromoteRequest):
    """
    Validate a deployment without actually deploying (dry run).
    """
    request.dry_run = True
    return await promote_to_environment(request)
