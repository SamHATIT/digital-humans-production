"""
Quality Gate Service - Handles quality gate checks and iterations.
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.quality_gate import QualityGate, GateStatus
from app.models.agent_iteration import AgentIteration, IterationStatus
from app.models.agent_deliverable import AgentDeliverable
from app.models.agent import Agent
from app.schemas.quality_gate import (
    QualityGateCreate,
    QualityGateResponse,
    QualityGateSummary,
    IterationCreate,
    IterationResponse
)


class QualityGateService:
    """Service for quality gate operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_quality_gate(self, data: QualityGateCreate) -> QualityGate:
        """Create new quality gate check."""
        gate = QualityGate(
            execution_id=data.execution_id,
            agent_id=data.agent_id,
            execution_agent_id=data.execution_agent_id,
            gate_type=data.gate_type,
            expected_value=data.expected_value,
            actual_value=data.actual_value,
            status=data.status,
            validation_details=data.validation_details,
            error_message=data.error_message
        )
        self.db.add(gate)
        self.db.commit()
        self.db.refresh(gate)
        return gate

    def get_by_execution(self, execution_id: int) -> List[QualityGate]:
        """Get all quality gates for an execution."""
        return self.db.query(QualityGate).filter(
            QualityGate.execution_id == execution_id
        ).order_by(QualityGate.checked_at).all()

    def get_by_execution_and_agent(
        self,
        execution_id: int,
        agent_id: int
    ) -> List[QualityGate]:
        """Get quality gates for specific execution and agent."""
        return self.db.query(QualityGate).filter(
            and_(
                QualityGate.execution_id == execution_id,
                QualityGate.agent_id == agent_id
            )
        ).order_by(QualityGate.checked_at).all()

    def get_summary(
        self,
        execution_id: int,
        agent_id: int
    ) -> QualityGateSummary:
        """Get quality gate summary for an agent."""
        gates = self.get_by_execution_and_agent(execution_id, agent_id)
        agent = self.db.query(Agent).filter(Agent.id == agent_id).first()

        passed_count = sum(1 for g in gates if g.status == GateStatus.PASSED)
        failed_count = sum(1 for g in gates if g.status == GateStatus.FAILED)

        return QualityGateSummary(
            agent_id=agent_id,
            agent_name=agent.name if agent else "Unknown",
            total_gates=len(gates),
            passed_gates=passed_count,
            failed_gates=failed_count,
            all_passed=failed_count == 0,
            gates=[QualityGateResponse.from_orm(g) for g in gates]
        )

    def check_all_passed(self, execution_id: int, agent_id: int) -> bool:
        """Check if all quality gates passed for an agent."""
        gates = self.get_by_execution_and_agent(execution_id, agent_id)
        return all(g.status == GateStatus.PASSED for g in gates)

    # Specific quality gate checks

    def check_erd_present(
        self,
        execution_id: int,
        agent_id: int
    ) -> QualityGate:
        """Check if ERD diagram is present in deliverables."""
        erd = self.db.query(AgentDeliverable).filter(
            and_(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.agent_id == agent_id,
                AgentDeliverable.deliverable_type == 'erd_diagram'
            )
        ).first()

        gate_data = QualityGateCreate(
            execution_id=execution_id,
            agent_id=agent_id,
            gate_type='erd_present',
            expected_value='true',
            actual_value='true' if erd else 'false',
            status=GateStatus.PASSED if erd else GateStatus.FAILED,
            error_message=None if erd else 'ERD diagram not found in deliverables'
        )

        return self.create_quality_gate(gate_data)

    def check_process_flows_count(
        self,
        execution_id: int,
        agent_id: int,
        minimum: int = 3
    ) -> QualityGate:
        """Check if minimum number of process flows exist."""
        flows = self.db.query(AgentDeliverable).filter(
            and_(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.agent_id == agent_id,
                AgentDeliverable.deliverable_type == 'process_flows'
            )
        ).first()

        if flows and flows.content_metadata:
            flows_count = flows.content_metadata.get('flows_count', 0)
        else:
            flows_count = 0

        passed = flows_count >= minimum

        gate_data = QualityGateCreate(
            execution_id=execution_id,
            agent_id=agent_id,
            gate_type='process_flows_count',
            expected_value=str(minimum),
            actual_value=str(flows_count),
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            validation_details={'flows_count': flows_count, 'minimum_required': minimum},
            error_message=None if passed else f'Only {flows_count} flows found, need at least {minimum}'
        )

        return self.create_quality_gate(gate_data)

    def check_hld_size(
        self,
        execution_id: int,
        agent_id: int,
        minimum_pages: int = 100
    ) -> QualityGate:
        """Check if HLD document meets minimum page count."""
        hld = self.db.query(AgentDeliverable).filter(
            and_(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.agent_id == agent_id,
                AgentDeliverable.deliverable_type == 'hld_document'
            )
        ).first()

        if hld and hld.content_metadata:
            page_count = hld.content_metadata.get('page_count', 0)
        else:
            page_count = 0

        passed = page_count >= minimum_pages

        gate_data = QualityGateCreate(
            execution_id=execution_id,
            agent_id=agent_id,
            gate_type='hld_size',
            expected_value=f'{minimum_pages}+ pages',
            actual_value=f'{page_count} pages',
            status=GateStatus.PASSED if passed else GateStatus.FAILED,
            validation_details={'page_count': page_count, 'minimum_required': minimum_pages},
            error_message=None if passed else f'HLD only {page_count} pages, need at least {minimum_pages}'
        )

        return self.create_quality_gate(gate_data)

    # Iteration management

    def create_iteration(self, data: IterationCreate) -> AgentIteration:
        """Create new iteration (retry attempt)."""
        iteration = AgentIteration(
            execution_id=data.execution_id,
            agent_id=data.agent_id,
            iteration_number=data.iteration_number,
            quality_gate_id=data.quality_gate_id,
            retry_reason=data.retry_reason,
            status=IterationStatus.RETRYING
        )
        self.db.add(iteration)
        self.db.commit()
        self.db.refresh(iteration)
        return iteration

    def get_iterations(
        self,
        execution_id: int,
        agent_id: int
    ) -> List[AgentIteration]:
        """Get all iterations for an agent in an execution."""
        return self.db.query(AgentIteration).filter(
            and_(
                AgentIteration.execution_id == execution_id,
                AgentIteration.agent_id == agent_id
            )
        ).order_by(AgentIteration.iteration_number).all()

    def get_iteration_count(
        self,
        execution_id: int,
        agent_id: int
    ) -> int:
        """Get number of iterations for an agent."""
        return self.db.query(AgentIteration).filter(
            and_(
                AgentIteration.execution_id == execution_id,
                AgentIteration.agent_id == agent_id
            )
        ).count()

    def complete_iteration(
        self,
        iteration_id: int,
        new_deliverable_id: Optional[int] = None,
        status: IterationStatus = IterationStatus.COMPLETED
    ) -> AgentIteration:
        """Mark iteration as completed."""
        iteration = self.db.query(AgentIteration).filter(
            AgentIteration.id == iteration_id
        ).first()

        if not iteration:
            raise ValueError(f"Iteration {iteration_id} not found")

        iteration.status = status
        iteration.new_deliverable_id = new_deliverable_id
        iteration.completed_at = self.db.func.now()

        self.db.commit()
        self.db.refresh(iteration)
        return iteration

    def should_retry(
        self,
        execution_id: int,
        agent_id: int,
        max_iterations: int = 2
    ) -> bool:
        """Check if agent should retry (hasn't exceeded max iterations)."""
        iteration_count = self.get_iteration_count(execution_id, agent_id)
        return iteration_count < max_iterations
