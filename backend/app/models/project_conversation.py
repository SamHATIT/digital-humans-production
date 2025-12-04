"""Project Conversation model for chat with Sophie."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProjectConversation(Base):
    """Model for project conversations with Sophie."""
    __tablename__ = "project_conversations"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="SET NULL"), nullable=True)
    
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    message = Column(Text, nullable=False)
    
    # Context summary used for response
    context_summary = Column(Text)
    
    # Metadata
    tokens_used = Column(Integer, default=0)
    model_used = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="conversations")
    execution = relationship("Execution", back_populates="conversations")
