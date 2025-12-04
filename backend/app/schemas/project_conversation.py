"""Schemas for Project Conversations with Sophie."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class ChatMessageBase(BaseModel):
    """Base schema for chat message."""
    message: str


class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a chat message (user sends)."""
    pass


class ChatMessageResponse(BaseModel):
    """Schema for chat message response."""
    id: int
    project_id: int
    execution_id: Optional[int] = None
    role: str  # 'user' or 'assistant'
    message: str
    tokens_used: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """Schema for chat history response."""
    messages: List[ChatMessageResponse]
    project_id: int
    project_name: str
    total_messages: int


class SophieResponse(BaseModel):
    """Schema for Sophie's response."""
    message: str
    tokens_used: int
    context_used: List[str] = []  # What context was used for the response
