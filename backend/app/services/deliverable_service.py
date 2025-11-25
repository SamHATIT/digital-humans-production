"""
Deliverable Service - Handles agent deliverable operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.agent_deliverable import AgentDeliverable
from app.models.agent import Agent
from app.schemas.deliverable import (
    AgentDeliverableCreate,
    AgentDeliverableUpdate,
    AgentDeliverablePreview,
    AgentDeliverableFull
)


class DeliverableService:
    """Service for agent deliverable operations."""

    def __init__(self, db: Session):
        self.db = db

    def create_deliverable(self, data: AgentDeliverableCreate) -> AgentDeliverable:
        """Create new agent deliverable."""
        deliverable = AgentDeliverable(
            execution_id=data.execution_id,
            agent_id=data.agent_id,
            execution_agent_id=data.execution_agent_id,
            deliverable_type=data.deliverable_type,
            content=data.content,
            content_metadata=data.content_metadata,
            output_file_id=data.output_file_id
        )
        self.db.add(deliverable)
        self.db.commit()
        self.db.refresh(deliverable)
        return deliverable

    def get_by_id(self, deliverable_id: int) -> Optional[AgentDeliverable]:
        """Get deliverable by ID."""
        return self.db.query(AgentDeliverable).filter(
            AgentDeliverable.id == deliverable_id
        ).first()

    def get_by_execution(self, execution_id: int) -> List[AgentDeliverable]:
        """Get all deliverables for an execution."""
        return self.db.query(AgentDeliverable).filter(
            AgentDeliverable.execution_id == execution_id
        ).order_by(AgentDeliverable.created_at).all()

    def get_by_execution_and_agent(
        self,
        execution_id: int,
        agent_id: int
    ) -> List[AgentDeliverable]:
        """Get deliverables for specific execution and agent."""
        return self.db.query(AgentDeliverable).filter(
            and_(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.agent_id == agent_id
            )
        ).order_by(AgentDeliverable.created_at).all()

    def get_by_type(
        self,
        execution_id: int,
        deliverable_type: str
    ) -> Optional[AgentDeliverable]:
        """Get deliverable by execution and type."""
        return self.db.query(AgentDeliverable).filter(
            and_(
                AgentDeliverable.execution_id == execution_id,
                AgentDeliverable.deliverable_type == deliverable_type
            )
        ).first()

    def get_deliverable_previews(
        self,
        execution_id: int
    ) -> List[AgentDeliverablePreview]:
        """Get previews of all deliverables for an execution."""
        deliverables = self.db.query(AgentDeliverable, Agent).join(
            Agent,
            AgentDeliverable.agent_id == Agent.id
        ).filter(
            AgentDeliverable.execution_id == execution_id
        ).order_by(AgentDeliverable.created_at).all()

        previews = []
        for deliverable, agent in deliverables:
            preview = AgentDeliverablePreview(
                id=deliverable.id,
                agent_id=deliverable.agent_id,
                agent_name=agent.name,
                deliverable_type=deliverable.deliverable_type,
                content_preview=deliverable.content[:500] if deliverable.content else "",
                content_size=len(deliverable.content) if deliverable.content else 0,
                content_metadata=deliverable.content_metadata,
                created_at=deliverable.created_at,
                download_url=f"/api/outputs/{deliverable.output_file_id}" if deliverable.output_file_id else None
            )
            previews.append(preview)

        return previews

    def get_full_deliverable(
        self,
        deliverable_id: int
    ) -> Optional[AgentDeliverableFull]:
        """Get full deliverable content."""
        deliverable = self.get_by_id(deliverable_id)
        if not deliverable:
            return None

        return AgentDeliverableFull(
            id=deliverable.id,
            deliverable_type=deliverable.deliverable_type,
            content=deliverable.content,
            content_metadata=deliverable.content_metadata,
            download_url=f"/api/outputs/{deliverable.output_file_id}" if deliverable.output_file_id else None,
            created_at=deliverable.created_at
        )

    def update_deliverable(
        self,
        deliverable_id: int,
        data: AgentDeliverableUpdate
    ) -> AgentDeliverable:
        """Update deliverable."""
        deliverable = self.get_by_id(deliverable_id)
        if not deliverable:
            raise ValueError(f"Deliverable {deliverable_id} not found")

        if data.content is not None:
            deliverable.content = data.content
        if data.content_metadata is not None:
            deliverable.content_metadata = data.content_metadata
        if data.output_file_id is not None:
            deliverable.output_file_id = data.output_file_id

        self.db.commit()
        self.db.refresh(deliverable)
        return deliverable

    def delete_deliverable(self, deliverable_id: int) -> bool:
        """Delete deliverable."""
        deliverable = self.get_by_id(deliverable_id)
        if not deliverable:
            return False

        self.db.delete(deliverable)
        self.db.commit()
        return True
