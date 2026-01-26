"""
PM Orchestrator API routes for project definition and execution.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect, Request, Response
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
from app.services.pm_orchestrator_service_v2 import execute_workflow_background
from app.rate_limiter import limiter, RateLimits

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
@limiter.limit(RateLimits.EXECUTE_SDS)
async def start_execution(
    request: Request,
    response: Response,
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
    asyncio.create_task(execute_workflow_background(db, execution.id, project.id, execution_data.selected_agents))

    return ExecutionStartResponse(
        execution_id=execution.id,
        status="started",
        message="Execution started successfully. Use the progress endpoint to track status."
    )



@router.post("/execute/{execution_id}/resume", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def resume_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resume execution after Business Requirements validation.
    
    This endpoint:
    1. Validates the execution is in WAITING_BR_VALIDATION status
    2. Resets status to RUNNING
    3. Starts background task to continue from Phase 2 (Olivia BA)
    """
    # Get execution
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Validate status - allow resume from WAITING_BR_VALIDATION or FAILED
    if execution.status not in [ExecutionStatus.WAITING_BR_VALIDATION, ExecutionStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume execution. Status must be WAITING_BR_VALIDATION or FAILED. Current: {execution.status.value}"
        )
    
    # Determine resume point
    # Note: The workflow only supports resuming from Phase 2 (after BR validation)
    # More granular resume (from arbitrary phases) would require workflow refactoring
    resume_point = None
    
    if execution.status == ExecutionStatus.WAITING_BR_VALIDATION:
        # Standard case: BRs validated, continue to Phase 2
        resume_point = "phase2_ba"
    elif execution.status == ExecutionStatus.FAILED:
        # For FAILED executions, we can only resume if BRs are already validated
        from app.models.business_requirement import BusinessRequirement, BRStatus
        validated_brs = db.query(BusinessRequirement).filter(
            BusinessRequirement.project_id == execution.project_id,
            BusinessRequirement.status == BRStatus.VALIDATED
        ).count()
        
        if validated_brs > 0:
            # BRs exist and are validated, resume from Phase 2
            resume_point = "phase2_ba"
            logger.info(f"Resuming FAILED execution {execution_id} with {validated_brs} validated BRs")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot resume: no validated Business Requirements found. Please validate BRs first or start a new execution."
            )
    
    if not resume_point:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine resume point. Execution must be in WAITING_BR_VALIDATION or FAILED status with validated BRs."
        )
    
    # Update status
    execution.status = ExecutionStatus.RUNNING
    db.commit()
    
    # Resume from detected checkpoint
    asyncio.create_task(
        execute_workflow_background(
            db, 
            execution.id, 
            execution.project_id, 
            execution.selected_agents,
            resume_from=resume_point
        )
    )
    
    return ExecutionStartResponse(
        execution_id=execution.id,
        status="resumed",
        message=f"Execution resumed from {resume_point}. Use the progress endpoint to track status."
    )

