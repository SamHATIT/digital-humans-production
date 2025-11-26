"""
Artifact models for V2 architecture
Digital Humans - Traceable Artifacts System
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ArtifactType:
    """Artifact type constants"""
    REQUIREMENT = 'requirement'
    BUSINESS_REQ = 'business_req'
    USE_CASE = 'use_case'
    QUESTION = 'question'
    ADR = 'adr'
    SPEC = 'spec'
    CODE = 'code'
    CONFIG = 'config'
    TEST = 'test'
    DOC = 'doc'
    
    ALL = [REQUIREMENT, BUSINESS_REQ, USE_CASE, QUESTION, ADR, SPEC, CODE, CONFIG, TEST, DOC]


class ArtifactStatus:
    """Artifact status constants"""
    DRAFT = 'draft'
    PENDING_REVIEW = 'pending_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    SUPERSEDED = 'superseded'
    
    ALL = [DRAFT, PENDING_REVIEW, APPROVED, REJECTED, SUPERSEDED]


class GateStatus:
    """Validation gate status constants"""
    PENDING = 'pending'
    READY = 'ready'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    
    ALL = [PENDING, READY, APPROVED, REJECTED]


class QuestionStatus:
    """Question status constants"""
    PENDING = 'pending'
    ANSWERED = 'answered'
    
    ALL = [PENDING, ANSWERED]


class ExecutionArtifact(Base):
    """
    Stores all artifacts produced by agents.
    
    Artifacts are versioned and traceable through parent_refs.
    Each artifact has a unique code (e.g., UC-001, BR-002, SPEC-003).
    """
    __tablename__ = 'execution_artifacts'
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey('executions.id', ondelete='CASCADE'), nullable=False)
    
    # Classification
    artifact_type = Column(String(50), nullable=False)
    artifact_code = Column(String(20), nullable=False)
    title = Column(String(255), nullable=False)
    
    # Producer and versioning
    producer_agent = Column(String(20), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_current = Column(Boolean, nullable=False, default=True)
    
    # Content (flexible JSON structure)
    content = Column(JSONB, nullable=False)
    
    # Traceability - references to parent artifacts
    parent_refs = Column(JSONB)  # e.g., ["BR-001", "UC-003"]
    
    # Validation status
    status = Column(String(20), nullable=False, default=ArtifactStatus.DRAFT)
    status_changed_at = Column(DateTime(timezone=True))
    status_changed_by = Column(String(50))
    rejection_reason = Column(Text)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship
    execution = relationship("Execution", back_populates="artifacts")
    
    def __repr__(self):
        return f"<Artifact {self.artifact_code} v{self.version} ({self.status})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "artifact_type": self.artifact_type,
            "artifact_code": self.artifact_code,
            "title": self.title,
            "producer_agent": self.producer_agent,
            "version": self.version,
            "is_current": self.is_current,
            "content": self.content,
            "parent_refs": self.parent_refs,
            "status": self.status,
            "status_changed_at": self.status_changed_at.isoformat() if self.status_changed_at else None,
            "status_changed_by": self.status_changed_by,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ValidationGate(Base):
    """
    Manages the 6 validation gates in the workflow.
    
    Gates:
    1. BR/UC Validation (Analyse)
    2. SDS/ADR Validation (Conception)
    3. Code/Config Validation (Réalisation)
    4. QA Validation (Test)
    5. Training Validation (Training)
    6. Deployment Validation (Déploiement)
    """
    __tablename__ = 'validation_gates'
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey('executions.id', ondelete='CASCADE'), nullable=False)
    
    # Gate identification
    gate_number = Column(Integer, nullable=False)
    gate_name = Column(String(50), nullable=False)
    phase = Column(String(50), nullable=False)
    
    # Artifacts managed by this gate
    artifact_types = Column(JSONB, nullable=False)  # e.g., ["business_req", "use_case"]
    artifacts_count = Column(Integer, default=0)
    
    # Status
    status = Column(String(20), nullable=False, default=GateStatus.PENDING)
    
    # Validation timestamps
    submitted_at = Column(DateTime(timezone=True))
    validated_at = Column(DateTime(timezone=True))
    validated_by = Column(String(50))
    rejection_reason = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    execution = relationship("Execution", back_populates="validation_gates")
    
    def __repr__(self):
        return f"<Gate {self.gate_number}: {self.gate_name} ({self.status})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "gate_number": self.gate_number,
            "gate_name": self.gate_name,
            "phase": self.phase,
            "artifact_types": self.artifact_types,
            "artifacts_count": self.artifacts_count,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "validated_by": self.validated_by,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
    
    @staticmethod
    def get_gate_definitions():
        """Returns the 6 gate definitions for initialization"""
        return [
            {"gate_number": 1, "gate_name": "BR/UC Validation", "phase": "Analyse", "artifact_types": ["business_req", "use_case"]},
            {"gate_number": 2, "gate_name": "SDS/ADR Validation", "phase": "Conception", "artifact_types": ["adr", "spec"]},
            {"gate_number": 3, "gate_name": "Code/Config Validation", "phase": "Réalisation", "artifact_types": ["code", "config"]},
            {"gate_number": 4, "gate_name": "QA Validation", "phase": "Test", "artifact_types": ["test"]},
            {"gate_number": 5, "gate_name": "Training Validation", "phase": "Training", "artifact_types": ["doc"]},
            {"gate_number": 6, "gate_name": "Deployment Validation", "phase": "Déploiement", "artifact_types": []},
        ]


class AgentQuestion(Base):
    """
    Manages synchronous questions between agents.
    
    When an agent needs information from another agent,
    they create a question and wait for the answer before proceeding.
    """
    __tablename__ = 'agent_questions'
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey('executions.id', ondelete='CASCADE'), nullable=False)
    
    # Question identification
    question_code = Column(String(20), nullable=False)  # e.g., Q-001
    
    # Participants
    from_agent = Column(String(20), nullable=False)
    to_agent = Column(String(20), nullable=False)
    
    # Question content
    context = Column(Text, nullable=False)
    question = Column(Text, nullable=False)
    related_artifacts = Column(JSONB)  # e.g., ["UC-012", "BR-003"]
    
    # Answer
    answer = Column(Text)
    recommendation = Column(Text)
    answered_at = Column(DateTime(timezone=True))
    
    # Status
    status = Column(String(20), nullable=False, default=QuestionStatus.PENDING)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationship
    execution = relationship("Execution", back_populates="agent_questions")
    
    def __repr__(self):
        return f"<Question {self.question_code}: {self.from_agent} -> {self.to_agent} ({self.status})>"
    
    def to_dict(self):
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "question_code": self.question_code,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "context": self.context,
            "question": self.question,
            "related_artifacts": self.related_artifacts,
            "answer": self.answer,
            "recommendation": self.recommendation,
            "answered_at": self.answered_at.isoformat() if self.answered_at else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
