"""API routes for project chat with Sophie."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.project import Project
from app.models.project_conversation import ProjectConversation
from app.schemas.project_conversation import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatHistoryResponse,
    SophieResponse
)
from app.services.sophie_chat_service import SophieChatService

router = APIRouter(prefix="/api/projects", tags=["project-chat"])


@router.post("/{project_id}/chat", response_model=SophieResponse)
async def chat_with_sophie(
    project_id: int,
    message: ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Send a message to Sophie and get a response."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Chat with Sophie
    service = SophieChatService(db)
    result = await service.chat(
        project_id=project_id,
        user_message=message.message
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Chat failed"))
    
    return SophieResponse(
        message=result["message"],
        tokens_used=result.get("tokens_used", 0),
        context_used=result.get("context_used", [])
    )


@router.get("/{project_id}/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    project_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get chat history for a project."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get messages
    messages = db.query(ProjectConversation).filter(
        ProjectConversation.project_id == project_id
    ).order_by(ProjectConversation.created_at.asc()).limit(limit).all()
    
    return ChatHistoryResponse(
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
        project_id=project_id,
        project_name=project.name,
        total_messages=len(messages)
    )


@router.delete("/{project_id}/chat/history")
async def clear_chat_history(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Clear chat history for a project."""
    # Verify project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Delete messages
    db.query(ProjectConversation).filter(
        ProjectConversation.project_id == project_id
    ).delete()
    db.commit()
    
    return {"message": "Chat history cleared", "project_id": project_id}
