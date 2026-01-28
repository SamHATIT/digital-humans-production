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
    
    # Connection status
    sf_connected: Optional[bool] = False
    sf_instance_url: Optional[str] = None
    sf_username: Optional[str] = None
    git_connected: Optional[bool] = False
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    
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
        sf_connected=project.sf_connected or False,
        sf_instance_url=project.sf_instance_url,
        sf_username=project.sf_username,
        git_connected=project.git_connected or False,
        git_repo_url=project.git_repo_url,
        git_branch=project.git_branch,
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




# ==================== PROJECT SETTINGS ====================

@router.get("/{project_id}/settings")
async def get_project_settings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Get project settings (Git and Salesforce configuration)"""
    from app.models.project_credential import ProjectCredential, CredentialType
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Get OAuth credentials if stored
    oauth_cred = db.query(ProjectCredential).filter(
        ProjectCredential.project_id == project_id,
        ProjectCredential.credential_type == CredentialType.SALESFORCE_TOKEN
    ).first()
    
    # Determine auth method from stored data
    sf_auth_method = None
    if project.sf_connected:
        # Check if we have OAuth credentials
        if oauth_cred and oauth_cred.label:  # consumer_key stored in label
            sf_auth_method = 'oauth'
        else:
            sf_auth_method = 'sfdx'
    
    return {
        "sf_instance_url": project.sf_instance_url or "",
        "sf_username": project.sf_username or "",
        "sf_consumer_key": oauth_cred.label if oauth_cred else "",
        "sf_connected": project.sf_connected or False,
        "sf_connection_date": project.sf_connection_date.isoformat() if project.sf_connection_date else None,
        "sf_auth_method": sf_auth_method,
        "git_repo_url": project.git_repo_url or "",
        "git_branch": project.git_branch or "main",
        "git_connected": project.git_connected or False,
        "git_connection_date": project.git_connection_date.isoformat() if project.git_connection_date else None,
    }


@router.put("/{project_id}/settings")
async def update_project_settings(
    project_id: int,
    settings: Dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Update project settings"""
    from app.models.project_credential import ProjectCredential, CredentialType
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Update basic Salesforce settings
    if "sf_instance_url" in settings:
        project.sf_instance_url = settings["sf_instance_url"]
    if "sf_username" in settings:
        project.sf_username = settings["sf_username"]
    
    # Store OAuth credentials if provided
    if settings.get("sf_consumer_key") or settings.get("sf_consumer_secret"):
        existing = db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == CredentialType.SALESFORCE_TOKEN
        ).first()
        
        if existing:
            if settings.get("sf_consumer_key"):
                existing.label = settings["sf_consumer_key"]
            if settings.get("sf_consumer_secret"):
                existing.encrypted_value = settings["sf_consumer_secret"]
            existing.updated_at = datetime.utcnow()
        else:
            if settings.get("sf_consumer_key") and settings.get("sf_consumer_secret"):
                cred = ProjectCredential(
                    project_id=project_id,
                    credential_type=CredentialType.SALESFORCE_TOKEN,
                    label=settings["sf_consumer_key"],
                    encrypted_value=settings["sf_consumer_secret"],
                )
                db.add(cred)
    
    # Update Git settings
    if "git_repo_url" in settings:
        project.git_repo_url = settings["git_repo_url"]
    if "git_branch" in settings:
        project.git_branch = settings["git_branch"]
    if settings.get("git_token"):
        existing = db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == CredentialType.GIT_TOKEN
        ).first()
        if existing:
            existing.encrypted_value = settings["git_token"]
            existing.updated_at = datetime.utcnow()
        else:
            cred = ProjectCredential(
                project_id=project_id,
                credential_type=CredentialType.GIT_TOKEN,
                encrypted_value=settings["git_token"],
                label="Git Personal Access Token"
            )
            db.add(cred)
    
    db.commit()
    db.refresh(project)
    
    return {"success": True, "message": "Settings updated successfully"}


