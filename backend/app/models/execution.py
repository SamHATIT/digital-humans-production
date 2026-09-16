"""
Execution model for tracking agent execution runs.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, Enum, JSON, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ExecutionStatus(str, enum.Enum):
    """Execution status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_BR_VALIDATION = "waiting_br_validation"
    WAITING_ARCHITECTURE_VALIDATION = "waiting_architecture_validation"
    # P2-Full: Configurable validation gates
    WAITING_EXPERT_VALIDATION = "waiting_expert_validation"
    WAITING_SDS_VALIDATION = "waiting_sds_validation"
    WAITING_BUILD_VALIDATION = "waiting_build_validation"


class Execution(Base):
    """Execution model for tracking multi-agent execution runs."""

    __tablename__ = "executions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Execution status and progress
    status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, nullable=False)
    progress = Column(Integer, default=0)  # Progress percentage (0-100)
    current_agent = Column(String)  # Currently executing agent name

    # PM Orchestrator specific fields
    selected_agents = Column(JSON)  # List of agent IDs selected for execution
    agent_execution_status = Column(JSON)  # Detailed status per agent {agent_id: {state, progress, message}}

    # Results
    sds_document_path = Column(String(500))  # Path to generated SDS document
    total_tokens_used = Column(Integer, default=0)  # Total tokens used across all agents
    total_cost = Column(Float, default=0.0)  # Total cost of execution

    # Timing
    duration_seconds = Column(Integer)  # Total execution duration
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Logs
    logs = Column(Text)  # JSON array of log entries stored as text
    
    # Resume capability
    last_completed_phase = Column(String(50))  # Last successfully completed phase for resume

    # State Machine (granular phase tracking — I1.2)
    execution_state = Column(String(60), default="draft", index=True)
    state_updated_at = Column(DateTime(timezone=True))
    state_history = Column(JSON, default=list)  # List of {from, to, at, metadata}

    # P2-Full: Configurable validation gates
    pending_validation = Column(JSONB, nullable=True)  # Current gate info when paused
    validation_history = Column(JSONB, default=list)    # List of past validation decisions

    # VAGUE 3 / §4 — selection des experts SDS, decidee par Marcus en fin de
    # phase 3 et **persistee** (contrainte 2, arbitrage Sam).
    #
    # Colonne dediee, et non reutilisation de `selected_agents` : cette
    # derniere porte l'intention du client au lancement, qui fait autorite
    # (contrainte 4). L'ecraser avec la decision de Marcus effacerait
    # precisement ce qui doit primer sur lui.
    #
    # Forme : {"selected": [...], "excluded": {agent: justification},
    #          "decided_by": "user"|"architect"|"resumed", "signals": {...}}
    #
    # Relue par une reprise en `phase4` : la recalculer relancerait des experts
    # que Marcus avait ecartes.
    expert_selection = Column(JSONB, nullable=True)

    # VAGUE 1 / FILE C (PROD-04 = CAL-11, CAL-07) — identite du job ARQ qui
    # porte l'execution. Sans elle, le demarrage d'un worker ne pouvait juger
    # une execution RUNNING que sur son statut, et les marquait toutes FAILED,
    # y compris celles dont le job tournait dans un autre worker (mesure
    # 15/09 18:0x : 179 tuee par le redemarrage des workers de calibration).
    # Posee par la route AVANT l'enfilage (identifiant deterministe), relue par
    # le worker au demarrage (job present dans Redis ?) et a la prise du job
    # (est-ce bien le job courant de cette execution ?).
    arq_job_id = Column(String(64), nullable=True, index=True)
    # CAL-07 — file ARQ sur laquelle l'execution a ete enfilee, reutilisee par
    # les reprises pour ne pas changer de worker/profil en cours de route.
    arq_queue_name = Column(String(100), nullable=True)
    # CAL-07 — annulation cooperative : horodatage de la demande, relu par
    # l'orchestrateur entre deux agents.
    cancel_requested_at = Column(DateTime(timezone=True), nullable=True)

    # VAGUE 1 / FILE C (GL-10) — degradations subies par cette execution.
    #
    # Le 15/09, le RAG documentaire est tombe toute la journee sans que rien ne
    # le trace : impossible, le soir, de dire quelles executions avaient
    # travaille sans corpus et lesquelles il fallait rejouer. Forme :
    # [{"motif": "rag_unavailable", "detail": "...", "at": "2026-09-16T..."}].
    #
    # La poursuite sans corpus reste toleree (arbitrage Sam) — mais tracee.
    degraded = Column(JSONB, nullable=True)

    # Relationships
    project = relationship("Project", back_populates="executions")
    user = relationship("User", back_populates="executions")
    execution_agents = relationship("ExecutionAgent", back_populates="execution", cascade="all, delete-orphan")
    outputs = relationship("Output", back_populates="execution", cascade="all, delete-orphan")

    # V2 Artifacts relationships
    artifacts = relationship("ExecutionArtifact", back_populates="execution", cascade="all, delete-orphan")
    validation_gates = relationship("ValidationGate", back_populates="execution", cascade="all, delete-orphan")
    agent_questions = relationship("AgentQuestion", back_populates="execution", cascade="all, delete-orphan")
    deliverable_items = relationship("DeliverableItem", back_populates="execution", cascade="all, delete-orphan")
    business_requirements = relationship("BusinessRequirement", back_populates="execution", cascade="all, delete-orphan")
    sds_versions = relationship("SDSVersion", back_populates="execution")
    change_requests = relationship("ChangeRequest", back_populates="execution")
    conversations = relationship("ProjectConversation", back_populates="execution")
    
    # ORCH-03a: Task executions for incremental build
    task_executions = relationship("TaskExecution", back_populates="execution", cascade="all, delete-orphan")
    
    # SDS v3: UC Requirement Sheets (micro-analysis by Nemo)
    uc_requirement_sheets = relationship("UCRequirementSheet", back_populates="execution", cascade="all, delete-orphan")
