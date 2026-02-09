"""
Shared helpers for pm_orchestrator route modules.

P4: Extracted from pm_orchestrator.py to avoid duplication across route files.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.execution import Execution


# Agent display names mapping (used in progress, SSE, WebSocket)
AGENT_NAMES = {
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
    "trainer": "Lucas (Trainer)",
}

# State mapping from internal to frontend format
STATUS_MAP = {
    "waiting": "pending",
    "running": "in_progress",
    "completed": "completed",
    "failed": "failed",
}


def verify_execution_access(
    execution_id: int,
    user_id: int,
    db: Session,
) -> Execution:
    """
    Verify that an execution exists and belongs to the given user.
    Raises HTTPException if not found.
    """
    execution = (
        db.query(Execution)
        .join(Project)
        .filter(Execution.id == execution_id, Project.user_id == user_id)
        .first()
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    return execution


def verify_execution_project_access(
    execution_id: int,
    user_id: int,
    db: Session,
) -> tuple:
    """
    Verify execution access and return both execution and project.
    Used by routes that need both objects.
    """
    execution = db.query(Execution).filter(Execution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    project = db.query(Project).filter(Project.id == execution.project_id).first()
    if not project or project.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return execution, project


def parse_agent_status(execution: Execution) -> dict:
    """Parse agent_execution_status from execution, handling str or dict."""
    import json

    agent_status = {}
    if execution.agent_execution_status:
        if isinstance(execution.agent_execution_status, str):
            agent_status = json.loads(execution.agent_execution_status)
        else:
            agent_status = execution.agent_execution_status
    return agent_status


def parse_selected_agents(execution: Execution) -> list:
    """Parse selected_agents from execution, handling str or list."""
    import json

    selected_agents = execution.selected_agents or []
    if isinstance(selected_agents, str):
        selected_agents = json.loads(selected_agents)
    return selected_agents


def build_agent_progress(execution: Execution) -> tuple:
    """
    Build agent progress data for frontend consumption.
    Returns (agent_progress_list, overall_progress_percent, current_phase_str).
    """
    from app.models.execution import ExecutionStatus

    agent_status = parse_agent_status(execution)
    selected_agents = parse_selected_agents(execution)

    agent_progress = []
    for agent_id in selected_agents:
        status_info = agent_status.get(agent_id, {})
        state = status_info.get("state", "waiting")
        agent_progress.append({
            "agent_name": AGENT_NAMES.get(agent_id, agent_id),
            "status": STATUS_MAP.get(state, state),
            "progress": status_info.get("progress", 0),
            "current_task": status_info.get("message", ""),
            "output_summary": status_info.get("message", ""),
        })

    total_agents = len(selected_agents)
    completed_agents = sum(
        1 for a in agent_status.values() if a.get("state") == "completed"
    )
    overall_progress = (
        int((completed_agents / total_agents) * 100) if total_agents > 0 else 0
    )

    current_phase = "Initializing..."
    if execution.current_agent:
        current_phase = f"Running {AGENT_NAMES.get(execution.current_agent, execution.current_agent)}"
    if execution.status == ExecutionStatus.COMPLETED:
        current_phase = "Completed"
        overall_progress = 100
    elif execution.status == ExecutionStatus.FAILED:
        current_phase = "Failed"
    elif execution.status == ExecutionStatus.WAITING_BR_VALIDATION:
        current_phase = "Waiting for BR Validation"
    elif execution.status == ExecutionStatus.WAITING_ARCHITECTURE_VALIDATION:
        current_phase = "Waiting for Architecture Validation"

    return agent_progress, overall_progress, current_phase
