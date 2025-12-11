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
from app.models.deliverable_item import DeliverableItem

# BR Validation
from app.models.business_requirement import (
    BusinessRequirement,
    BRStatus,
    BRPriority,
    BRSource,
)

# V2 Artifacts System
from app.models.artifact import (
    ExecutionArtifact,
    ValidationGate,
    AgentQuestion,
    ArtifactType,
    ArtifactStatus,
    GateStatus as ArtifactGateStatus,  # Alias to avoid conflict with quality_gate.GateStatus
    QuestionStatus,
)

# Post-SDS Workflow
from app.models.sds_version import SDSVersion

# ORCH-03a: Incremental Build
from app.models.task_execution import TaskExecution, TaskStatus
from app.models.llm_interaction import LLMInteraction
from app.models.change_request import ChangeRequest, CRStatus, CRCategory, CRPriority
from app.models.project_conversation import ProjectConversation

__all__ = [
    # Core models
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
    "DeliverableItem",
    # BR Validation
    "BusinessRequirement",
    "BRStatus",
    "BRPriority",
    "BRSource",
    # V2 Artifacts
    "ExecutionArtifact",
    "ValidationGate",
    "AgentQuestion",
    "ArtifactType",
    "ArtifactStatus",
    "ArtifactGateStatus",
    "QuestionStatus",
    # Post-SDS Workflow
    "SDSVersion",
    "ChangeRequest",
    "CRStatus",
    "CRCategory",
    "CRPriority",
    "ProjectConversation",
    # Incremental Build
    "TaskExecution",
    "TaskStatus",
    # Audit Logging
    "AuditLog",
    "ActorType",
    "ActionCategory",
]

# CORE-001: Audit Logging
from app.models.audit import AuditLog, ActorType, ActionCategory
