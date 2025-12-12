"""
Environment API Routes - Section 6.2 & 6.3
Endpoints for managing SFDX environments and Git config.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.services.environment_service import EnvironmentService


router = APIRouter()


# ========================================
# Pydantic Schemas
# ========================================

class EnvironmentCreate(BaseModel):
    environment_type: str  # dev, qa, uat, staging, prod
    alias: str
    instance_url: str
    username: str
    auth_method: str = "web_login"
    client_id: Optional[str] = None
    private_key: Optional[str] = None
    refresh_token: Optional[str] = None
    is_default: bool = False


class GitConfigCreate(BaseModel):
    git_provider: str  # github, gitlab, bitbucket, azure_devops
    repo_url: str
    access_token: str
    default_branch: str = "main"
    auto_commit: bool = True
    branch_strategy: str = "feature_branch"


# ========================================
# Environment Routes
# ========================================

@router.get("/projects/{project_id}/environments")
async def get_project_environments(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all environments for a project."""
    service = EnvironmentService(db)
    environments = service.get_project_environments(project_id)
    
    return {
        "project_id": project_id,
        "environments": [
            {
                "id": env.id,
                "environment_type": env.environment_type.value,
                "alias": env.alias,
                "display_name": env.display_name,
                "instance_url": env.instance_url,
                "username": env.username,
                "auth_method": env.auth_method.value,
                "connection_status": env.connection_status.value,
                "is_default": env.is_default,
                "last_connection_test": env.last_connection_test
            }
            for env in environments
        ]
    }


@router.post("/projects/{project_id}/environments")
async def create_environment(
    project_id: int,
    data: EnvironmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new environment for a project."""
    service = EnvironmentService(db)
    
    try:
        env = service.create_environment(
            project_id=project_id,
            environment_type=data.environment_type,
            alias=data.alias,
            instance_url=data.instance_url,
            username=data.username,
            auth_method=data.auth_method,
            client_id=data.client_id,
            private_key=data.private_key,
            refresh_token=data.refresh_token,
            is_default=data.is_default
        )
        
        return {
            "success": True,
            "environment": {
                "id": env.id,
                "alias": env.alias,
                "environment_type": env.environment_type.value,
                "connection_status": env.connection_status.value
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/environments/{environment_id}/test")
async def test_environment(
    environment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test connection to an environment."""
    service = EnvironmentService(db)
    result = service.test_environment_connection(environment_id)
    
    return result


@router.delete("/environments/{environment_id}")
async def delete_environment(
    environment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an environment."""
    service = EnvironmentService(db)
    deleted = service.delete_environment(environment_id)
    
    if deleted:
        return {"success": True, "message": "Environment deleted"}
    else:
        raise HTTPException(status_code=404, detail="Environment not found")


# ========================================
# Git Config Routes
# ========================================

@router.get("/projects/{project_id}/git-config")
async def get_git_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get Git configuration for a project."""
    service = EnvironmentService(db)
    config = service.get_git_config(project_id)
    
    if not config:
        return {"project_id": project_id, "git_config": None}
    
    return {
        "project_id": project_id,
        "git_config": {
            "id": config.id,
            "git_provider": config.git_provider.value,
            "repo_url": config.repo_url,
            "repo_name": config.repo_name,
            "default_branch": config.default_branch,
            "branch_strategy": config.branch_strategy.value,
            "auto_commit": config.auto_commit,
            "connection_status": config.connection_status.value,
            "last_connection_test": config.last_connection_test
        }
    }


@router.post("/projects/{project_id}/git-config")
async def create_git_config(
    project_id: int,
    data: GitConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create or update Git configuration for a project."""
    service = EnvironmentService(db)
    
    try:
        config = service.create_git_config(
            project_id=project_id,
            git_provider=data.git_provider,
            repo_url=data.repo_url,
            access_token=data.access_token,
            default_branch=data.default_branch,
            auto_commit=data.auto_commit,
            branch_strategy=data.branch_strategy
        )
        
        return {
            "success": True,
            "git_config": {
                "id": config.id,
                "repo_name": config.repo_name,
                "connection_status": config.connection_status.value
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/projects/{project_id}/git-config/test")
async def test_git_config(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test Git connection for a project."""
    service = EnvironmentService(db)
    result = service.test_git_connection(project_id)
    
    return result


# ========================================
# SDS Templates Routes
# ========================================

@router.get("/sds-templates")
async def get_sds_templates(
    db: Session = Depends(get_db),
    language: str = None
):
    """Get available SDS templates."""
    from app.models.sds_template import SDSTemplate
    
    query = db.query(SDSTemplate).filter(SDSTemplate.is_system == True)
    
    if language:
        query = query.filter(SDSTemplate.language == language)
    
    templates = query.all()
    
    return {
        "templates": [
            {
                "template_id": t.template_id,
                "name": t.name,
                "description": t.description,
                "language": t.language,
                "is_default": t.is_default,
                "sections": t.get_sections()
            }
            for t in templates
        ]
    }


@router.get("/sds-templates/{template_id}")
async def get_sds_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific SDS template."""
    from app.models.sds_template import SDSTemplate
    
    template = db.query(SDSTemplate).filter(
        SDSTemplate.template_id == template_id
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        "template_id": template.template_id,
        "name": template.name,
        "description": template.description,
        "language": template.language,
        "template_structure": template.template_structure,
        "primary_color": template.primary_color,
        "secondary_color": template.secondary_color,
        "font_family": template.font_family,
        "include_toc": template.include_toc,
        "include_cover_page": template.include_cover_page
    }
