"""
PM Orchestrator API routes for project definition and execution.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import asyncio
import json
from datetime import datetime
from jose import jwt, JWTError
from app.config import settings
import logging

logger = logging.getLogger(__name__)

from app.database import get_db
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.execution import Execution, ExecutionStatus
from app.schemas.project import Project as ProjectSchema, ProjectCreate, ProjectUpdate
from app.schemas.execution import (
    ExecutionCreate,
    Execution as ExecutionSchema,
    ExecutionStartResponse,
    ExecutionResultResponse,
    ExecutionProgress
)
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header
from app.services.pm_orchestrator_service import execute_agents_background

router = APIRouter(tags=["PM Orchestrator"])


# ==================== PROJECT DEFINITION ROUTES ====================

@router.post("/projects", response_model=ProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new project definition for PM Orchestrator.

    This endpoint allows users to define a Salesforce project with:
    - Project information (name, Salesforce product, organization type)
    - Business requirements (3-7 bullet points)
    - Technical constraints (existing systems, compliance, etc.)
    - Architecture preferences (optional)
    """
    project = Project(
        user_id=current_user.id,
        name=project_data.name,
        description=project_data.description,
        salesforce_product=project_data.salesforce_product,
        organization_type=project_data.organization_type,
        business_requirements=project_data.business_requirements,
        existing_systems=project_data.existing_systems,
        compliance_requirements=project_data.compliance_requirements,
        expected_users=project_data.expected_users,
        expected_data_volume=project_data.expected_data_volume,
        architecture_preferences=project_data.architecture_preferences,
        architecture_notes=project_data.architecture_notes,
        requirements_text=project_data.requirements_text,
        status=ProjectStatus.READY
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    return project


@router.get("/projects", response_model=List[ProjectSchema])
async def list_projects(
    skip: int = 0,
    limit: int = 50,
    status: ProjectStatus = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all projects for the current user.

    Optional filters:
    - status: Filter by project status (draft, ready, active, completed, archived)
    - skip/limit: Pagination
    """
    query = db.query(Project).filter(Project.user_id == current_user.id)

    if status:
        query = query.filter(Project.status == status)

    projects = query.order_by(Project.created_at.desc()).offset(skip).limit(limit).all()

    return projects


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get dashboard statistics for the current user.

    Returns:
    - Total projects count
    - Projects by status (draft, ready, active, completed, archived)
    - Active executions count
    - Completed executions count
    - Recent projects
    """
    from sqlalchemy import func

    # Total projects
    total_projects = db.query(func.count(Project.id)).filter(
        Project.user_id == current_user.id
    ).scalar()

    # Projects by status
    projects_by_status = {}
    for status in ProjectStatus:
        count = db.query(func.count(Project.id)).filter(
            Project.user_id == current_user.id,
            Project.status == status
        ).scalar()
        projects_by_status[status.value] = count

    # Active executions
    active_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING])
    ).scalar()

    # Completed executions
    completed_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status == ExecutionStatus.COMPLETED
    ).scalar()

    # Failed executions
    failed_executions = db.query(func.count(Execution.id)).filter(
        Execution.user_id == current_user.id,
        Execution.status == ExecutionStatus.FAILED
    ).scalar()

    # Recent projects (last 5)
    recent_projects = db.query(Project).filter(
        Project.user_id == current_user.id
    ).order_by(Project.created_at.desc()).limit(5).all()

    return {
        "total_projects": total_projects,
        "projects_by_status": projects_by_status,
        "active_executions": active_executions,
        "completed_executions": completed_executions,
        "failed_executions": failed_executions,
        "recent_projects": [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "salesforce_product": p.salesforce_product,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in recent_projects
        ]
    }


@router.get("/projects/{project_id}", response_model=ProjectSchema)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific project by ID.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    return project


