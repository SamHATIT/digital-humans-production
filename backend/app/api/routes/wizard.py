"""
Wizard API Routes - Project Configuration Wizard
6-step wizard for creating and configuring projects.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models.project import Project, ProjectStatus, ProjectType, TargetObjective
from app.models.project_credential import ProjectCredential, CredentialType
from app.models.user import User
from app.api.routes.auth import get_current_user
# EnvironmentService handles encryption internally

router = APIRouter(prefix="/wizard", tags=["Wizard"])


# ========================================
# PYDANTIC SCHEMAS
# ========================================

class WizardStep1(BaseModel):
    """Step 1: Basic Information"""
    name: str
    description: Optional[str] = None
    project_code: Optional[str] = None
    client_name: Optional[str] = None
    client_contact_name: Optional[str] = None
    client_contact_email: Optional[EmailStr] = None
    client_contact_phone: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class WizardStep2(BaseModel):
    """Step 2: Project Type"""
    project_type: ProjectType
    salesforce_product: Optional[str] = None


class WizardStep3(BaseModel):
    """Step 3: Target Objective"""
    target_objective: TargetObjective


class WizardStep4(BaseModel):
    """Step 4: Salesforce Connection"""
    sf_instance_url: Optional[str] = None
    sf_username: Optional[str] = None
    sf_access_token: Optional[str] = None  # Will be encrypted


class WizardStep5(BaseModel):
    """Step 5: Git Repository"""
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = "main"
    git_token: Optional[str] = None  # Will be encrypted


class WizardStep6(BaseModel):
    """Step 6: Agent Configuration & Business Requirements"""
    business_requirements: str
    selected_sds_agents: Optional[List[str]] = ["qa", "devops", "data", "trainer"]
    existing_systems: Optional[str] = None
    compliance_requirements: Optional[str] = None
    expected_users: Optional[int] = None
    expected_data_volume: Optional[str] = None


class WizardProgressResponse(BaseModel):
    """Response showing wizard progress"""
    project_id: int
    project_name: str
    wizard_step: int
    wizard_completed: bool
    status: str


class ConnectionTestResult(BaseModel):
    """Result of connection test"""
    success: bool
    message: str
    details: Optional[dict] = None


# ========================================
# WIZARD ENDPOINTS
# ========================================

@router.post("/create", response_model=WizardProgressResponse)
async def create_wizard_project(
    data: WizardStep1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project and start the wizard.
    This creates the project with Step 1 data.
    """
    # Auto-generate project_code if not provided
    project_code = data.project_code
    if not project_code:
        from sqlalchemy import func
        max_id = db.query(func.max(Project.id)).scalar() or 0
        project_code = f"PRJ-{datetime.utcnow().strftime('%Y')}-{max_id + 1:03d}"

    project = Project(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        project_code=project_code,
        client_name=data.client_name,
        client_contact_name=data.client_contact_name,
        client_contact_email=data.client_contact_email,
        client_contact_phone=data.client_contact_phone,
        start_date=data.start_date,
        end_date=data.end_date,
        wizard_step=2,  # Move to step 2
        wizard_completed=False,
        status=ProjectStatus.DRAFT
    )
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return WizardProgressResponse(
        project_id=project.id,
        project_name=project.name,
        wizard_step=project.wizard_step,
        wizard_completed=project.wizard_completed,
        status=project.status.value
    )


