"""
Database models package.
Import all models to ensure they are registered with SQLAlchemy.
"""
from app.models.user import User
from app.models.project import Project, ProjectStatus
from app.models.agent import Agent
from app.models.execution import Execution, ExecutionStatus
from app.models.execution_agent import ExecutionAgent, AgentExecutionStatus
from app.models.output import Output
from app.models.pm_orchestration import PMOrchestration, PMStatus
from app.models.agent_deliverable import AgentDeliverable
from app.models.document_fusion import DocumentFusion, FusionStatus
from app.models.training_content import TrainingContent, ContentStatus, FormattingStatus
from app.models.quality_gate import QualityGate, GateStatus
from app.models.agent_iteration import AgentIteration, IterationStatus

__all__ = [
    "User",
    "Project",
    "ProjectStatus",
    "Agent",
    "Execution",
    "ExecutionStatus",
    "ExecutionAgent",
    "AgentExecutionStatus",
    "Output",
    "PMOrchestration",
    "PMStatus",
    "AgentDeliverable",
    "DocumentFusion",
    "FusionStatus",
    "TrainingContent",
    "ContentStatus",
    "FormattingStatus",
    "QualityGate",
    "GateStatus",
    "AgentIteration",
    "IterationStatus",
]