@router.get("/execute/{execution_id}/progress")
async def get_execution_progress(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Get current progress of an execution.
    Returns format compatible with frontend ExecutionProgress interface.
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

    # Parse agent_execution_status JSON
    agent_status = {}
    if execution.agent_execution_status:
        if isinstance(execution.agent_execution_status, str):
            agent_status = json.loads(execution.agent_execution_status)
        else:
            agent_status = execution.agent_execution_status

    # Build agent_progress array for frontend
    agent_progress = []
    selected_agents = execution.selected_agents or []
    if isinstance(selected_agents, str):
        selected_agents = json.loads(selected_agents)
    
    # Agent display names mapping
    agent_names = {
        "pm": "Sophie (PM)",
        "ba": "Olivia (BA)",
        "research_analyst": "Emma (Research Analyst)",
        "architect": "Marcus (Architect)",
        "apex": "Diego (Apex)",
        "lwc": "Zara (LWC)",
        "admin": "Raj (Admin)",
        "qa": "Elena (QA)",
        "devops": "Jordan (DevOps)",
        "data": "Aisha (Data)",
        "trainer": "Lucas (Trainer)"
    }
    
    for agent_id in selected_agents:
        status_info = agent_status.get(agent_id, {})
        state = status_info.get("state", "waiting")
        
        # Map state to frontend expected status
        status_map = {
            "waiting": "pending",
            "running": "in_progress",
            "completed": "completed",
            "failed": "failed"
        }
        
        agent_progress.append({
            "agent_name": agent_names.get(agent_id, agent_id),
            "status": status_map.get(state, state),
            "progress": status_info.get("progress", 0),
            "current_task": status_info.get("message", ""),
            "output_summary": status_info.get("message", "")
        })

    # Calculate overall progress based on completed agents
    total_agents = len(selected_agents)
    completed_agents = sum(1 for a in agent_status.values() if a.get("state") == "completed")
    overall_progress = int((completed_agents / total_agents) * 100) if total_agents > 0 else 0

    # Determine current phase
    current_phase = "Initializing..."
    if execution.current_agent:
        current_phase = f"Running {agent_names.get(execution.current_agent, execution.current_agent)}"
    if execution.status == ExecutionStatus.COMPLETED:
        current_phase = "Completed"
        overall_progress = 100
    elif execution.status == ExecutionStatus.FAILED:
        current_phase = "Failed"
    elif execution.status == ExecutionStatus.WAITING_BR_VALIDATION:
        current_phase = "Waiting for BR Validation"

    return {
        "execution_id": execution.id,
        "project_id": execution.project_id,
        "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "overall_progress": overall_progress,
        "current_phase": current_phase,
        "agent_progress": agent_progress,
        "sds_document_path": execution.sds_document_path
    }

# FRNT-04: SSE endpoint for real-time progress updates
# PERF-001: Uses PostgreSQL NOTIFY for instant updates with polling fallback
@router.get("/execute/{execution_id}/progress/stream")
async def stream_execution_progress(
    execution_id: int,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db)
):
    """
    Stream execution progress updates via Server-Sent Events (SSE).
    
    Uses PostgreSQL LISTEN/NOTIFY for instant updates, with polling fallback.
    Connect with: const eventSource = new EventSource(`/api/pm-orchestrator/execute/{id}/progress/stream?token={jwt}`)
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    
    # Validate token
    try:
        from app.services.auth_service import verify_token
        payload = verify_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
    
    # Verify execution access
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == int(user_id)
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Try to use notifications, fallback to polling
    try:
        from app.services.notification_service import get_notification_service
        notification_service = await get_notification_service()
        use_notifications = True
    except Exception as e:
        logger.debug(f"Notifications unavailable, using polling: {e}")
        use_notifications = False
        notification_service = None
    
    async def event_generator():
        """Generate SSE events for progress updates"""
        last_status = None
        last_progress = -1
        max_duration = 600  # 10 minutes max
        start_time = asyncio.get_event_loop().time()
        poll_interval = 3 if use_notifications else 2  # Longer interval when using notifications
        
        # Helper to build progress data
        def build_progress_data():
            db.refresh(execution)
            agent_status = {}
            if execution.agent_execution_status:
                if isinstance(execution.agent_execution_status, str):
                    agent_status = json.loads(execution.agent_execution_status)
                else:
                    agent_status = execution.agent_execution_status
            
            selected_agents = execution.selected_agents or []
            if isinstance(selected_agents, str):
                selected_agents = json.loads(selected_agents)
            
            agent_names = {
                "pm": "Sophie (PM)", "ba": "Olivia (BA)", "research_analyst": "Emma (Research Analyst)",
                "architect": "Marcus (Architect)", "apex": "Diego (Apex)", "lwc": "Zara (LWC)",
                "admin": "Raj (Admin)", "qa": "Elena (QA)", "devops": "Jordan (DevOps)",
                "data": "Aisha (Data)", "trainer": "Lucas (Trainer)"
            }
            
            agent_progress = []
            for agent_id in selected_agents:
                info = agent_status.get(agent_id, {})
                state = info.get("state", "waiting")
                status_map = {"waiting": "pending", "running": "in_progress", "completed": "completed", "failed": "failed"}
                agent_progress.append({
                    "agent_name": agent_names.get(agent_id, agent_id),
                    "status": status_map.get(state, state),
                    "progress": info.get("progress", 0),
                    "current_task": info.get("message", ""),
                    "output_summary": info.get("message", "")
                })
            
            total = len(selected_agents)
            completed = sum(1 for a in agent_status.values() if a.get("state") == "completed")
            overall = int((completed / total) * 100) if total > 0 else 0
            current_status = execution.status.value if hasattr(execution.status, "value") else str(execution.status)
            
            return {
                "execution_id": execution.id,
                "status": current_status,
                "overall_progress": overall,
                "current_phase": f"Running {agent_names.get(execution.current_agent, execution.current_agent)}" if execution.current_agent else "Processing...",
                "agent_progress": agent_progress
            }, current_status, overall
        
        if use_notifications and notification_service:
            # PERF-001: Event-driven mode with notifications
            channel = f"execution_{execution_id}"
            try:
                async with notification_service.subscribe(channel) as queue:
                    while (asyncio.get_event_loop().time() - start_time) < max_duration:
                        try:
                            # Wait for notification or timeout
                            try:
                                notification = await asyncio.wait_for(queue.get(), timeout=poll_interval)
                                logger.debug(f"SSE: Received notification for execution {execution_id}")
                            except asyncio.TimeoutError:
                                notification = None
                            
                            # Build and send progress data
                            data, current_status, overall = build_progress_data()
                            
                            if current_status != last_status or overall != last_progress:
                                yield f"data: {json.dumps(data)}\n\n"
                                last_status = current_status
                                last_progress = overall
                            
                            if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                                yield f"data: {json.dumps({'event': 'close', 'status': current_status})}\n\n"
                                return
                                
                        except Exception as e:
                            logger.error(f"SSE notification error: {e}")
                            break
            except Exception as e:
                logger.warning(f"SSE notification subscription failed, falling back to polling: {e}")
                use_notifications = False
        
        # Polling fallback (or primary if notifications unavailable)
        if not use_notifications:
            while (asyncio.get_event_loop().time() - start_time) < max_duration:
                try:
                    data, current_status, overall = build_progress_data()
                    
                    if current_status != last_status or overall != last_progress:
                        yield f"data: {json.dumps(data)}\n\n"
                        last_status = current_status
                        last_progress = overall
                    
                    if current_status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        yield f"data: {json.dumps({'event': 'close', 'status': current_status})}\n\n"
                        return
                    
                    await asyncio.sleep(poll_interval)
                    
                except Exception as e:
                    yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
                    return
        
        yield f"data: {json.dumps({'event': 'timeout'})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )




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


# ==================== BUILD TASKS MONITORING ====================

@router.get("/execute/{execution_id}/build-tasks")
async def get_build_tasks(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Get all BUILD phase tasks with their execution status.
    Used by BuildMonitoringPage to display task progress.
    """
    from app.models.task_execution import TaskExecution, TaskStatus
    
    # Verify execution access
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Get all task executions
    tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id
    ).order_by(TaskExecution.task_id).all()
    
    # Group by agent
    tasks_by_agent = {}
    for task in tasks:
        agent = task.assigned_agent or "unassigned"
        if agent not in tasks_by_agent:
            tasks_by_agent[agent] = []
        tasks_by_agent[agent].append({
            "task_id": task.task_id,
            "task_name": task.task_name,
            "phase_name": task.phase_name,
            "status": task.status.value if hasattr(task.status, "value") else str(task.status),
            "attempt_count": task.attempt_count,
            "last_error": task.last_error,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "git_commit_sha": task.git_commit_sha,
        })
    
    # Stats
    total = len(tasks)
    completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED or t.status == TaskStatus.PASSED])
    running = len([t for t in tasks if t.status == TaskStatus.RUNNING])
    failed = len([t for t in tasks if t.status == TaskStatus.FAILED])
    pending = len([t for t in tasks if t.status == TaskStatus.PENDING])
    
    return {
        "execution_id": execution_id,
        "execution_status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "build_phase": {
            "total_tasks": total,
            "completed": completed,
            "running": running,
            "failed": failed,
            "pending": pending,
            "progress_percent": int((completed / total) * 100) if total > 0 else 0
        },
        "tasks_by_agent": tasks_by_agent,
        "all_tasks": [{
            "task_id": t.task_id,
            "task_name": t.task_name,
            "phase_name": t.phase_name,
            "assigned_agent": t.assigned_agent,
            "status": t.status.value if hasattr(t.status, "value") else str(t.status),
            "attempt_count": t.attempt_count,
            "last_error": t.last_error,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        } for t in tasks]
    }



