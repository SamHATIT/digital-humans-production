"""
ChatLog Model — Public marketing-site chat conversations.

Stores every message exchanged between visitors and Sophie (concierge mode)
on the marketing site. Used for:
  - Conversation continuity (visitor refreshes page, picks up where they left off)
  - Lead nurturing (we look back at what someone said before sending an email)
  - Quality and abuse review (rate-limit IPs that try to jailbreak Sophie)

Privacy / RGPD:
  - IP is hashed (SHA-256 + secret salt) before storage — never raw IP
  - email collected only with explicit visitor consent in conversation
  - retention: rows are auto-deleted after 90 days (cron job to add)
  - visitor can request deletion of their session via /api/public/forget
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base


class ChatLog(Base):
    """One row per message (user or assistant) in a marketing-chat session."""
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True)

    # Session identifier — UUID generated client-side, sent on every request.
    # Lets the visitor refresh the page or come back later and resume.
    session_uuid = Column(String(64), nullable=False, index=True)

    # Hashed visitor IP — for rate-limit forensics and abuse triage, never PII.
    ip_hash = Column(String(64), nullable=False, index=True)

    # Visitor's browser language at the time the session started (en/fr).
    visitor_language = Column(String(8), nullable=True)

    # 'user' or 'assistant' — same vocabulary as Anthropic's API.
    role = Column(String(16), nullable=False)

    # The actual message text (user input or Sophie's reply, META stripped).
    message = Column(Text, nullable=False)

    # Sophie's classification, only set on assistant turns.
    intent = Column(String(32), nullable=True)
    next_action = Column(String(32), nullable=True)
    email_collected = Column(String(255), nullable=True)

    # Cost tracking per turn (so we can cap daily budget).
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_usd = Column(Integer, nullable=True)  # micro-cents (multiply by 1e-6)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_chat_logs_session_created", "session_uuid", "created_at"),
    )
