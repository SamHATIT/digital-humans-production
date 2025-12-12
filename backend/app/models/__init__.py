"""
Database models package.
Import all models to ensure they are registered with SQLAlchemy.
"""
from app.models.user import User
from app.models.project import Project, ProjectStatus, ProjectType, TargetObjective
from app.models.project_credential import ProjectCredential, CredentialType
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
    GateStatus as ArtifactGateStatus,
)

# Post-SDS Workflow
from app.models.sds_version import SDSVersion

# ORCH-03a: Incremental Build
from app.models.task_execution import TaskExecution, TaskStatus
from app.models.llm_interaction import LLMInteraction
from app.models.change_request import ChangeRequest, CRStatus, CRCategory, CRPriority
from app.models.project_conversation import ProjectConversation

# CORE-001: Audit Logging
from app.models.audit import AuditLog, ActorType, ActionCategory

__all__ = [
    # Core models
    "User",
    "Project",
    "ProjectStatus",
    "ProjectType",
    "TargetObjective",
    "ProjectCredential",
    "CredentialType",
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
    "LLMInteraction",
    # Audit Logging
    "AuditLog",
    "ActorType",
    "ActionCategory",
]

# Phase 6: WBS Task Types
from app.models.wbs_task_type import (
    WBSTaskType,
    WBSTaskExecutor,
    TASK_TYPE_CONFIG,
    get_task_config,
    is_automatable,
    get_executor,
    get_automatable_task_types,
    get_manual_task_types,
    infer_task_type,
)

__all__.extend([
    "WBSTaskType",
    "WBSTaskExecutor",
    "TASK_TYPE_CONFIG",
    "get_task_config",
    "is_automatable",
    "get_executor",
    "get_automatable_task_types",
    "get_manual_task_types",
    "infer_task_type",
])

# Section 9: Subscription/Freemium Model
from app.models.subscription import (
    SubscriptionTier,
    TIER_FEATURES,
    get_tier_config,
    get_tier_features,
    has_feature,
    get_limit,
    get_required_tier,
)

# Section 6.2: Project Environments (SFDX)
from app.models.project_environment import (
    ProjectEnvironment,
    EnvironmentType,
    AuthMethod,
    ConnectionStatus,
)

# Section 6.3: Project Git Config
from app.models.project_git_config import (
    ProjectGitConfig,
    GitProvider,
    BranchStrategy,
    GitConnectionStatus,
)

# Section 6.4: SDS Templates
from app.models.sds_template import (
    SDSTemplate,
    DEFAULT_SDS_TEMPLATE,
    SYSTEM_TEMPLATES,
)

__all__.extend([
    # Subscription
    "SubscriptionTier",
    "TIER_FEATURES",
    "get_tier_config",
    "get_tier_features",
    "has_feature",
    "get_limit",
    "get_required_tier",
    # Project Environments
    "ProjectEnvironment",
    "EnvironmentType",
    "AuthMethod",
    "ConnectionStatus",
    # Project Git Config
    "ProjectGitConfig",
    "GitProvider",
    "BranchStrategy",
    "GitConnectionStatus",
    # SDS Templates
    "SDSTemplate",
    "DEFAULT_SDS_TEMPLATE",
    "SYSTEM_TEMPLATES",
])
