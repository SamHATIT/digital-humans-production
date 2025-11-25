"""
Pydantic schemas for Agent model validation and serialization.
"""
from typing import Optional
from pydantic import BaseModel, Field


class AgentBase(BaseModel):
    """Base agent schema with common attributes."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    icon: Optional[str] = None
    estimated_time: Optional[int] = None  # in seconds
    cost_estimate: Optional[float] = None


class AgentCreate(AgentBase):
    """Schema for creating a new agent."""
    pass


class AgentUpdate(BaseModel):
    """Schema for updating agent information."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    estimated_time: Optional[int] = None
    cost_estimate: Optional[float] = None


class AgentInDB(AgentBase):
    """Schema for agent stored in database."""
    id: int

    class Config:
        from_attributes = True


class Agent(AgentInDB):
    """Schema for agent response (public)."""
    pass