# ==================== START BUILD PHASE ====================

@router.post("/projects/{project_id}/start-build")
@limiter.limit(RateLimits.EXECUTE_BUILD)
async def start_build_phase(
    request: Request,
    response: Response,
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header)
):
    """
    Start the BUILD phase for a project after SDS approval.
    Creates TaskExecution entries from WBS and starts execution.
    """
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService
    
    # Use BuildPhaseService for business logic
    service = BuildPhaseService(db)
    result = service.prepare_build_phase(project_id, current_user.id)
    
    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))
    
    # Start BUILD execution in background
    asyncio.create_task(safe_execute_build_phase(result["execution_id"]))
    
    return {
        "message": f"BUILD phase started with {result['tasks_created']} tasks",
        "execution_id": result["execution_id"],
        "project_id": project_id,
        "tasks_created": result["tasks_created"]
    }


# OLD CODE REMOVED - Logic moved to BuildPhaseService
# The following was replaced:
# - Project verification
# - Execution retrieval
# - WBS parsing (complex nested structure handling)
# - TaskExecution creation
# - Status updates
# All this logic is now in BuildPhaseService.prepare_build_phase()

_OLD_START_BUILD_REMOVED = True  # Marker for refactoring


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
                
                # PERF-001: Increased poll interval (notifications reduce need for frequent polling)
                await asyncio.sleep(5)  # Reduced from 3s - notifications handle instant updates
                
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