@router.post("/{project_id}/test-salesforce")
async def test_salesforce_connection(
    project_id: int,
    body: Dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Test Salesforce connection using SFDX or OAuth"""
    import httpx
    from app.services.sfdx_auth_service import sfdx_auth
    from app.models.project_credential import ProjectCredential, CredentialType
    
    body = body or {}
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    auth_method = body.get("auth_method", "sfdx")
    
    if auth_method == "sfdx":
        # Use SFDX CLI authentication
        username = project.sf_username
        if not username:
            return {"success": False, "message": "Please enter a Salesforce username"}
        
        result = sfdx_auth.test_connection(username)
        
        if result.get("success"):
            project.sf_connected = True
            project.sf_connection_date = datetime.utcnow()
            if result.get("org_id"):
                project.sf_org_id = result["org_id"]
            if result.get("instance_url"):
                project.sf_instance_url = result["instance_url"]
            db.commit()
            return {"success": True, "message": f"Connected via SFDX to {username}"}
        else:
            return {
                "success": False, 
                "message": result.get("message", "SFDX authentication failed. Run 'sfdx auth:web:login' on the server first.")
            }
    
    else:  # OAuth method
        instance_url = project.sf_instance_url
        
        # Get OAuth credentials
        cred = db.query(ProjectCredential).filter(
            ProjectCredential.project_id == project_id,
            ProjectCredential.credential_type == CredentialType.SALESFORCE_TOKEN
        ).first()
        
        if not cred or not cred.label or not cred.encrypted_value:
            return {"success": False, "message": "Please enter Consumer Key and Consumer Secret"}
        
        consumer_key = cred.label
        consumer_secret = cred.encrypted_value
        
        if not instance_url:
            return {"success": False, "message": "Please enter the Salesforce Instance URL"}
        
        try:
            # Clean up instance URL
            api_url = instance_url.strip().rstrip('/')
            
            # Determine login URL
            if '.sandbox.my.salesforce.com' in api_url or '--' in api_url:
                login_url = "https://test.salesforce.com"
            else:
                login_url = "https://login.salesforce.com"
            
            async with httpx.AsyncClient() as client:
                # OAuth 2.0 Client Credentials Flow
                token_response = await client.post(
                    f"{login_url}/services/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": consumer_key,
                        "client_secret": consumer_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )
                
                if token_response.status_code == 200:
                    token_data = token_response.json()
                    access_token = token_data.get("access_token")
                    
                    # Test the token
                    test_response = await client.get(
                        f"{api_url}/services/data/v59.0/",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=30.0
                    )
                    
                    if test_response.status_code == 200:
                        project.sf_connected = True
                        project.sf_connection_date = datetime.utcnow()
                        db.commit()
                        return {"success": True, "message": "Connected via OAuth!"}
                    else:
                        return {"success": False, "message": f"API test failed: {test_response.status_code}"}
                else:
                    error_data = token_response.json() if 'json' in token_response.headers.get('content-type', '') else {}
                    error_msg = error_data.get('error_description', token_response.text[:200])
                    return {"success": False, "message": f"OAuth failed: {error_msg}"}
                    
        except httpx.TimeoutException:
            return {"success": False, "message": "Connection timeout. Check instance URL."}
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}


@router.post("/{project_id}/test-git")
async def test_git_connection(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict:
    """Test Git repository connection"""
    import httpx
    import re
    from app.models.project_credential import ProjectCredential, CredentialType
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    repo_url = project.git_repo_url
    
    cred = db.query(ProjectCredential).filter(
        ProjectCredential.project_id == project_id,
        ProjectCredential.credential_type == CredentialType.GIT_TOKEN
    ).first()
    git_token = cred.encrypted_value if cred else None
    
    if not repo_url:
        return {"success": False, "message": "Please enter a repository URL"}
    if not git_token:
        return {"success": False, "message": "Please enter a Personal Access Token"}
    
    try:
        match = re.match(r'https://github\.com/([^/]+)/([^/\.]+)', repo_url)
        if not match:
            return {"success": False, "message": "Only GitHub URLs are supported currently"}
        
        owner, repo = match.groups()
        
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {git_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            response = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                repo_data = response.json()
                project.git_connected = True
                project.git_connection_date = datetime.utcnow()
                db.commit()
                return {
                    "success": True, 
                    "message": f"Connected to {repo_data['full_name']}",
                }
            elif response.status_code == 401:
                return {"success": False, "message": "Authentication failed. Check your token."}
            elif response.status_code == 404:
                return {"success": False, "message": "Repository not found. Check URL and permissions."}
            else:
                return {"success": False, "message": f"Connection failed: {response.status_code}"}
                
    except httpx.TimeoutException:
        return {"success": False, "message": "Connection timeout."}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)}"}
