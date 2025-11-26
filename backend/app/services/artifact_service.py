"""
Artifact Service for V2 architecture
Handles CRUD operations and business logic for artifacts, gates, and questions
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from app.models.artifact import (
    ExecutionArtifact, ValidationGate, AgentQuestion,
    ArtifactType, ArtifactStatus, GateStatus, QuestionStatus
)
from app.schemas.artifact import (
    ArtifactCreate, ArtifactUpdate, ArtifactStatusUpdate,
    GateCreate, GateStatusUpdate,
    QuestionCreate, QuestionAnswer,
    GraphNode, GraphEdge, DependencyGraph
)


class ArtifactService:
    """Service for managing execution artifacts"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============ ARTIFACT CRUD ============
    
    def create_artifact(self, data: ArtifactCreate) -> ExecutionArtifact:
        """Create a new artifact"""
        artifact = ExecutionArtifact(
            execution_id=data.execution_id,
            artifact_type=data.artifact_type.value,
            artifact_code=data.artifact_code,
            title=data.title,
            producer_agent=data.producer_agent,
            content=data.content,
            parent_refs=data.parent_refs,
            version=1,
            is_current=True,
            status=ArtifactStatus.DRAFT
        )
        self.db.add(artifact)
        self.db.commit()
        self.db.refresh(artifact)
        return artifact
    
    def get_artifact(self, artifact_code: str, execution_id: int, version: Optional[int] = None) -> Optional[ExecutionArtifact]:
        """Get an artifact by code, optionally specific version"""
        query = self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.artifact_code == artifact_code
        )
        if version:
            query = query.filter(ExecutionArtifact.version == version)
        else:
            query = query.filter(ExecutionArtifact.is_current == True)
        return query.first()
    
    def get_artifact_by_id(self, artifact_id: int) -> Optional[ExecutionArtifact]:
        """Get an artifact by ID"""
        return self.db.query(ExecutionArtifact).filter(ExecutionArtifact.id == artifact_id).first()
    
    def list_artifacts(
        self,
        execution_id: int,
        artifact_type: Optional[str] = None,
        status: Optional[str] = None,
        current_only: bool = True
    ) -> List[ExecutionArtifact]:
        """List artifacts with optional filters"""
        query = self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id
        )
        if current_only:
            query = query.filter(ExecutionArtifact.is_current == True)
        if artifact_type:
            query = query.filter(ExecutionArtifact.artifact_type == artifact_type)
        if status:
            query = query.filter(ExecutionArtifact.status == status)
        return query.order_by(ExecutionArtifact.artifact_code).all()
    
    def update_artifact(self, artifact_code: str, execution_id: int, data: ArtifactUpdate) -> ExecutionArtifact:
        """Update an artifact (creates new version)"""
        current = self.get_artifact(artifact_code, execution_id)
        if not current:
            raise ValueError(f"Artifact {artifact_code} not found")
        
        # Mark current as superseded
        current.is_current = False
        current.status = ArtifactStatus.SUPERSEDED
        
        # Create new version
        new_artifact = ExecutionArtifact(
            execution_id=execution_id,
            artifact_type=current.artifact_type,
            artifact_code=artifact_code,
            title=data.title or current.title,
            producer_agent=current.producer_agent,
            content=data.content if data.content is not None else current.content,
            parent_refs=data.parent_refs if data.parent_refs is not None else current.parent_refs,
            version=current.version + 1,
            is_current=True,
            status=ArtifactStatus.DRAFT
        )
        self.db.add(new_artifact)
        self.db.commit()
        self.db.refresh(new_artifact)
        return new_artifact
    
    def update_artifact_status(
        self,
        artifact_code: str,
        execution_id: int,
        data: ArtifactStatusUpdate,
        changed_by: str = "user"
    ) -> ExecutionArtifact:
        """Update artifact status"""
        artifact = self.get_artifact(artifact_code, execution_id)
        if not artifact:
            raise ValueError(f"Artifact {artifact_code} not found")
        
        artifact.status = data.status.value
        artifact.status_changed_at = datetime.utcnow()
        artifact.status_changed_by = changed_by
        if data.rejection_reason:
            artifact.rejection_reason = data.rejection_reason
        
        self.db.commit()
        self.db.refresh(artifact)
        return artifact
    
    def get_artifacts_stats(self, execution_id: int) -> Dict[str, Any]:
        """Get artifact statistics for an execution"""
        artifacts = self.list_artifacts(execution_id, current_only=True)
        
        by_type = {}
        by_status = {}
        for a in artifacts:
            by_type[a.artifact_type] = by_type.get(a.artifact_type, 0) + 1
            by_status[a.status] = by_status.get(a.status, 0) + 1
        
        return {
            "total": len(artifacts),
            "by_type": by_type,
            "by_status": by_status
        }
    
    # ============ CONTEXT FOR AGENTS ============
    
    def get_context_for_agent(self, execution_id: int, agent_id: str) -> Dict[str, Any]:
        """Get minimal context required for an agent"""
        context = {
            "execution_id": execution_id,
            "agent_id": agent_id,
            "artifacts": [],
            "pending_questions": [],
            "answered_questions": []
        }
        
        # Define what each agent needs
        agent_artifact_needs = {
            "ba": ["requirement"],
            "architect": ["requirement", "business_req", "use_case"],
            "apex": ["spec", "adr", "use_case", "business_req"],
            "lwc": ["spec", "adr", "use_case", "business_req"],
            "admin": ["spec", "adr", "use_case", "business_req"],
            "qa": ["spec", "code", "config"],
            "devops": ["code", "config", "test"],
            "data": ["spec", "business_req"],
            "trainer": ["use_case", "business_req", "doc"],
            "pm": ["requirement", "business_req", "use_case", "adr", "spec"]
        }
        
        needed_types = agent_artifact_needs.get(agent_id, [])
        
        # Get relevant artifacts
        for artifact_type in needed_types:
            artifacts = self.list_artifacts(execution_id, artifact_type=artifact_type, status=ArtifactStatus.APPROVED)
            context["artifacts"].extend([a.to_dict() for a in artifacts])
        
        # Get questions for this agent
        pending = self.list_questions(execution_id, to_agent=agent_id, status=QuestionStatus.PENDING)
        answered = self.list_questions(execution_id, from_agent=agent_id, status=QuestionStatus.ANSWERED)
        
        context["pending_questions"] = [q.to_dict() for q in pending]
        context["answered_questions"] = [q.to_dict() for q in answered]
        
        return context
    
    # ============ VALIDATION GATES ============
    
    def initialize_gates(self, execution_id: int) -> List[ValidationGate]:
        """Initialize all 6 gates for an execution"""
        gates = []
        for gate_def in ValidationGate.get_gate_definitions():
            gate = ValidationGate(
                execution_id=execution_id,
                gate_number=gate_def["gate_number"],
                gate_name=gate_def["gate_name"],
                phase=gate_def["phase"],
                artifact_types=gate_def["artifact_types"],
                status=GateStatus.PENDING
            )
            self.db.add(gate)
            gates.append(gate)
        
        self.db.commit()
        for g in gates:
            self.db.refresh(g)
        return gates
    
    def get_gate(self, execution_id: int, gate_number: int) -> Optional[ValidationGate]:
        """Get a specific gate"""
        return self.db.query(ValidationGate).filter(
            ValidationGate.execution_id == execution_id,
            ValidationGate.gate_number == gate_number
        ).first()
    
    def list_gates(self, execution_id: int) -> List[ValidationGate]:
        """List all gates for an execution"""
        return self.db.query(ValidationGate).filter(
            ValidationGate.execution_id == execution_id
        ).order_by(ValidationGate.gate_number).all()
    
    def update_gate_artifacts_count(self, execution_id: int, gate_number: int) -> ValidationGate:
        """Update the artifacts count for a gate"""
        gate = self.get_gate(execution_id, gate_number)
        if not gate:
            raise ValueError(f"Gate {gate_number} not found")
        
        # Count current artifacts of the gate's types
        count = self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.is_current == True,
            ExecutionArtifact.artifact_type.in_(gate.artifact_types)
        ).count()
        
        gate.artifacts_count = count
        self.db.commit()
        self.db.refresh(gate)
        return gate
    
    def submit_gate_for_review(self, execution_id: int, gate_number: int) -> ValidationGate:
        """Submit a gate for user review"""
        gate = self.get_gate(execution_id, gate_number)
        if not gate:
            raise ValueError(f"Gate {gate_number} not found")
        
        # Update artifacts count
        self.update_gate_artifacts_count(execution_id, gate_number)
        
        # Update all related artifacts to pending_review
        self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.is_current == True,
            ExecutionArtifact.artifact_type.in_(gate.artifact_types),
            ExecutionArtifact.status == ArtifactStatus.DRAFT
        ).update({
            "status": ArtifactStatus.PENDING_REVIEW,
            "status_changed_at": datetime.utcnow()
        }, synchronize_session=False)
        
        gate.status = GateStatus.READY
        gate.submitted_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(gate)
        return gate
    
    def approve_gate(self, execution_id: int, gate_number: int, validated_by: str = "user") -> ValidationGate:
        """Approve a gate and all its artifacts"""
        gate = self.get_gate(execution_id, gate_number)
        if not gate:
            raise ValueError(f"Gate {gate_number} not found")
        
        # Approve all related artifacts
        self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.is_current == True,
            ExecutionArtifact.artifact_type.in_(gate.artifact_types),
            ExecutionArtifact.status == ArtifactStatus.PENDING_REVIEW
        ).update({
            "status": ArtifactStatus.APPROVED,
            "status_changed_at": datetime.utcnow(),
            "status_changed_by": validated_by
        }, synchronize_session=False)
        
        gate.status = GateStatus.APPROVED
        gate.validated_at = datetime.utcnow()
        gate.validated_by = validated_by
        self.db.commit()
        self.db.refresh(gate)
        return gate
    
    def reject_gate(self, execution_id: int, gate_number: int, reason: str, validated_by: str = "user") -> ValidationGate:
        """Reject a gate"""
        gate = self.get_gate(execution_id, gate_number)
        if not gate:
            raise ValueError(f"Gate {gate_number} not found")
        
        # Mark related artifacts as rejected
        self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.is_current == True,
            ExecutionArtifact.artifact_type.in_(gate.artifact_types),
            ExecutionArtifact.status == ArtifactStatus.PENDING_REVIEW
        ).update({
            "status": ArtifactStatus.REJECTED,
            "status_changed_at": datetime.utcnow(),
            "status_changed_by": validated_by,
            "rejection_reason": reason
        }, synchronize_session=False)
        
        gate.status = GateStatus.REJECTED
        gate.validated_at = datetime.utcnow()
        gate.validated_by = validated_by
        gate.rejection_reason = reason
        self.db.commit()
        self.db.refresh(gate)
        return gate
    
    def get_gates_progress(self, execution_id: int) -> Dict[str, Any]:
        """Get progress across all gates"""
        gates = self.list_gates(execution_id)
        if not gates:
            return {"gates": [], "current_gate": None, "progress_percent": 0.0}
        
        approved_count = sum(1 for g in gates if g.status == GateStatus.APPROVED)
        current_gate = None
        for g in gates:
            if g.status != GateStatus.APPROVED:
                current_gate = g.gate_number
                break
        
        return {
            "gates": [g.to_dict() for g in gates],
            "current_gate": current_gate,
            "progress_percent": (approved_count / len(gates)) * 100
        }
    
    # ============ AGENT QUESTIONS ============
    
    def create_question(self, data: QuestionCreate) -> AgentQuestion:
        """Create a new question between agents"""
        question = AgentQuestion(
            execution_id=data.execution_id,
            question_code=data.question_code,
            from_agent=data.from_agent,
            to_agent=data.to_agent,
            context=data.context,
            question=data.question,
            related_artifacts=data.related_artifacts,
            status=QuestionStatus.PENDING
        )
        self.db.add(question)
        self.db.commit()
        self.db.refresh(question)
        return question
    
    def get_question(self, question_code: str, execution_id: int) -> Optional[AgentQuestion]:
        """Get a question by code"""
        return self.db.query(AgentQuestion).filter(
            AgentQuestion.execution_id == execution_id,
            AgentQuestion.question_code == question_code
        ).first()
    
    def list_questions(
        self,
        execution_id: int,
        from_agent: Optional[str] = None,
        to_agent: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[AgentQuestion]:
        """List questions with optional filters"""
        query = self.db.query(AgentQuestion).filter(
            AgentQuestion.execution_id == execution_id
        )
        if from_agent:
            query = query.filter(AgentQuestion.from_agent == from_agent)
        if to_agent:
            query = query.filter(AgentQuestion.to_agent == to_agent)
        if status:
            query = query.filter(AgentQuestion.status == status)
        return query.order_by(AgentQuestion.created_at).all()
    
    def answer_question(self, question_code: str, execution_id: int, data: QuestionAnswer) -> AgentQuestion:
        """Answer a question"""
        question = self.get_question(question_code, execution_id)
        if not question:
            raise ValueError(f"Question {question_code} not found")
        
        question.answer = data.answer
        question.recommendation = data.recommendation
        question.answered_at = datetime.utcnow()
        question.status = QuestionStatus.ANSWERED
        
        self.db.commit()
        self.db.refresh(question)
        return question
    
    def get_next_question_code(self, execution_id: int) -> str:
        """Generate the next question code (Q-001, Q-002, etc.)"""
        last = self.db.query(AgentQuestion).filter(
            AgentQuestion.execution_id == execution_id
        ).order_by(AgentQuestion.question_code.desc()).first()
        
        if not last:
            return "Q-001"
        
        num = int(last.question_code.split("-")[1]) + 1
        return f"Q-{num:03d}"
    
    # ============ DEPENDENCY GRAPH ============
    
    def get_dependency_graph(self, execution_id: int) -> DependencyGraph:
        """Build the dependency graph for visualization"""
        artifacts = self.list_artifacts(execution_id, current_only=True)
        
        nodes = []
        edges = []
        artifact_map = {a.artifact_code: a for a in artifacts}
        
        for artifact in artifacts:
            nodes.append(GraphNode(
                id=artifact.artifact_code,
                type=artifact.artifact_type,
                title=artifact.title,
                status=artifact.status,
                producer=artifact.producer_agent
            ))
            
            # Create edges from parent_refs
            if artifact.parent_refs:
                for parent_code in artifact.parent_refs:
                    if parent_code in artifact_map:
                        edges.append(GraphEdge(
                            source=parent_code,
                            target=artifact.artifact_code,
                            relation="derives_from"
                        ))
        
        return DependencyGraph(nodes=nodes, edges=edges)
    
    # ============ UTILITY METHODS ============
    
    def get_next_artifact_code(self, execution_id: int, artifact_type: str) -> str:
        """Generate the next artifact code for a type"""
        prefix_map = {
            "requirement": "REQ",
            "business_req": "BR",
            "use_case": "UC",
            "question": "Q",
            "adr": "ADR",
            "spec": "SPEC",
            "code": "CODE",
            "config": "CFG",
            "test": "TEST",
            "doc": "DOC"
        }
        prefix = prefix_map.get(artifact_type, "ART")
        
        last = self.db.query(ExecutionArtifact).filter(
            ExecutionArtifact.execution_id == execution_id,
            ExecutionArtifact.artifact_type == artifact_type
        ).order_by(ExecutionArtifact.artifact_code.desc()).first()
        
        if not last:
            return f"{prefix}-001"
        
        num = int(last.artifact_code.split("-")[1]) + 1
        return f"{prefix}-{num:03d}"