# ORCH-04: Retry failed execution
@router.post("/execute/{execution_id}/retry", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_failed_execution(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retry a failed execution from the last stable point.
    
    ORCH-04: This endpoint:
    1. Validates the execution is in FAILED status
    2. Identifies the last completed phase/task
    3. Resets status to RUNNING
    4. Starts background task to continue from failure point
    """
    from app.models.task_execution import TaskExecution, TaskStatus
    
    # Get execution
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found"
        )
    
    # Validate status - allow FAILED or CANCELLED
    if execution.status not in [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution cannot be retried. Current status: {execution.status.value}. Only failed/cancelled executions can be retried."
        )
    
    # Check for task-level failures (Build phase)
    failed_tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id,
        TaskExecution.status == TaskStatus.FAILED
    ).all()
    
    # Determine resume point based on agent_execution_status
    agent_status = execution.agent_execution_status or {}
    resume_from = "phase1"  # Default to start
    
    # Find last completed phase
    phase_order = ["pm", "ba", "architect", "data", "trainer", "qa", "devops"]
    for agent_id in reversed(phase_order):
        if agent_id in agent_status:
            status_info = agent_status[agent_id]
            if status_info.get("state") == "completed":
                # Resume from next phase
                idx = phase_order.index(agent_id)
                if idx < len(phase_order) - 1:
                    resume_from = f"phase_{phase_order[idx + 1]}"
                break
    
    # If we have task-level tracking, use that instead
    if failed_tasks:
        # Reset failed tasks to pending for retry
        for task in failed_tasks:
            task.status = TaskStatus.PENDING
            task.attempt_count = 0
            task.last_error = None
            task.error_log = None
        db.commit()
        resume_from = "build_tasks"
    
    # Update execution status
    execution.status = ExecutionStatus.RUNNING
    db.commit()
    
    # Resume execution
    asyncio.create_task(
        execute_workflow_background(
            db,
            execution.id,
            execution.project_id,
            execution.selected_agents,
            resume_from=resume_from
        )
    )
    
    return ExecutionStartResponse(
        execution_id=execution.id,
        status="retrying",
        message=f"Execution retrying from {resume_from}. {len(failed_tasks)} failed tasks reset."
    )


# ORCH-04: Get retry status and options
@router.get("/execute/{execution_id}/retry-info")
async def get_retry_info(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get information about retry options for a failed execution.
    
    Returns:
    - Can retry: bool
    - Resume point: where execution would resume from
    - Failed tasks: list of failed task IDs
    - Completed tasks: list of completed task IDs
    """
    from app.models.task_execution import TaskExecution, TaskStatus
    
    execution = db.query(Execution).join(Project).filter(
        Execution.id == execution_id,
        Project.user_id == current_user.id
    ).first()
    
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Get task-level info
    task_summary = {"completed": [], "failed": [], "pending": [], "blocked": []}
    
    tasks = db.query(TaskExecution).filter(
        TaskExecution.execution_id == execution_id
    ).all()
    
    for task in tasks:
        status_key = task.status.value if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING, TaskStatus.BLOCKED] else "other"
        if status_key in task_summary:
            task_summary[status_key].append({
                "task_id": task.task_id,
                "name": task.task_name,
                "agent": task.assigned_agent,
                "attempts": task.attempt_count,
                "last_error": task.last_error
            })
    
    # Determine resume point
    agent_status = execution.agent_execution_status or {}
    completed_phases = [k for k, v in agent_status.items() if v.get("state") == "completed"]
    
    can_retry = execution.status in [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]
    
    return {
        "execution_id": execution_id,
        "current_status": execution.status.value,
        "can_retry": can_retry,
        "completed_phases": completed_phases,
        "task_summary": {
            "completed": len(task_summary["completed"]),
            "failed": len(task_summary["failed"]),
            "pending": len(task_summary["pending"]),
            "blocked": len(task_summary["blocked"]),
        },
        "failed_tasks": task_summary["failed"],
        "resume_point": "build_tasks" if task_summary["failed"] else ("phase2" if "pm" in completed_phases else "phase1")
    }


# ==================== BUILD PHASE EXECUTION ====================


async def safe_execute_build_phase(execution_id: int):
    """Wrapper to catch and log any errors in background BUILD execution"""
    try:
        logger.info(f"[BUILD] 🚀 Background task starting for execution {execution_id}")
        await execute_build_phase(execution_id)
    except Exception as e:
        logger.error(f"[BUILD] 💥 Background task crashed: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"[BUILD] Traceback: {traceback.format_exc()}")

async def execute_build_phase(execution_id: int):
    """
    Background task to execute all BUILD phase tasks.
    Uses IncrementalExecutor to run each task through the full cycle:
    Agent → SFDX Deploy → Elena Tests → Git Commit
    """
    from app.database import SessionLocal
    from app.services.incremental_executor import IncrementalExecutor
    from app.models.execution import Execution, ExecutionStatus
    from app.models.project import Project, ProjectStatus
    
    logger.info(f"[BUILD] ══════════════════════════════════════════════════════")
    logger.info(f"[BUILD] Starting BUILD phase for execution {execution_id}")
    
    db = SessionLocal()
    
    try:
        # Get execution
        execution = db.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            logger.error(f"[BUILD] Execution {execution_id} not found")
            return
        
        # Update execution status
        execution.status = ExecutionStatus.RUNNING
        db.commit()
        
        # Initialize IncrementalExecutor
        executor = IncrementalExecutor(db, execution_id)
        
        # Execute tasks one by one
        tasks_completed = 0
        tasks_failed = 0
        
        while True:
            # Get next available task
            next_task = executor.get_next_task()
            
            if next_task is None:
                # No more tasks or all blocked
                if executor.is_build_complete():
                    logger.info(f"[BUILD] ✅ All tasks completed!")
                    break
                else:
                    # Check if we have blocked tasks only
                    summary = executor.get_task_summary()
                    if summary["by_status"].get("BLOCKED", 0) > 0 and summary["by_status"].get("PENDING", 0) == 0:
                        logger.warning(f"[BUILD] ⚠️ {summary['by_status'].get('BLOCKED', 0)} tasks blocked - cannot continue")
                        break
                    logger.info(f"[BUILD] Waiting for dependencies... (completed: {summary['by_status'].get('COMPLETED', 0)}, blocked: {summary['by_status'].get('BLOCKED', 0)})")
                    # PERF-001: Intentional delay while waiting for dependencies
                    await asyncio.sleep(2)
                    continue
            
            # Execute task
            logger.info(f"[BUILD] ────────────────────────────────────────────")
            logger.info(f"[BUILD] Processing task {tasks_completed + 1}: {next_task.task_id}")
            
            result = await executor.execute_single_task(next_task)
            
            if result.get("success"):
                tasks_completed += 1
                logger.info(f"[BUILD] ✅ Task {next_task.task_id} completed ({tasks_completed} done)")
            else:
                tasks_failed += 1
                logger.error(f"[BUILD] ❌ Task {next_task.task_id} failed: {result.get('error')}")
                
                # Check if we should continue despite failure
                if tasks_failed > 5:
                    logger.error(f"[BUILD] Too many failures ({tasks_failed}), stopping BUILD")
                    break
            
            # PERF-001: Small intentional delay between BUILD tasks
            await asyncio.sleep(1)
        
        # Finalize build
        logger.info(f"[BUILD] ══════════════════════════════════════════════════════")
        logger.info(f"[BUILD] Finalizing BUILD phase...")
        
        summary = executor.get_task_summary()
        
        if summary["failed"] == 0 and summary["completed"] == summary["total"]:
            # All tasks passed - finalize
            finalize_result = await executor.finalize_build()
            
            # Update project and execution status
            project = db.query(Project).filter(Project.id == execution.project_id).first()
            if project:
                project.status = ProjectStatus.BUILD_COMPLETED
            execution.status = ExecutionStatus.COMPLETED
            
            logger.info(f"[BUILD] ✅ BUILD phase COMPLETED successfully")
            logger.info(f"[BUILD]    - Tasks completed: {summary['completed']}")
            logger.info(f"[BUILD]    - Package: {finalize_result.get('package_path', 'N/A')}")
        else:
            # Some failures
            execution.status = ExecutionStatus.FAILED
            logger.warning(f"[BUILD] ⚠️ BUILD phase finished with issues")
            logger.warning(f"[BUILD]    - Completed: {summary['completed']}/{summary['total']}")
            logger.warning(f"[BUILD]    - Failed: {summary['failed']}")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"[BUILD] ❌ BUILD phase exception: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if execution:
                execution.status = ExecutionStatus.FAILED
                db.commit()
        except:
            pass
    finally:
        db.close()
        logger.info(f"[BUILD] ══════════════════════════════════════════════════════")


# ════════════════════════════════════════════════════════════════════════════════
# PAUSE / RESUME BUILD
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/execute/{execution_id}/pause-build")
async def pause_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Pause the BUILD phase execution.
    Current task will complete, but no new tasks will start.
    """
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService
    
    service = BuildPhaseService(db)
    result = service.pause_build(execution_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))
    
    return {
        "status": result["status"],
        "message": result["message"],
        "execution_id": execution_id
    }


@router.post("/execute/{execution_id}/resume-build")
async def resume_build(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resume a paused BUILD phase execution.
    """
    from app.services.pm_orchestrator_service_v2 import BuildPhaseService
    
    service = BuildPhaseService(db)
    result = service.resume_build(execution_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=result.get("code", 400), detail=result.get("error"))
    
    # Restart the build phase in background
    asyncio.create_task(safe_execute_build_phase(execution_id))
    
    return {
        "status": result["status"],
        "message": "BUILD resumed. Execution continuing from next pending task.",
        "execution_id": execution_id
    }


# ════════════════════════════════════════════════════════════════════════════════
# SDS V3 - MICRO-ANALYSE UC (LLM LOCAL)
# ════════════════════════════════════════════════════════════════════════════════

@router.post("/execute/{execution_id}/microanalyze")
async def microanalyze_ucs(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    SDS V3: Lance la micro-analyse des UCs avec LLM local (Mistral).
    
    Cette étape analyse chaque UC individuellement pour générer des "Fiches Besoin" JSON
    qui seront utilisées pour enrichir le SDS et le WBS.
    
    Prérequis: L'exécution doit avoir des UCs générés (Phase 2 - Olivia terminée).
    
    Returns:
        - total_ucs: Nombre d'UCs à analyser
        - analyzed: Nombre d'UCs analysés avec succès
        - failed: Nombre d'échecs
        - agent_distribution: Répartition des agents suggérés
        - cost_usd: Coût total (0 si LLM local)
        - avg_latency_ms: Latence moyenne par UC
    """
    from app.models.deliverable_item import DeliverableItem
    from app.services.uc_analyzer_service import get_uc_analyzer, UCAnalyzerService
    from app.models.uc_requirement_sheet import UCRequirementSheet
    from sqlalchemy import select
    
    # Vérifier l'exécution
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Vérifier que l'utilisateur a accès
    project = db.query(Project).filter(Project.id == execution.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Récupérer les UCs depuis deliverable_items
    ucs = db.query(DeliverableItem).filter(
        DeliverableItem.execution_id == execution_id,
        DeliverableItem.item_type == "use_case"
    ).all()
    
    if not ucs:
        raise HTTPException(
            status_code=400, 
            detail="No Use Cases found. Run Phase 2 (Olivia) first."
        )
    
    logger.info(f"[MicroAnalyze] Starting analysis of {len(ucs)} UCs for execution {execution_id}")
    
    # Convertir en format dict pour l'analyseur
    uc_dicts = []
    for uc in ucs:
        # content_parsed contient le JSON complet du UC
        parsed = uc.content_parsed or {}
        uc_dict = {
            "id": uc.item_id,
            "uc_id": uc.item_id,
            "title": parsed.get("title", ""),
            "parent_br_id": uc.parent_ref,
        }
        # Fusionner le contenu JSON si disponible
        if isinstance(parsed, dict):
            uc_dict.update(parsed)
        uc_dicts.append(uc_dict)
    
    # Lancer l'analyse
    analyzer = get_uc_analyzer()
    
    # Analyse séquentielle (LLM local = pas de parallélisme)
    results = await analyzer.analyze_batch(uc_dicts)
    
    # Sauvegarder en base
    saved_count = 0
    errors = []
    for (fiche, llm_response), uc_dict in zip(results, uc_dicts):
        try:
            # Vérifier si existe déjà
            existing = db.query(UCRequirementSheet).filter(
                UCRequirementSheet.execution_id == execution_id,
                UCRequirementSheet.uc_id == fiche.uc_id
            ).first()
            
            if existing:
                # Mise à jour
                existing.uc_title = fiche.titre or uc_dict.get("title", "")
                existing.sheet_content = fiche.to_dict()
                existing.analysis_complete = not bool(fiche.error)
                existing.analysis_error = fiche.error
                if llm_response:
                    existing.llm_provider = llm_response.provider
                    existing.llm_model = llm_response.model_id
                    existing.tokens_in = llm_response.tokens_in
                    existing.tokens_out = llm_response.tokens_out
                    existing.cost_usd = llm_response.cost_usd
                    existing.latency_ms = llm_response.latency_ms
            else:
                # Création
                sheet = UCRequirementSheet(
                    execution_id=execution_id,
                    uc_id=fiche.uc_id,
                    uc_title=fiche.titre or uc_dict.get("title", ""),
                    parent_br_id=uc_dict.get("parent_br_id"),
                    sheet_content=fiche.to_dict(),
                    analysis_complete=not bool(fiche.error),
                    analysis_error=fiche.error,
                    llm_provider=llm_response.provider if llm_response else None,
                    llm_model=llm_response.model_id if llm_response else None,
                    tokens_in=llm_response.tokens_in if llm_response else 0,
                    tokens_out=llm_response.tokens_out if llm_response else 0,
                    cost_usd=llm_response.cost_usd if llm_response else 0.0,
                    latency_ms=llm_response.latency_ms if llm_response else 0
                )
                db.add(sheet)
            
            if not fiche.error:
                saved_count += 1
            else:
                errors.append({"uc_id": fiche.uc_id, "error": fiche.error})
                
        except Exception as e:
            logger.error(f"[MicroAnalyze] Error saving {fiche.uc_id}: {e}")
            errors.append({"uc_id": fiche.uc_id, "error": str(e)})
    
    db.commit()
    
    # Stats
    stats = analyzer.get_stats()
    
    # Distribution des agents
    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id,
        UCRequirementSheet.analysis_complete == True
    ).all()
    
    agent_distribution = {}
    for sheet in sheets:
        if sheet.sheet_content:
            agent = sheet.sheet_content.get("agent_suggere", "unknown")
            agent_distribution[agent] = agent_distribution.get(agent, 0) + 1
    
    logger.info(f"[MicroAnalyze] Completed: {saved_count}/{len(ucs)} UCs analyzed")
    logger.info(f"[MicroAnalyze] Agent distribution: {agent_distribution}")
    
    return {
        "execution_id": execution_id,
        "total_ucs": len(ucs),
        "analyzed": saved_count,
        "failed": len(errors),
        "errors": errors[:5] if errors else [],  # Max 5 erreurs affichées
        "agent_distribution": agent_distribution,
        "cost_usd": round(stats.get("total_cost_usd", 0), 4),
        "avg_latency_ms": stats.get("avg_latency_ms", 0),
        "success_rate": stats.get("success_rate", 0),
        "llm_provider": "ollama/mistral" if saved_count > 0 else None
    }


@router.get("/execute/{execution_id}/requirement-sheets")
async def get_requirement_sheets(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupère les Fiches Besoin générées par la micro-analyse.
    
    Returns:
        - sheets: Liste des fiches avec leur contenu
        - stats: Statistiques agrégées
    """
    from app.models.uc_requirement_sheet import UCRequirementSheet
    
    # Vérifier l'exécution
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    # Vérifier que l'utilisateur a accès
    project = db.query(Project).filter(Project.id == execution.project_id).first()
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    sheets = db.query(UCRequirementSheet).filter(
        UCRequirementSheet.execution_id == execution_id
    ).order_by(UCRequirementSheet.uc_id).all()
    
    # Stats
    total = len(sheets)
    complete = sum(1 for s in sheets if s.analysis_complete)
    total_latency = sum(s.latency_ms or 0 for s in sheets)
    total_cost = sum(s.cost_usd or 0 for s in sheets)
    
    # Distribution agents
    agent_dist = {}
    complexity_dist = {"simple": 0, "moyenne": 0, "complexe": 0}
    for s in sheets:
        if s.analysis_complete and s.sheet_content:
            agent = s.sheet_content.get("agent_suggere", "unknown")
            agent_dist[agent] = agent_dist.get(agent, 0) + 1
            comp = s.sheet_content.get("complexite", "moyenne")
            if comp in complexity_dist:
                complexity_dist[comp] += 1
    
    return {
        "execution_id": execution_id,
        "stats": {
            "total": total,
            "analyzed": complete,
            "pending": total - complete,
            "total_latency_ms": total_latency,
            "avg_latency_ms": round(total_latency / max(1, complete)),
            "total_cost_usd": round(total_cost, 4),
            "agent_distribution": agent_dist,
            "complexity_distribution": complexity_dist
        },
        "sheets": [s.to_dict() for s in sheets]
    }
