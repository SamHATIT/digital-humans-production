"""
Agent model for Salesforce specification generation agents.
"""
from sqlalchemy import Column, Integer, String, Text, Float
from sqlalchemy.orm import relationship

from app.database import Base


class Agent(Base):
    """Agent model for storing available Salesforce agents."""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=False)
    icon = Column(String)  # Emoji or icon identifier
    estimated_time = Column(Integer)  # Estimated time in seconds
    cost_estimate = Column(Float)  # Estimated cost in credits/dollars

    # Relationships
    execution_agents = relationship("ExecutionAgent", back_populates="agent")
    outputs = relationship("Output", back_populates="agent")
