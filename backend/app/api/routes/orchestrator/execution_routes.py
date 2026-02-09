"""
Execution management routes for PM Orchestrator.

P4: Extracted from pm_orchestrator.py — SDS execution lifecycle.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List
import asyncio
import json
from datetime import datetime
import logging

from app.database import get_db
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.execution import Execution, ExecutionStatus
from app.schemas.execution import (
    ExecutionCreate,
    Execution as ExecutionSchema,
    ExecutionStartResponse,
    ExecutionResultResponse,
)
from app.utils.dependencies import get_current_user, get_current_user_from_token_or_header
from app.workers.arq_config import get_redis_pool
from app.services.budget_service import BudgetService, BudgetExceededError
from app.rate_limiter import limiter, RateLimits
from app.api.routes.orchestrator._helpers import (
    AGENT_NAMES,
    STATUS_MAP,
    verify_execution_access,
    parse_agent_status,
    parse_selected_agents,
    build_agent_progress,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["PM Orchestrator"])


@router.post("/execute", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(RateLimits.EXECUTE_SDS)
async def start_execution(
    request: Request,
    response: Response,
    execution_data: ExecutionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start execution of selected agents for a project."""
    project = db.query(Project).filter(
        Project.id == execution_data.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    if "pm" not in execution_data.selected_agents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product Manager (PM) agent is required and must be selected",
        )

    agent_execution_status = {
        agent_id: {"state": "waiting", "progress": 0, "message": "Waiting to start..."}
        for agent_id in execution_data.selected_agents
        if agent_id != "pm"
    }

    execution = Execution(
        project_id=project.id,
        user_id=current_user.id,
        selected_agents=execution_data.selected_agents,
        agent_execution_status=agent_execution_status,
        status=ExecutionStatus.RUNNING,
        started_at=datetime.utcnow(),
    )

    try:
        db.add(execution)
        db.commit()
        db.refresh(execution)
    except Exception:
        db.rollback()
        raise

    pool = await get_redis_pool()
    job = await pool.enqueue_job(
        "execute_sds_task",
        execution_id=execution.id,
        project_id=project.id,
        selected_agents=execution_data.selected_agents,
        _queue_name="digital-humans",
    )
    logger.info(f"[ARQ] Job {job.job_id} enqueued for execution {execution.id}")

    return ExecutionStartResponse(
        execution_id=execution.id,
        status="started",
        message="Execution started successfully. Use the progress endpoint to track status.",
    )


