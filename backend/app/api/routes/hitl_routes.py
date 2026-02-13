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
# Agent Chat Profiles — system prompts for contextual chat
# ---------------------------------------------------------------------------

AGENT_CHAT_PROFILES = {
    "sophie": {
        "name": "Sophie",
        "role": "Project Manager",
        "agent_type": "pm",
        "color": "purple",
        "system_prompt": """Tu es Sophie, Project Manager senior chez Digital Humans, spécialisée en implémentation Salesforce.
Tu es en charge du projet "{project_name}".
Réponds aux questions du client sur le projet et ses livrables. Explique les choix faits.
Si le client demande une modification, propose de créer un Change Request.
Réponds en français, de manière concise et professionnelle.""",
    },
    "marcus": {
        "name": "Marcus",
        "role": "Solution Architect",
        "agent_type": "architect",
        "color": "blue",
        "deliverable_types": ["architect_solution_design", "architect_gap_analysis", "architect_wbs"],
        "system_prompt": """Tu es Marcus, Salesforce Certified Technical Architect (CTA).
Tu as conçu l'architecture du projet "{project_name}".
Tu peux expliquer tes choix de data model, flows, security, et répondre aux questions techniques.
Si le client propose une modification architecturale, explique l'impact et les dépendances.
Réponds en français, en étant précis et technique.""",
    },
    "olivia": {
        "name": "Olivia",
        "role": "Business Analyst",
        "agent_type": "business_analyst",
        "color": "green",
        "deliverable_types": ["ba_use_cases"],
        "system_prompt": """Tu es Olivia, Business Analyst senior spécialisée Salesforce.
Tu as rédigé les Use Cases du projet "{project_name}".
Tu peux expliquer la logique métier, les scénarios, et les critères d'acceptation.
Réponds en français, de manière claire et orientée métier.""",
    },
    "emma": {
        "name": "Emma",
        "role": "Research Analyst",
        "agent_type": "research_analyst",
        "color": "cyan",
        "deliverable_types": ["research_analyst_coverage_report", "research_analyst_sds_document"],
        "system_prompt": """Tu es Emma, Research Analyst senior.
Tu as validé la couverture de l'architecture et rédigé le SDS du projet "{project_name}".
Tu peux expliquer les gaps identifiés, le score de couverture, et la structure du SDS.
Réponds en français, de manière analytique et précise.""",
    },
    "elena": {
        "name": "Elena",
        "role": "QA Engineer",
        "agent_type": "qa_tester",
        "color": "pink",
        "deliverable_types": ["qa_"],
        "system_prompt": """Tu es Elena, QA Engineer senior spécialisée Salesforce.
Tu as conçu la stratégie de test du projet "{project_name}".
Tu peux expliquer les scénarios de test, la couverture, et les risques identifiés.
Réponds en français, de manière rigoureuse et méthodique.""",
    },
    "jordan": {
        "name": "Jordan",
        "role": "Admin Config",
        "agent_type": "admin",
        "color": "yellow",
        "deliverable_types": ["admin_"],
        "system_prompt": """Tu es Jordan, Salesforce Admin senior.
Tu as planifié la configuration du projet "{project_name}".
Tu peux expliquer les choix de configuration, permissions, et page layouts.
Réponds en français, de manière pratique et orientée solution.""",
    },
    "aisha": {
        "name": "Aisha",
        "role": "DevOps",
        "agent_type": "devops",
        "color": "orange",
        "deliverable_types": ["devops_"],
        "system_prompt": """Tu es Aisha, DevOps Engineer senior spécialisée Salesforce.
Tu as planifié le pipeline de déploiement du projet "{project_name}".
Tu peux expliquer la stratégie CI/CD, les environnements, et les migrations.
Réponds en français, de manière technique et concrète.""",
    },
    "lucas": {
        "name": "Lucas",
        "role": "Trainer",
        "agent_type": "trainer",
        "color": "teal",
        "deliverable_types": ["trainer_"],
        "system_prompt": """Tu es Lucas, Trainer senior spécialisé Salesforce.
Tu as conçu le plan de formation du projet "{project_name}".
Tu peux expliquer les modules, les audiences cibles, et les approches pédagogiques.
Réponds en français, de manière pédagogique et engageante.""",
    },
    "raj": {
        "name": "Raj",
        "role": "Data Migration",
        "agent_type": "data_migration",
        "color": "indigo",
        "deliverable_types": ["data_"],
        "system_prompt": """Tu es Raj, Data Migration Specialist senior.
Tu as conçu le plan de migration de données du projet "{project_name}".
Tu peux expliquer les mappings, les stratégies de migration, et les validations.
Réponds en français, de manière structurée et rigoureuse.""",
    },
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
    Send a contextual message to Sophie within an execution.

    If a deliverable_id is provided, the deliverable content is loaded as context.
    If Sophie detects the message implies a modification, a ChangeRequest is
    created automatically.
    """
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

    # Load conversation history
    history = db.query(ProjectConversation).filter(
        ProjectConversation.project_id == project.id,
        ProjectConversation.execution_id == execution_id,
    ).order_by(ProjectConversation.created_at.desc()).limit(10).all()

    history_text = ""
    for msg in reversed(history):
        role_label = "Client" if msg.role == "user" else "Sophie"
        history_text += f"\n{role_label}: {msg.message}\n"

    # Build prompt with context
    phase_label = f" (Phase {body.phase})" if body.phase else ""
    deliverable_section = ""
    if deliverable_context:
        deliverable_section = f"\n## Livrable en contexte{phase_label}\n{deliverable_context}\n"

    full_prompt = f"{history_text}\n{deliverable_section}\nClient: {body.message}\n\nSophie:"

    system_prompt = f"""Tu es Sophie, Project Manager senior chez Digital Humans, spécialisée en implémentation Salesforce.
Tu es en charge du projet "{project.name}".

Ton rôle:
- Répondre aux questions du client sur le projet et ses livrables
- Expliquer les choix techniques et fonctionnels
- Aider le client à comprendre les impacts de modifications potentielles
- Si le client demande une modification, explique-la clairement et propose de créer un Change Request

Réponds en français, de manière concise et professionnelle."""

    # Call LLM
    from app.services.llm_service import LLMService
    llm = LLMService()

    try:
        response = llm.generate(
            prompt=full_prompt,
            agent_type="sophie",
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

    # Save user message + assistant response
    for role, text, tokens in [
        ("user", body.message, 0),
        ("assistant", assistant_message, tokens_used),
    ]:
        db.add(ProjectConversation(
            project_id=project.id,
            execution_id=execution_id,
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

    return ChatResponse(response=assistant_message, change_request=cr_response)


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

@router.get("/deliverables/{deliverable_id}/versions", response_model=List[VersionEntry])
def list_deliverable_versions(
    deliverable_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all versions of an artifact (execution_artifacts table).

    The deliverable_id here refers to an ExecutionArtifact id. We find its
    artifact_code and list all versions sharing that code within the same execution.
    """
    artifact = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.id == deliverable_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    # Verify user access via execution -> project
    execution = db.query(Execution).filter(Execution.id == artifact.execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

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


@router.get("/deliverables/{deliverable_id}/diff", response_model=DiffResponse)
def diff_deliverable_versions(
    deliverable_id: int,
    v1: int = Query(..., description="Version number 1"),
    v2: int = Query(..., description="Version number 2"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the content of two artifact versions for client-side diff."""
    artifact = db.query(ExecutionArtifact).filter(
        ExecutionArtifact.id == deliverable_id,
    ).first()
    if not artifact:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    # Verify access
    execution = db.query(Execution).filter(Execution.id == artifact.execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(
        Project.id == execution.project_id,
        Project.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail="Access denied")

    # Load both versions
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
    for agent_id, profile in AGENT_CHAT_PROFILES.items():
        has_deliverables = agent_id == "sophie"  # Sophie always available
        if not has_deliverables and "deliverable_types" in profile:
            for dtype in profile["deliverable_types"]:
                if any(dt.startswith(dtype) or dt == dtype for dt in deliverable_types):
                    has_deliverables = True
                    break
        # Also check by agent_type prefix
        if not has_deliverables:
            prefix = profile.get("agent_type", "")
            if any(dt.startswith(prefix + "_") for dt in deliverable_types):
                has_deliverables = True

        agents.append({
            "agent_id": agent_id,
            "name": profile["name"],
            "role": profile["role"],
            "color": profile.get("color", "slate"),
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
        ProjectConversation.agent_id == agent_id,
    ).order_by(ProjectConversation.created_at.asc()).all()

    return {
        "agent_id": agent_id,
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
