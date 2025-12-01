"""
DeliverableItem model for database-first storage of individual items
(Use Cases, Gaps, Tasks, Test Cases, etc.)
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class DeliverableItem(Base):
    """
    Individual deliverable item (UC, Gap, Task, etc.)
    
    Implements database-first resilience: each item is saved immediately
    after LLM generation, preserving raw content even if parsing fails.
    """
    __tablename__ = "deliverable_items"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Agent identification
    agent_id = Column(String(50), nullable=False)  # 'ba', 'architect', 'qa', etc.
    
    # Item identification
    parent_ref = Column(String(100))      # 'BR-001', 'UC-001-01', etc. (source reference)
    item_id = Column(String(100), nullable=False)  # 'UC-001-01', 'GAP-001-01', etc.
    item_type = Column(String(50), nullable=False)  # 'use_case', 'gap', 'task', 'test_case'
    
    # Content - ALWAYS store raw for recovery
    content_parsed = Column(JSONB)        # Parsed content if successful
    content_raw = Column(Text)            # Raw content ALWAYS stored
    parse_success = Column(Boolean, default=False)
    parse_error = Column(Text)            # Error message if parsing failed
    
    # Metrics
    tokens_used = Column(Integer, default=0)
    model_used = Column(String(100))
    execution_time_seconds = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    execution = relationship("Execution", back_populates="deliverable_items")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('execution_id', 'item_id', name='uq_execution_item'),
    )
    
    def __repr__(self):
        return f"<DeliverableItem {self.item_id} ({self.item_type}) - parse_success={self.parse_success}>"
    
    @property
    def content(self):
        """Return parsed content if available, otherwise raw"""
        return self.content_parsed if self.parse_success else {"raw": self.content_raw, "parse_error": self.parse_error}