@router.post("/execute/{execution_id}/resume", response_model=ExecutionStartResponse, status_code=status.HTTP_202_ACCEPTED)
async def resume_execution(
    execution_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume execution after BR validation or architecture validation (H12)."""
    execution = verify_execution_access(execution_id, current_user.id, db)

    # Parse optional action from request body
    action = None
    try:
        body = await request.json()
        action = body.get("action")
    except Exception:
        pass  # No body or invalid JSON — action stays None

    allowed_statuses = [
        ExecutionStatus.WAITING_BR_VALIDATION,
        ExecutionStatus.WAITING_ARCHITECTURE_VALIDATION,
        # P2-Full: Configurable validation gates
        ExecutionStatus.WAITING_EXPERT_VALIDATION,
        ExecutionStatus.WAITING_SDS_VALIDATION,
        ExecutionStatus.WAITING_BUILD_VALIDATION,
        ExecutionStatus.FAILED,
    ]
    if execution.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume execution. Current status: {execution.status.value}",
        )

    # ── H12: Architecture validation resume ──
    if execution.status == ExecutionStatus.WAITING_ARCHITECTURE_VALIDATION:
        if action not in ("approve_architecture", "revise_architecture"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action required: 'approve_architecture' or 'revise_architecture'",
            )
        logger.info(f"[Resume] Architecture validation: action={action}, execution={execution_id}")
        pool = await get_redis_pool()
        job = await pool.enqueue_job(
            "resume_architecture_task",
            execution_id=execution.id,
            project_id=execution.project_id,
            action=action,
            _queue_name="digital-humans",
        )
        logger.info(f"[ARQ] Job {job.job_id} enqueued for architecture resume {execution.id}")
        return ExecutionStartResponse(
            execution_id=execution.id,
            status="resumed",
            message=f"Architecture validation: {action}. Use the progress endpoint to track status.",
        )

    # ── BR validation resume (existing logic) ──
    resume_point = None
    if execution.status == ExecutionStatus.WAITING_BR_VALIDATION:
        resume_point = "phase2_ba"
    elif execution.status == ExecutionStatus.FAILED:
        from app.models.business_requirement import BusinessRequirement, BRStatus

        validated_brs = db.query(BusinessRequirement).filter(
            BusinessRequirement.project_id == execution.project_id,
            BusinessRequirement.status == BRStatus.VALIDATED,
        ).count()
        if validated_brs > 0:
            resume_point = "phase2_ba"
            logger.info(f"Resuming FAILED execution {execution_id} with {validated_brs} validated BRs")
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot resume: no validated Business Requirements found.",
            )

    if not resume_point:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine resume point.",
        )

    try:
        execution.status = ExecutionStatus.RUNNING
        db.commit()
    except Exception:
        db.rollback()
        raise

    pool = await get_redis_pool()
    job = await pool.enqueue_job(
        "execute_sds_task",
        execution_id=execution.id,
        project_id=execution.project_id,
        selected_agents=execution.selected_agents,
        resume_from=resume_point,
        _queue_name="digital-humans",
    )
    logger.info(f"[ARQ] Job {job.job_id} enqueued for resume {execution.id} from {resume_point}")

    return ExecutionStartResponse(
        execution_id=execution.id,
        status="resumed",
        message=f"Execution resumed from {resume_point}. Use the progress endpoint to track status.",
    )


@router.get("/execute/{execution_id}/progress")
def get_execution_progress(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Get current progress of an execution."""
    execution = verify_execution_access(execution_id, current_user.id, db)
    agent_progress, overall_progress, current_phase = build_agent_progress(execution)

    return {
        "execution_id": execution.id,
        "project_id": execution.project_id,
        "status": execution.status.value if hasattr(execution.status, "value") else str(execution.status),
        "overall_progress": overall_progress,
        "current_phase": current_phase,
        "agent_progress": agent_progress,
        "sds_document_path": execution.sds_document_path,
    }


@router.get("/execute/{execution_id}/progress/stream")
async def stream_execution_progress(
    execution_id: int,
    token: str = Query(..., description="JWT token for authentication"),
    db: Session = Depends(get_db),
):
    """Stream execution progress updates via Server-Sent Events (SSE)."""
    # Validate token
    try:
        from app.services.auth_service import verify_token

        payload = verify_token(token)
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

    execution = (
        db.query(Execution)
        .join(Project)
        .filter(Execution.id == execution_id, Project.user_id == int(user_id))
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Try notifications, fallback to polling
    try:
        from app.services.notification_service import get_notification_service

        notification_service = await get_notification_service()
        use_notifications = True
    except Exception as e:
        logger.debug(f"Notifications unavailable, using polling: {e}")
        use_notifications = False
        notification_service = None

    async def event_generator():
        last_status = None
        last_progress = -1
        max_duration = 600
        start_time = asyncio.get_event_loop().time()
        poll_interval = 3 if use_notifications else 2

        def build_progress_data():
            db.refresh(execution)
            agent_prog, overall, phase = build_agent_progress(execution)
            current_status = (
                execution.status.value if hasattr(execution.status, "value") else str(execution.status)
            )
            return {
                "execution_id": execution.id,
                "status": current_status,
                "overall_progress": overall,
                "current_phase": phase,
                "agent_progress": agent_prog,
            }, current_status, overall

        if use_notifications and notification_service:
            channel = f"execution_{execution_id}"
            try:
                async with notification_service.subscribe(channel) as queue:
                    while (asyncio.get_event_loop().time() - start_time) < max_duration:
                        try:
                            try:
                                await asyncio.wait_for(queue.get(), timeout=poll_interval)
                            except asyncio.TimeoutError:
                                pass
                            data, current_status, overall = build_progress_data()
                            if current_status != last_status or overall != last_progress:
                                yield f"data: {json.dumps(data)}\n\n"
                                last_status = current_status
                                last_progress = overall
                            terminal = ["COMPLETED", "FAILED", "CANCELLED",
                                       "WAITING_EXPERT_VALIDATION", "WAITING_SDS_VALIDATION", "WAITING_BUILD_VALIDATION"]
                            if current_status.upper() in terminal or current_status in terminal:
                                yield f"data: {json.dumps({'event': 'close', 'status': current_status})}\n\n"
                                return
                        except Exception as e:
                            logger.error(f"SSE notification error: {e}")
                            break
            except Exception as e:
                logger.warning(f"SSE subscription failed, falling back to polling: {e}")
                use_notifications = False

        if not use_notifications:
            while (asyncio.get_event_loop().time() - start_time) < max_duration:
                try:
                    data, current_status, overall = build_progress_data()
                    if current_status != last_status or overall != last_progress:
                        yield f"data: {json.dumps(data)}\n\n"
                        last_status = current_status
                        last_progress = overall
                    terminal = ["COMPLETED", "FAILED", "CANCELLED",
                               "WAITING_EXPERT_VALIDATION", "WAITING_SDS_VALIDATION", "WAITING_BUILD_VALIDATION"]
                    if current_status.upper() in terminal or current_status in terminal:
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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/execute/{execution_id}/result", response_model=ExecutionResultResponse)
def get_execution_result(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get final execution result including SDS document information."""
    execution = verify_execution_access(execution_id, current_user.id, db)

    if execution.status != ExecutionStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Execution not yet completed. Current status: {execution.status.value}",
        )

    return ExecutionResultResponse(
        execution_id=execution.id,
        status=execution.status,
        sds_document_url=f"/api/pm-orchestrator/execute/{execution.id}/download" if execution.sds_document_path else None,
        execution_time=execution.duration_seconds,
        agents_used=len(execution.selected_agents) if execution.selected_agents else 0,
        total_cost=execution.total_cost,
        completed_at=execution.completed_at,
    )


@router.get("/execute/{execution_id}/download")
def download_sds_document(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_from_token_or_header),
):
    """Download the generated SDS document."""
    execution = verify_execution_access(execution_id, current_user.id, db)

    if not execution.sds_document_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SDS document not available")

    project = db.query(Project).filter(Project.id == execution.project_id).first()
    filename = f"SDS_{project.name.replace(' ', '_')}_{execution.id}.docx"

    return FileResponse(
        path=execution.sds_document_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/executions", response_model=List[ExecutionSchema])
def list_executions(
    project_id: int = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get execution history for the current user."""
    query = db.query(Execution).filter(Execution.user_id == current_user.id)

    if project_id:
        project = db.query(Project).filter(
            Project.id == project_id, Project.user_id == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        query = query.filter(Execution.project_id == project_id)

    return query.order_by(Execution.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/agents")
def list_available_agents(
    current_user: User = Depends(get_current_user),
):
    """Get list of all available Salesforce agents with their metadata."""
    from app.services.agent_integration import AgentIntegrationService

    agent_service = AgentIntegrationService()
    agents = agent_service.get_available_agents()
    return {"agents": agents}


@router.get("/execute/{execution_id}/budget")
def get_execution_budget(
    execution_id: int,
    db: Session = Depends(get_db),
):
    """Get budget status for an execution (P1.1)."""
    service = BudgetService(db)
    try:
        return service.check_budget(execution_id)
    except BudgetExceededError as e:
        return {
            "allowed": False,
            "limit_type": e.limit_type,
            "current": e.current,
            "limit": e.limit,
            "message": str(e),
        }


@router.get("/workers/health")
async def worker_health():
    """Check ARQ worker status via Redis."""
    try:
        pool = await get_redis_pool()
        info = await pool.info()
        queued = await pool.llen(b"arq:queue:digital-humans")
        return {
            "redis": "connected",
            "redis_version": info.get("redis_version", "unknown"),
            "queued_jobs": queued,
        }
    except Exception as e:
        return {"redis": "error", "detail": str(e)}
