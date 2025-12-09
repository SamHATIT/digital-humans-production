"""
LLM Interaction Model - Tracks all LLM calls for debugging
"""
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class LLMInteraction(Base):
    """
    Tracks every LLM API call made by agents.
    Enables debugging by storing full prompt, response, and context.
    """
    __tablename__ = "llm_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=True)
    task_id = Column(String(50), nullable=True, index=True)
    agent_id = Column(String(50), nullable=False, index=True)
    agent_mode = Column(String(20))  # spec, build, test
    
    # Input
    prompt = Column(Text, nullable=False)
    rag_context = Column(Text, nullable=True)
    previous_feedback = Column(Text, nullable=True)
    
    # Output
    response = Column(Text, nullable=True)
    parsed_files = Column(JSONB, nullable=True)  # Extracted files from response
    
    # Metrics
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    model = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)  # anthropic, openai
    execution_time_seconds = Column(Float, nullable=True)
    
    # Status
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<LLMInteraction {self.id} agent={self.agent_id} task={self.task_id}>"