@router.put("/{project_id}/step/1", response_model=WizardProgressResponse)
async def update_step1(
    project_id: int,
    data: WizardStep1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 1: Basic Information"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.name = data.name
    project.description = data.description
    project.project_code = data.project_code
    project.client_name = data.client_name
    project.client_contact_name = data.client_contact_name
    project.client_contact_email = data.client_contact_email
    project.client_contact_phone = data.client_contact_phone
    project.start_date = data.start_date
    project.end_date = data.end_date
    
    if project.wizard_step < 2:
        project.wizard_step = 2
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.put("/{project_id}/step/2", response_model=WizardProgressResponse)
async def update_step2(
    project_id: int,
    data: WizardStep2,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 2: Project Type"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.project_type = data.project_type
    project.salesforce_product = data.salesforce_product
    
    if project.wizard_step < 3:
        project.wizard_step = 3
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.put("/{project_id}/step/3", response_model=WizardProgressResponse)
async def update_step3(
    project_id: int,
    data: WizardStep3,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 3: Target Objective"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.target_objective = data.target_objective
    
    if project.wizard_step < 4:
        project.wizard_step = 4
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.put("/{project_id}/step/4", response_model=WizardProgressResponse)
async def update_step4(
    project_id: int,
    data: WizardStep4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 4: Salesforce Connection"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.sf_instance_url = data.sf_instance_url
    project.sf_username = data.sf_username
    
    # Store encrypted access token if provided
    if data.sf_access_token:
        _store_credential(
            db, project.id, 
            CredentialType.SALESFORCE_TOKEN, 
            data.sf_access_token,
            "Salesforce Access Token"
        )
        project.sf_connected = True
        project.sf_connection_date = datetime.utcnow()
    
    if project.wizard_step < 5:
        project.wizard_step = 5
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.put("/{project_id}/step/5", response_model=WizardProgressResponse)
async def update_step5(
    project_id: int,
    data: WizardStep5,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 5: Git Repository"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.git_repo_url = data.git_repo_url
    project.git_branch = data.git_branch or "main"
    
    # Store encrypted git token if provided
    if data.git_token:
        _store_credential(
            db, project.id,
            CredentialType.GIT_TOKEN,
            data.git_token,
            "Git Access Token"
        )
        project.git_connected = True
        project.git_connection_date = datetime.utcnow()
    
    if project.wizard_step < 6:
        project.wizard_step = 6
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.put("/{project_id}/step/6", response_model=WizardProgressResponse)
async def update_step6(
    project_id: int,
    data: WizardStep6,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update Step 6: Business Requirements & Complete Wizard"""
    project = _get_user_project(db, project_id, current_user.id)
    
    project.business_requirements = data.business_requirements
    project.selected_sds_agents = data.selected_sds_agents
    project.existing_systems = data.existing_systems
    project.compliance_requirements = data.compliance_requirements
    project.expected_users = data.expected_users
    project.expected_data_volume = data.expected_data_volume
    
    project.wizard_step = 6
    project.wizard_completed = True
    project.status = ProjectStatus.READY
    
    db.commit()
    db.refresh(project)
    
    return _wizard_response(project)


@router.get("/{project_id}/progress", response_model=WizardProgressResponse)
async def get_wizard_progress(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current wizard progress for a project."""
    project = _get_user_project(db, project_id, current_user.id)
    return _wizard_response(project)


@router.post("/{project_id}/test/salesforce", response_model=ConnectionTestResult)
async def test_salesforce_connection(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test Salesforce connection for a project."""
    from app.services.connection_validator import get_connection_validator
    
    project = _get_user_project(db, project_id, current_user.id)
    
    if not project.sf_instance_url:
        return ConnectionTestResult(
            success=False,
            message="No Salesforce instance URL configured"
        )
    
    # Get stored token
    token = _get_credential(db, project.id, CredentialType.SALESFORCE_TOKEN)
    if not token:
        return ConnectionTestResult(
            success=False,
            message="No Salesforce token stored"
        )
    
    # Real connection test
    validator = get_connection_validator()
    result = validator.test_salesforce_connection(
        instance_url=project.sf_instance_url,
        access_token=token,
        username=project.sf_username
    )
    
    # Update project connection status
    if result.success:
        project.sf_connected = True
        project.sf_connection_date = datetime.utcnow()
        if result.details and result.details.get("org_id"):
            project.sf_org_id = result.details["org_id"]
        db.commit()
    
    return ConnectionTestResult(
        success=result.success,
        message=result.message,
        details=result.details
    )


@router.post("/{project_id}/test/git", response_model=ConnectionTestResult)
async def test_git_connection(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Test Git connection for a project."""
    from app.services.connection_validator import get_connection_validator
    
    project = _get_user_project(db, project_id, current_user.id)
    
    if not project.git_repo_url:
        return ConnectionTestResult(
            success=False,
            message="No Git repository URL configured"
        )
    
    # Get stored token
    token = _get_credential(db, project.id, CredentialType.GIT_TOKEN)
    if not token:
        return ConnectionTestResult(
            success=False,
            message="No Git token stored"
        )
    
    # Real connection test
    validator = get_connection_validator()
    result = validator.test_git_connection(
        repo_url=project.git_repo_url,
        token=token,
        branch=project.git_branch or "main"
    )
    
    # Update project connection status
    if result.success:
        project.git_connected = True
        project.git_connection_date = datetime.utcnow()
        db.commit()
    
    return ConnectionTestResult(
        success=result.success,
        message=result.message,
        details=result.details
    )


# ========================================
# HELPER FUNCTIONS
# ========================================

def _get_user_project(db: Session, project_id: int, user_id: int) -> Project:
    """Get project and verify ownership."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()
    
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )
    
    return project


def _wizard_response(project: Project) -> WizardProgressResponse:
    """Build wizard progress response."""
    return WizardProgressResponse(
        project_id=project.id,
        project_name=project.name,
        wizard_step=project.wizard_step or 1,
        wizard_completed=project.wizard_completed or False,
        status=project.status.value
    )


def _store_credential(
    db: Session, 
    project_id: int, 
    cred_type: CredentialType, 
    value: str,
    label: str = None
):
    """Store an encrypted credential using EnvironmentService."""
    from app.services.environment_service import get_environment_service
    env_service = get_environment_service(db)
    env_service.store_credential(project_id, cred_type, value, label)


def _get_credential(db: Session, project_id: int, cred_type: CredentialType) -> Optional[str]:
    """Get and decrypt a credential using EnvironmentService."""
    from app.services.environment_service import get_environment_service
    env_service = get_environment_service(db)
    return env_service.get_credential(project_id, cred_type)
