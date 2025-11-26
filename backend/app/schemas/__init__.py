"""
Pydantic schemas package for data validation and serialization.
"""
from app.schemas.user import (
    User, UserCreate, UserUpdate, UserLogin, UserInDB,
    Token, TokenData
)
from app.schemas.project import (
    Project, ProjectCreate, ProjectUpdate, ProjectInDB
)
from app.schemas.agent import (
    Agent, AgentCreate, AgentUpdate, AgentInDB
)
from app.schemas.execution import (
    Execution, ExecutionCreate, ExecutionUpdate, ExecutionInDB,
    ExecutionLog, ExecutionProgress
)
from app.schemas.output import (
    Output, OutputCreate, OutputInDB
)

# V2 Artifacts System
from app.schemas.artifact import (
    # Enums
    ArtifactTypeEnum, ArtifactStatusEnum, GateStatusEnum, QuestionStatusEnum,
    # Artifact schemas
    ArtifactBase, ArtifactCreate, ArtifactUpdate, ArtifactStatusUpdate,
    ArtifactResponse, ArtifactListResponse,
    # Gate schemas
    GateBase, GateCreate, GateStatusUpdate, GateResponse, GateListResponse,
    # Question schemas
    QuestionBase, QuestionCreate, QuestionAnswer, QuestionResponse, QuestionListResponse,
    # Graph schemas
    GraphNode, GraphEdge, DependencyGraph,
    # Context schema
    AgentContext,
    # Init schemas
    InitializeGatesRequest, InitializeGatesResponse,
)

__all__ = [
    # User schemas
    "User", "UserCreate", "UserUpdate", "UserLogin", "UserInDB",
    "Token", "TokenData",
    # Project schemas
    "Project", "ProjectCreate", "ProjectUpdate", "ProjectInDB",
    # Agent schemas
    "Agent", "AgentCreate", "AgentUpdate", "AgentInDB",
    # Execution schemas
    "Execution", "ExecutionCreate", "ExecutionUpdate", "ExecutionInDB",
    "ExecutionLog", "ExecutionProgress",
    # Output schemas
    "Output", "OutputCreate", "OutputInDB",
    # V2 Artifact Enums
    "ArtifactTypeEnum", "ArtifactStatusEnum", "GateStatusEnum", "QuestionStatusEnum",
    # V2 Artifact schemas
    "ArtifactBase", "ArtifactCreate", "ArtifactUpdate", "ArtifactStatusUpdate",
    "ArtifactResponse", "ArtifactListResponse",
    # V2 Gate schemas
    "GateBase", "GateCreate", "GateStatusUpdate", "GateResponse", "GateListResponse",
    # V2 Question schemas
    "QuestionBase", "QuestionCreate", "QuestionAnswer", "QuestionResponse", "QuestionListResponse",
    # V2 Graph schemas
    "GraphNode", "GraphEdge", "DependencyGraph",
    # V2 Context
    "AgentContext",
    # V2 Init
    "InitializeGatesRequest", "InitializeGatesResponse",
]