@router.put("/projects/{project_id}", response_model=ProjectSchema)
async def update_project(
    project_id: int,
    project_data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a project definition.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Update only provided fields
    update_data = project_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)

    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a project.
    """
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    db.delete(project)
    db.commit()

    return None


# ==================== EXECUTION ROUTES ====================

@router.post("/execute", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_execution(
    execution_data: ExecutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Start execution of selected agents for a project.

    This endpoint:
    1. Validates the project exists and belongs to the user
    2. Validates PM agent is selected (required)
    3. Creates an execution record
    4. Starts background task to execute agents
    5. Returns execution_id to track progress

    The PM agent must always be included in selected_agents.
    """
    # Validate project exists
    project = db.query(Project).filter(
        Project.id == execution_data.project_id,
        Project.user_id == current_user.id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found"
        )

    # Validate PM agent is selected
    # Validate PM agent is selected (required for SDS generation)
    if 'pm' not in execution_data.selected_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product Manager (PM) agent is required and must be selected"
        )

    # Initialize agent execution status (exclude PM as it's not executed as regular agent)
    agent_execution_status = {
        agent_id: {
            "state": "waiting",
            "progress": 0,
            "message": "Waiting to start..."
        }
        for agent_id in execution_data.selected_agents if agent_id != 'pm'
    }

    # Create execution record
    execution = Execution(
        project_id=project.id,
        user_id=current_user.id,
        selected_agents=execution_data.selected_agents,
        agent_execution_status=agent_execution_status,
        status=ExecutionStatus.RUNNING,
        started_at=datetime.utcnow()
    )

    db.add(execution)
    db.commit()
    db.refresh(execution)

    # Start background task for execution
    asyncio.create_task(execute_agents_background(execution.id, project.id, execution_data.selected_agents))

    return ExecutionStartResponse(
        execution_id=execution.id,
        status="started",
        message="Execution started successfully. Use the progress endpoint to track status."
    )


@router.get("/execute/{execution_id}/progress")
async def get_execution_progress(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Get current progress of an execution.
    """
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    return {
        "execution_id": execution.id,
        "project_id": execution.project_id,
        "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "progress": execution.progress or 0,
        "current_agent": execution.current_agent,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None
    }


@router.get("/execute/{execution_id}/result", response_model=ExecutionResultResponse)
async def get_execution_result(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get final execution result including SDS document information.

    This endpoint should be called after execution completes.
    """
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    if execution.status != ExecutionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution not yet completed. Current status: {execution.status.value}"
        )

    return ExecutionResultResponse(
        execution_id=execution.id,
        status=execution.status,
        sds_document_url=f"/api/pm-orchestrator/execute/{execution.id}/download" if execution.sds_document_path else None,
        execution_time=execution.duration_seconds,
        agents_used=len(execution.selected_agents) if execution.selected_agents else 0,
        total_cost=execution.total_cost,
        completed_at=execution.completed_at
    )


