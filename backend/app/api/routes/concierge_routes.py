"""
Public concierge routes — Sophie chat widget on the marketing site.

These endpoints are PUBLIC (no auth) and rate-limited per IP. Designed for
the "Talk to Sophie" widget on /preview/ and the upcoming production site.

Routes:
  POST /api/public/concierge/talk        — one turn of conversation
  GET  /api/public/concierge/history     — load prior turns of a session
  POST /api/public/concierge/forget      — RGPD: delete all turns for a session
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chat_log import ChatLog
from app.rate_limiter import limiter, get_client_ip
from app.services.sophie_concierge_service import converse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/public/concierge", tags=["Public Concierge"])


# ─────────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────────

class TalkRequest(BaseModel):
    """One visitor message + the session context."""
    session_uuid: Optional[str] = Field(None, description="Stable per browser session — generate a v4 UUID client-side")
    message: str = Field(..., min_length=1, max_length=2000)
    visitor_language: str = Field("en", pattern="^(en|fr)$")


class TalkResponse(BaseModel):
    session_uuid: str
    reply: str
    intent: Optional[str] = None
    next_action: Optional[str] = None
    ended: bool = False


class HistoryTurn(BaseModel):
    role: str
    message: str
    created_at: str


# ─────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────

@router.post("/talk", response_model=TalkResponse)
@limiter.limit("30/hour")  # per IP — abuse cap
async def talk_to_sophie(
    request: Request,                # required by slowapi limiter
    response: Response,              # required by slowapi to inject rate-limit headers
    payload: TalkRequest,
    db: Session = Depends(get_db),
):
    """One turn of conversation. Generates a session_uuid if absent."""
    session_uuid = payload.session_uuid or str(uuid.uuid4())
    visitor_ip = get_client_ip(request)

    reply = await converse(
        db=db,
        session_uuid=session_uuid,
        visitor_ip=visitor_ip,
        visitor_language=payload.visitor_language,
        user_message=payload.message,
    )

    return TalkResponse(
        session_uuid=session_uuid,
        reply=reply.text,
        intent=reply.intent,
        next_action=reply.next_action,
        ended=reply.ended,
    )


@router.get("/history/{session_uuid}", response_model=list[HistoryTurn])
@limiter.limit("60/hour")
async def get_history(
    request: Request,
    response: Response,
    session_uuid: str,
    db: Session = Depends(get_db),
):
    """Reload the conversation when the visitor refreshes the page."""
    turns = (
        db.query(ChatLog)
        .filter(ChatLog.session_uuid == session_uuid)
        .order_by(ChatLog.created_at)
        .all()
    )
    return [
        HistoryTurn(role=t.role, message=t.message, created_at=t.created_at.isoformat())
        for t in turns
    ]


@router.post("/forget/{session_uuid}", status_code=204)
@limiter.limit("10/hour")
async def forget_session(
    request: Request,
    response: Response,
    session_uuid: str,
    db: Session = Depends(get_db),
):
    """RGPD right to erasure — delete all turns for this session."""
    deleted = (
        db.query(ChatLog)
        .filter(ChatLog.session_uuid == session_uuid)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info(f"RGPD forget: deleted {deleted} chat_logs for session {session_uuid}")
    return None
