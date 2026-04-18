"""HITL (Human-in-the-Loop) routes for contextual chat, CR lifecycle, versions/diff, and metrics."""
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.execution import Execution
from app.models.change_request import ChangeRequest
from app.models.agent_deliverable import AgentDeliverable
from app.models.sds_version import SDSVersion
from app.models.artifact import ExecutionArtifact
from app.models.project_conversation import ProjectConversation
from app.services.change_request_service import ChangeRequestService
from app.services.sophie_chat_service import SophieChatService
from app.services.agents_registry import (
    AgentNotFoundError,
    get_chat_profile,
    iter_chat_profiles,
    resolve_agent_id,
)
from app.schemas.change_request import ChangeRequestResponse, ChangeRequestList

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/pm-orchestrator",
    tags=["hitl"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas specific to HITL routes
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Body for contextual chat endpoint."""
    message: str
    agent_id: Optional[str] = "sophie"  # Agent to chat with
    deliverable_id: Optional[int] = None
    phase: Optional[int] = None


class ChatResponse(BaseModel):
    """Response from contextual chat."""
    response: str
    agent_id: str = "sophie"
    agent_name: str = "Sophie"
    change_request: Optional[ChangeRequestResponse] = None


class MetricsResponse(BaseModel):
    """Execution metrics."""
    tokens_by_agent: dict
    cost_by_phase: dict
    duration_by_phase: dict
    deliverables_count: int


class VersionEntry(BaseModel):
    """A single artifact version entry."""
    id: int
    version: int
    producer_agent: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DiffResponse(BaseModel):
    """Side-by-side diff of two versions."""
    v1: int
    v2: int
    content_v1: dict
    content_v2: dict

# ---------------------------------------------------------------------------
# Agent Chat Profiles — sourced from agents_registry.yaml (see B-2d / N93).
# The old inline dict used to duplicate Sophie's system prompt; now every
# profile comes from one canonical place.
# ---------------------------------------------------------------------------

# Backward compat: a dict view of the registry in the legacy shape.
AGENT_CHAT_PROFILES = {
    p["agent_id"]: {
        "name": p["name"],
        "role": p["role"],
        "agent_type": p["agent_type"],
        "color": p["color"],
        "deliverable_types": p["deliverable_types"],
        "system_prompt": p["system_prompt"],
    }
    for p in iter_chat_profiles()
}




# ---------------------------------------------------------------------------
# 1. Contextual Chat
# ---------------------------------------------------------------------------

@router.post("/executions/{execution_id}/chat", response_model=ChatResponse)
def chat_with_sophie_contextual(
    execution_id: int,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a contextual message to an agent within an execution.

    If a deliverable_id is provided, the deliverable content is loaded as context.
    If the agent detects the message implies a modification, a ChangeRequest is
    created automatically.
    """
    # Resolve agent via registry (N93 — single source of truth for chat profiles).
    try:
        canonical_agent_id = resolve_agent_id(body.agent_id or "sophie")
    except AgentNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown agent_id: {body.agent_id}")
    profile = get_chat_profile(canonical_agent_id)

    # Verify execution exists and belongs to user
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")

    # Build deliverable context
    deliverable_context = ""
    if body.deliverable_id:
        deliverable = db.query(AgentDeliverable).filter(
            AgentDeliverable.id == body.deliverable_id,
            AgentDeliverable.execution_id == execution_id,
        ).first()
        if deliverable:
            deliverable_context = (deliverable.content or "")[:8000]

    # Load conversation history for this agent only (N92 — chat is per-agent).
    history = db.query(ProjectConversation).filter(
        ProjectConversation.project_id == project.id,
        ProjectConversation.execution_id == execution_id,
        ProjectConversation.agent_id == canonical_agent_id,
    ).order_by(ProjectConversation.created_at.desc()).limit(10).all()

    agent_label = profile["name"]
    history_text = ""
    for msg in reversed(history):
        role_label = "Client" if msg.role == "user" else agent_label
        history_text += f"\n{role_label}: {msg.message}\n"

    # Build prompt with context
    phase_label = f" (Phase {body.phase})" if body.phase else ""
    deliverable_section = ""
    if deliverable_context:
        deliverable_section = f"\n## Livrable en contexte{phase_label}\n{deliverable_context}\n"

    full_prompt = f"{history_text}\n{deliverable_section}\nClient: {body.message}\n\n{agent_label}:"

    # N93 fix: system prompt now sourced from agents_registry.yaml (no inline dup).
    system_prompt = profile["system_prompt"].format(project_name=project.name)

    # Call LLM via router (C-0: no more LLMService bypass)
    from app.services.llm_service import generate_llm_response

    try:
        response = generate_llm_response(
            prompt=full_prompt,
            agent_type=profile["agent_type"],
            system_prompt=system_prompt,
            max_tokens=1500,
            temperature=0.7,
        )
    except Exception as e:
        logger.error(f"[HITL Chat] LLM call failed: {e}")
        raise HTTPException(status_code=500, detail="LLM call failed")

    assistant_message = response["content"]
    tokens_used = response.get("tokens_used", 0)
    model_used = response.get("model", "unknown")

    # Save user message + assistant response with agent_id (N92 fix).
    for role, text, tokens in [
        ("user", body.message, 0),
        ("assistant", assistant_message, tokens_used),
    ]:
        db.add(ProjectConversation(
            project_id=project.id,
            execution_id=execution_id,
            agent_id=canonical_agent_id,
            role=role,
            message=text,
            tokens_used=tokens,
            model_used=model_used,
        ))
    db.commit()

    # Detect if a CR should be created
    cr_response = None
    cr_service = ChangeRequestService(db)
    cr = cr_service.create_from_chat(
        message=body.message,
        execution_id=execution_id,
        deliverable_id=body.deliverable_id,
        user_id=current_user.id,
    )
    if cr:
        cr_response = ChangeRequestResponse.model_validate(cr)

    return ChatResponse(
        response=assistant_message,
        agent_id=canonical_agent_id,
        agent_name=profile["name"],
        change_request=cr_response,
    )


# ---------------------------------------------------------------------------
# 2. CR Lifecycle
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/change-requests", response_model=ChangeRequestList)
def list_project_change_requests(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all change requests for a project."""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(ChangeRequest).filter(ChangeRequest.project_id == project_id)
    if status:
        query = query.filter(ChangeRequest.status == status)

    crs = query.order_by(ChangeRequest.created_at.desc()).all()

    responses = [ChangeRequestResponse.model_validate(cr) for cr in crs]
    pending_count = sum(1 for cr in crs if cr.status in ["draft", "submitted", "analyzed", "approved", "processing"])
    completed_count = sum(1 for cr in crs if cr.status == "completed")

    return ChangeRequestList(
        change_requests=responses,
        total_count=len(crs),
        pending_count=pending_count,
        completed_count=completed_count,
    )


@router.post("/change-requests/{cr_id}/analyze")
def analyze_change_request(
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run Sophie's impact analysis on a CR. Updates impact_analysis, estimated_cost, agents_to_rerun."""
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    # Verify ownership
    project = db.query(Project).filter(
        Project.id == cr.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    if cr.status not in ("draft", "submitted"):
        raise HTTPException(status_code=400, detail=f"Cannot analyze CR in status '{cr.status}'")

    # Mark as submitted if still draft
    if cr.status == "draft":
        cr.status = "submitted"
        cr.submitted_at = datetime.utcnow()
        db.commit()

    service = ChangeRequestService(db)
    result = service.analyze_impact(cr_id)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Analysis failed"))

    return {
        "message": "Impact analysis complete",
        "cr_id": cr_id,
        "cr_number": result["cr_number"],
        "status": "analyzed",
        "impact_analysis": result["impact_analysis"],
        "estimated_cost": result["estimated_cost"],
        "agents_to_rerun": result["agents_to_rerun"],
    }


@router.post("/change-requests/{cr_id}/approve")
def approve_change_request(
    cr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve an analyzed CR, setting status to approved."""
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    project = db.query(Project).filter(
        Project.id == cr.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    if cr.status != "analyzed":
        raise HTTPException(status_code=400, detail="CR must be analyzed before approval")

    cr.status = "approved"
    cr.approved_at = datetime.utcnow()
    db.commit()

    return {
        "message": "CR approved",
        "cr_id": cr_id,
        "cr_number": cr.cr_number,
        "status": "approved",
    }


@router.post("/change-requests/{cr_id}/execute")
def execute_change_request(
    cr_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute an approved CR: launch agents_to_rerun in background and
    create a new SDSVersion when done.
    """
    cr = db.query(ChangeRequest).filter(ChangeRequest.id == cr_id).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    project = db.query(Project).filter(
        Project.id == cr.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    if cr.status != "approved":
        raise HTTPException(status_code=400, detail="CR must be approved before execution")

    async def _run_cr(cr_id: int):
        from app.database import SessionLocal
        session = SessionLocal()
        try:
            service = ChangeRequestService(session)
            result = await service.execute_cr(cr_id)
            logger.info(f"[HITL] CR {cr_id} execution result: {result.get('success')}")
        except Exception as e:
            logger.error(f"[HITL] CR {cr_id} execution error: {e}")
        finally:
            session.close()

    background_tasks.add_task(_run_cr, cr_id)

    return {
        "message": "CR execution started in background",
        "cr_id": cr_id,
        "cr_number": cr.cr_number,
        "agents_to_rerun": cr.agents_to_rerun,
    }


# ---------------------------------------------------------------------------
# 3. Deliverable Versions & Diff
# ---------------------------------------------------------------------------

def _load_artifact_for_user(
    artifact_id: int,
    db: Session,
    current_user: User,
) -> ExecutionArtifact:
    """Fetch an ExecutionArtifact after verifying project ownership."""
    artifact = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.id == artifact_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")

    execution = db.query(Execution).filter(Execution.id == artifact.execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")
    return artifact


def _list_artifact_versions(artifact: ExecutionArtifact, db: Session) -> List[VersionEntry]:
    versions = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.execution_id == artifact.execution_id,
        ExecutionArtifact.artifact_code == artifact.artifact_code,
    ).order_by(ExecutionArtifact.version.asc()).all()
    return [
        VersionEntry(
            id=v.id,
            version=v.version,
            producer_agent=v.producer_agent,
            status=v.status,
            created_at=v.created_at,
        )
        for v in versions
    ]


def _diff_artifact_versions(
    artifact: ExecutionArtifact,
    v1: int,
    v2: int,
    db: Session,
) -> DiffResponse:
    ver1 = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.execution_id == artifact.execution_id,
        ExecutionArtifact.artifact_code == artifact.artifact_code,
        ExecutionArtifact.version == v1,
    ).first()
    ver2 = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.execution_id == artifact.execution_id,
        ExecutionArtifact.artifact_code == artifact.artifact_code,
        ExecutionArtifact.version == v2,
    ).first()
    if not ver1:
        raise HTTPException(status_code=404, detail=f"Version {v1} not found")
    if not ver2:
        raise HTTPException(status_code=404, detail=f"Version {v2} not found")
    return DiffResponse(
        v1=v1,
        v2=v2,
        content_v1=ver1.content or {},
        content_v2=ver2.content or {},
    )


@router.get("/artifacts/{artifact_id}/versions", response_model=List[VersionEntry])
def list_artifact_versions(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all versions of an artifact (execution_artifacts table)."""
    artifact = _load_artifact_for_user(artifact_id, db, current_user)
    return _list_artifact_versions(artifact, db)


@router.get("/artifacts/{artifact_id}/diff", response_model=DiffResponse)
def diff_artifact_versions(
    artifact_id: int,
    v1: int = Query(..., description="Version number 1"),
    v2: int = Query(..., description="Version number 2"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the content of two artifact versions for client-side diff."""
    artifact = _load_artifact_for_user(artifact_id, db, current_user)
    return _diff_artifact_versions(artifact, v1, v2, db)


# --- Deprecated aliases kept for one release (N91 — `deliverable_id` was ambiguous) ---

@router.get(
    "/deliverables/{deliverable_id}/versions",
    response_model=List[VersionEntry],
    deprecated=True,
)
def list_deliverable_versions(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deprecated: use ``/artifacts/{artifact_id}/versions`` instead."""
    import warnings

    warnings.warn(
        "GET /deliverables/{id}/versions is deprecated; call /artifacts/{id}/versions instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    artifact = _load_artifact_for_user(deliverable_id, db, current_user)
    return _list_artifact_versions(artifact, db)


@router.get(
    "/deliverables/{deliverable_id}/diff",
    response_model=DiffResponse,
    deprecated=True,
)
def diff_deliverable_versions(
    deliverable_id: int,
    v1: int = Query(..., description="Version number 1"),
    v2: int = Query(..., description="Version number 2"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deprecated: use ``/artifacts/{artifact_id}/diff`` instead."""
    import warnings

    warnings.warn(
        "GET /deliverables/{id}/diff is deprecated; call /artifacts/{id}/diff instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    artifact = _load_artifact_for_user(deliverable_id, db, current_user)
    return _diff_artifact_versions(artifact, v1, v2, db)


# ---------------------------------------------------------------------------
# 4. Execution Metrics
# ---------------------------------------------------------------------------

@router.get("/executions/{execution_id}/metrics", response_model=MetricsResponse)
def get_execution_metrics(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return aggregated metrics for an execution:
    tokens_by_agent, cost_by_phase, duration_by_phase, deliverables_count.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Deliverables count
    deliverables_count = db.query(sa_func.count(AgentDeliverable.id)).filter(
        AgentDeliverable.execution_id == execution_id,
    ).scalar() or 0

    # Tokens by agent from agent_execution_status (JSONB on execution)
    tokens_by_agent: dict = {}
    cost_by_phase: dict = {}
    duration_by_phase: dict = {}

    agent_status = execution.agent_execution_status
    if isinstance(agent_status, str):
        import json
        try:
            agent_status = json.loads(agent_status)
        except Exception:
            agent_status = {}

    if isinstance(agent_status, dict):
        for agent_id, info in agent_status.items():
            if isinstance(info, dict):
                tokens_by_agent[agent_id] = info.get("tokens_used", 0)

    # Cost from execution totals
    total_cost = execution.total_cost or 0.0
    total_tokens = execution.total_tokens_used or 0

    # Build phase info from state_history
    state_history = execution.state_history or []
    if isinstance(state_history, list):
        for i, entry in enumerate(state_history):
            if not isinstance(entry, dict):
                continue
            phase_name = entry.get("to", f"phase_{i}")
            # Duration: diff between consecutive entries
            if i + 1 < len(state_history) and isinstance(state_history[i + 1], dict):
                try:
                    from datetime import datetime as dt
                    t1 = dt.fromisoformat(entry.get("at", ""))
                    t2 = dt.fromisoformat(state_history[i + 1].get("at", ""))
                    duration_by_phase[phase_name] = (t2 - t1).total_seconds()
                except Exception:
                    pass

    # Cost per phase: distribute proportionally by token count if available
    if tokens_by_agent and total_cost > 0:
        total_agent_tokens = sum(tokens_by_agent.values()) or 1
        for agent_id, tok in tokens_by_agent.items():
            cost_by_phase[agent_id] = round(total_cost * tok / total_agent_tokens, 4)

    return MetricsResponse(
        tokens_by_agent=tokens_by_agent,
        cost_by_phase=cost_by_phase,
        duration_by_phase=duration_by_phase,
        deliverables_count=deliverables_count,
    )


# ---------------------------------------------------------------------------
# 1b. Agent List & Chat History
# ---------------------------------------------------------------------------

@router.get("/executions/{execution_id}/agents")
def list_available_agents(
    execution_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List agents available for chat in this execution (those with deliverables)."""
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Get deliverable types for this execution
    deliverable_types = [
        r[0] for r in db.query(AgentDeliverable.deliverable_type)
        .filter(AgentDeliverable.execution_id == execution_id)
        .distinct().all()
    ]

    agents = []
    for profile in iter_chat_profiles():
        has_deliverables = bool(profile.get("always_available")) or profile["agent_id"] == "sophie"
        if not has_deliverables:
            for dtype in profile["deliverable_types"]:
                if any(dt.startswith(dtype) or dt == dtype for dt in deliverable_types):
                    has_deliverables = True
                    break
        if not has_deliverables:
            prefix = profile["agent_type"]
            if any(dt.startswith(prefix + "_") for dt in deliverable_types):
                has_deliverables = True

        agents.append({
            "agent_id": profile["agent_id"],
            "name": profile["name"],
            "role": profile["role"],
            "color": profile["color"],
            "available": has_deliverables,
        })

    return {"agents": agents}


@router.get("/executions/{execution_id}/chat/history")
def get_agent_chat_history(
    execution_id: int,
    agent_id: str = Query(default="sophie"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chat history for a specific agent in an execution."""
    try:
        canonical_agent_id = resolve_agent_id(agent_id)
    except AgentNotFoundError:
        raise HTTPException(status_code=400, detail=f"Unknown agent_id: {agent_id}")

    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Access denied")

    messages = db.query(ProjectConversation).filter(
        ProjectConversation.project_id == project.id,
        ProjectConversation.execution_id == execution_id,
        ProjectConversation.agent_id == canonical_agent_id,
    ).order_by(ProjectConversation.created_at.asc()).all()

    return {
        "agent_id": canonical_agent_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.message,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "tokens_used": msg.tokens_used,
            }
            for msg in messages
        ],
    }