@router.get("/execute/{execution_id}/download")
async def download_sds_document(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Download the generated SDS document.
    """
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )

    if not execution.sds_document_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="SDS document not available"
        )

    # Get project name for filename
    project = db.query(Project).filter(Project.id == execution.project_id).first()
    filename = f"SDS_{project.name.replace(' ', '_')}_{execution.id}.docx"

    return FileResponse(
        path=execution.sds_document_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/executions", response_model=List[ExecutionSchema])
async def list_executions(
    project_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get execution history for the current user.

    Optional filters:
    - project_id: Filter by specific project
    - skip/limit: Pagination
    """
    query = db.query(Execution).filter(Execution.user_id == current_user.id)

    if project_id:
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
        query = query.filter(Execution.project_id == project_id)

    executions = query.order_by(Execution.created_at.desc()).offset(skip).limit(limit).all()

    return executions


# ==================== AGENTS LIST ENDPOINT ====================

@router.get("/agents")
async def list_available_agents(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all available Salesforce agents with their metadata.

    Returns:
    - id: Agent unique identifier
    - name: Agent display name (e.g., "Olivia (Business Analyst)")
    - description: What the agent does
    - required: Whether the agent is mandatory
    - available: Whether the agent file exists on the server
    - order: Execution order
    - avatar: Path to agent avatar image
    - estimatedTime: Estimated execution time in minutes
    """
    from app.services.agent_integration import AgentIntegrationService
    
    agent_service = AgentIntegrationService()
    agents = agent_service.get_available_agents()
    
    return {"agents": agents}


# ==================== DETAILED PROGRESS ENDPOINT ====================

@router.get("/execute/{execution_id}/detailed-progress")
async def get_detailed_execution_progress(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Get detailed progress with agent tasks breakdown.
    
    Returns:
    - execution_id
    - status (running, completed, failed)
    - tasks: Liste des tâches avec statut (completed, running, waiting)
    - current_task: Tâche en cours
    - sds_document_path: Chemin du document SDS si disponible
    """
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Récupérer les deliverables pour connaître les agents terminés
    from app.models.agent_deliverable import AgentDeliverable
    deliverables = db.query(AgentDeliverable).filter(
        AgentDeliverable.execution_id == execution_id
    ).all()
    
    completed_agent_types = {d.deliverable_type for d in deliverables if d.deliverable_type}
    
    # Mapping des agents vers leurs deliverable_type
    agent_to_type = {
        'ba': 'business_analyst_specification',
        'architect': 'solution_architect_specification',
        'apex': 'apex_developer_code',
        'lwc': 'lwc_developer_code',
        'admin': 'admin_configuration',
        'qa': 'qa_test_plan',
        'devops': 'devops_setup',
        'data': 'data_migration_plan',
        'trainer': 'training_documentation',
    }
    
    # Construire liste des tâches
    tasks = [
        {"order": 1, "name": "Business Analysis & Requirements", "agent": "ba", "status": "completed" if agent_to_type['ba'] in completed_agent_types else "waiting"},
        {"order": 2, "name": "Solution Architecture Design", "agent": "architect", "status": "completed" if agent_to_type['architect'] in completed_agent_types else "waiting"},
        {"order": 3, "name": "Apex Development (Triggers & Classes)", "agent": "apex", "status": "completed" if agent_to_type['apex'] in completed_agent_types else "waiting"},
        {"order": 4, "name": "LWC Development (Components)", "agent": "lwc", "status": "completed" if agent_to_type['lwc'] in completed_agent_types else "waiting"},
        {"order": 5, "name": "Admin Configuration (Flows & Rules)", "agent": "admin", "status": "completed" if agent_to_type['admin'] in completed_agent_types else "waiting"},
        {"order": 6, "name": "Quality Assurance & Testing", "agent": "qa", "status": "completed" if agent_to_type['qa'] in completed_agent_types else "waiting"},
        {"order": 7, "name": "DevOps Setup & CI/CD", "agent": "devops", "status": "completed" if agent_to_type['devops'] in completed_agent_types else "waiting"},
        {"order": 8, "name": "Data Migration Strategy", "agent": "data", "status": "completed" if agent_to_type['data'] in completed_agent_types else "waiting"},
        {"order": 9, "name": "Training & Documentation", "agent": "trainer", "status": "completed" if agent_to_type['trainer'] in completed_agent_types else "waiting"},
        {"order": 10, "name": "PM Consolidation & SDS Generation", "agent": "pm", "status": "completed" if execution.sds_document_path else "waiting"},
    ]
    
    # Déterminer tâche en cours
    current_task_index = len([t for t in tasks if t["status"] == "completed"])
    if current_task_index < len(tasks) and execution.status == ExecutionStatus.RUNNING:
        tasks[current_task_index]["status"] = "running"
    
    return {
        "execution_id": execution_id,
        "project_id": execution.project_id,
        "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "tasks": tasks,
        "current_task": next((t for t in tasks if t["status"] == "running"), None),
        "sds_document_path": execution.sds_document_path
    }


# ==================== CHAT WITH PM ENDPOINT ====================

@router.post("/chat/{execution_id}")
async def chat_with_pm(
    execution_id: int,
    chat_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send a message to Sophie (PM Orchestrator) for questions about the execution.
    
    Body:
    - message: User's question/message
    
    Returns:
    - execution_id
    - user_message: Original message
    - pm_response: Sophie's response
    """
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    user_message = chat_data.get("message", "").strip()
    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required"
        )
    
    # Pour l'instant, réponse simple
    # TODO: Intégrer OpenAI pour réponses intelligentes basées sur le contexte du projet
    pm_response = (
        f"Hello! I'm Sophie, your PM Orchestrator. "
        f"Your execution (#{execution_id}) is currently in '{execution.status}' status. "
        f"How can I help you with your project?"
    )
    
    return {
        "execution_id": execution_id,
        "user_message": user_message,
        "pm_response": pm_response
    }


# ==================== WEBSOCKET ROUTES ====================

from fastapi import WebSocket, WebSocketDisconnect
from jose import jwt, JWTError
from app.config import settings

@router.websocket("/ws/{execution_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    execution_id: int,
    token: str = Query(None)
):
    """
    WebSocket endpoint for real-time execution progress updates.
    
    Clients connect with: ws://host/api/pm-orchestrator/ws/{execution_id}?token=JWT
    
    Messages sent to client:
    - type: 'progress' - Execution progress update
    - type: 'log' - New log entry
    - type: 'completed' - Execution completed
    - type: 'error' - Execution error
    """
    # Authenticate via JWT token from query param
    if not token:
        await websocket.close(code=1008, reason="Missing authentication token")
        return
    
    try:
        # Verify JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except JWTError:
        await websocket.close(code=1008, reason="Invalid token")
        return
    
    # Accept WebSocket connection
    await websocket.accept()
    
    try:
        # Get database session
        db = next(get_db())
        
        # Verify execution exists and belongs to user
        execution = db.query(Execution).join(Project).filter(
            Execution.id == execution_id,
            Project.user_id == int(user_id)
        ).first()
        
        if not execution:
            await websocket.send_json({
                "type": "error",
                "data": {"error": "Execution not found"}
            })
            await websocket.close()
            return
        
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "data": {
                "execution_id": execution_id,
                "status": execution.status.value
            }
        })
        
        # Poll and push updates
        last_status = execution.status
        last_agent = execution.current_agent
        
        while True:
            try:
                # Refresh execution from DB
                db.refresh(execution)
                
                # Check if status changed
                if execution.status != last_status or execution.current_agent != last_agent:
                    # Send progress update
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "execution_id": execution_id,
                            "status": execution.status.value,
                            "progress": execution.progress or 0,
                            "current_agent": execution.current_agent,
                            "agent_execution_status": execution.agent_execution_status,
                            "message": f"Agent {execution.current_agent} is running..." if execution.current_agent else None
                        }
                    })
                    
                    last_status = execution.status
                    last_agent = execution.current_agent
                
                # If execution completed or failed, send final message and close
                if execution.status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED]:
                    await websocket.send_json({
                        "type": "completed" if execution.status == ExecutionStatus.COMPLETED else "error",
                        "data": {
                            "execution_id": execution_id,
                            "status": execution.status.value,
                            "progress": 100 if execution.status == ExecutionStatus.COMPLETED else execution.progress,
                            "sds_document_path": execution.sds_document_path
                        }
                    })
                    break
                
                # Wait before next poll (3 seconds)
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {str(e)}")
                await websocket.send_json({
                    "type": "error",
                    "data": {"error": "Internal server error"}
                })
                break
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for execution {execution_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"error": str(e)}
            })
        except:
            pass
    
    finally:
        try:
            await websocket.close()
        except:
            pass
