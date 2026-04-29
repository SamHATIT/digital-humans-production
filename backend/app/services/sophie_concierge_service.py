"""
Sophie Concierge Service — chat backend for the marketing-site widget.

Wraps the LLM router with everything the public endpoint needs:
  - load Sophie's "concierge" mode prompt from sophie_pm.yaml
  - render conversation history in the format Anthropic expects
  - call Claude Sonnet 4.6 with a tight token cap
  - parse the [META] trailer Sophie appends (intent / email / next_action)
  - persist every turn (user + assistant) to chat_logs
  - enforce a global daily budget (Redis counter, fail-soft if Redis down)
  - hash visitor IPs before storage (RGPD)

The HTTP layer (concierge_routes.py) handles rate-limiting, request shape,
and SSE streaming. This module stays HTTP-agnostic so it can be reused
later (e.g. by a "talk to Sophie from the Studio" feature, or batch
analysis of past conversations).
"""
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import yaml
from sqlalchemy.orm import Session

from app.models.chat_log import ChatLog
from app.services.llm_router_service import LLMRequest, get_llm_router

logger = logging.getLogger(__name__)


# Configuration — kept module-level so tests can monkeypatch easily
PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "agents" / "sophie_pm.yaml"
HISTORY_TURNS_MAX = 20            # hard cap on conversation length per session
DAILY_BUDGET_USD = 20.0           # global ceiling, all sessions combined
IP_SALT = os.getenv("CHAT_IP_SALT", "dh-concierge-default-salt-change-me")

# Loaded once at module import — small file, no need to re-read on every call.
_PROMPT_CACHE: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ConciergeReply:
    """What we send back to the visitor after one turn."""
    text: str                       # Sophie's reply, META block stripped
    intent: Optional[str] = None
    next_action: Optional[str] = None
    email_collected: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0           # actual dollars (DB stores micro-cents)
    ended: bool = False             # True if Sophie said "end" or budget hit


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _hash_ip(ip: str) -> str:
    """SHA-256 of (ip + salt). Reversible only with the salt, never stored raw."""
    return hashlib.sha256(f"{ip}{IP_SALT}".encode("utf-8")).hexdigest()


def _load_concierge_prompt() -> dict:
    """Load and cache the concierge mode prompts from sophie_pm.yaml."""
    global _PROMPT_CACHE
    if _PROMPT_CACHE is not None:
        return _PROMPT_CACHE
    with open(PROMPT_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    mode = data.get("modes", {}).get("concierge")
    if not mode:
        raise RuntimeError("sophie_pm.yaml is missing the 'concierge' mode")
    _PROMPT_CACHE = mode
    return mode


def _render_history(turns: List[ChatLog], max_turns: int = HISTORY_TURNS_MAX) -> str:
    """Render the last N turns as a plain-text dialogue for the prompt."""
    recent = turns[-max_turns:]
    lines = []
    for t in recent:
        speaker = "Visitor" if t.role == "user" else "Sophie"
        lines.append(f"{speaker}: {t.message}")
    return "\n".join(lines) if lines else "(no prior turns — first message)"


# Sophie appends [META]{...json...} on its own line. Capture and strip.
_META_RE = re.compile(r"\[META\]\s*(\{.*?\})\s*$", re.DOTALL)


def _split_message_and_meta(raw: str) -> tuple[str, dict]:
    """Pull the trailing [META]{...} block off Sophie's reply.

    Returns (clean_text_for_user, meta_dict). If the META block is missing
    or malformed we return ({} dict and the full text — the user still sees
    a usable reply, the analytics just won't have a classification."""
    m = _META_RE.search(raw)
    if not m:
        return raw.strip(), {}
    try:
        meta = json.loads(m.group(1))
    except json.JSONDecodeError:
        logger.warning("Sophie META block was not valid JSON, ignoring")
        meta = {}
    clean = _META_RE.sub("", raw).strip()
    return clean, meta


def _check_daily_budget(db: Session) -> bool:
    """Return True if we're still under the daily $ ceiling.

    Checks SUM(cost_usd) on chat_logs from the last 24h. Cheap query thanks
    to the created_at index. We use the DB rather than Redis to avoid
    introducing a Redis dependency for a low-volume endpoint — if traffic
    grows we'll move to a cached counter."""
    from sqlalchemy import func, and_
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    total_micro_cents = db.query(func.coalesce(func.sum(ChatLog.cost_usd), 0)).filter(
        ChatLog.created_at >= cutoff
    ).scalar()
    total_usd = (total_micro_cents or 0) / 1_000_000.0
    return total_usd < DAILY_BUDGET_USD


# ─────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────

async def converse(
    db: Session,
    session_uuid: str,
    visitor_ip: str,
    visitor_language: str,
    user_message: str,
) -> ConciergeReply:
    """Process one visitor message and return Sophie's reply.

    This is the single entry point. The HTTP route is a thin shell around it.
    The function is responsible for the full turn lifecycle: budget check,
    persisting the user turn, calling the LLM, parsing the META, persisting
    the assistant turn, returning a structured reply.
    """
    ip_hash = _hash_ip(visitor_ip)

    # 1. Budget guard — fail closed: if we can't tell, we still try (Postgres
    #    is local, the query is cheap, this should never raise).
    if not _check_daily_budget(db):
        logger.warning("Daily concierge budget exceeded — refusing turn")
        return ConciergeReply(
            text=(
                "Sorry — I'm taking a short break. "
                "Please email sam@samhatit.com and Sam will get back to you."
                if visitor_language == "en"
                else "Désolée, je prends une petite pause. "
                "Écrivez à sam@samhatit.com, Sam vous répondra."
            ),
            ended=True,
        )

    # 2. Conversation length guard — past N turns we redirect to email.
    history = (
        db.query(ChatLog)
        .filter(ChatLog.session_uuid == session_uuid)
        .order_by(ChatLog.created_at)
        .all()
    )
    if len(history) >= HISTORY_TURNS_MAX * 2:  # *2 because user + assistant per round
        return ConciergeReply(
            text=(
                "We've had a great chat! To go further, leave your email "
                "and Sam will follow up with the next steps."
                if visitor_language == "en"
                else "On a bien échangé ! Pour continuer, laisse ton email "
                "et Sam te recontacte avec la suite."
            ),
            next_action="end",
            ended=True,
        )

    # 3. Persist the user turn first (so even if LLM call fails we have it).
    user_log = ChatLog(
        session_uuid=session_uuid,
        ip_hash=ip_hash,
        visitor_language=visitor_language,
        role="user",
        message=user_message,
    )
    db.add(user_log)
    db.commit()

    # 4. Build the prompt from sophie_pm.yaml + this conversation's history.
    mode = _load_concierge_prompt()
    rendered_prompt = mode["prompt"].replace("{{visitor_language}}", visitor_language)
    rendered_prompt = rendered_prompt.replace("{{history}}", _render_history(history))
    rendered_prompt = rendered_prompt.replace("{{user_message}}", user_message)

    # 5. Call the LLM.
    router = get_llm_router()
    request = LLMRequest(
        prompt=rendered_prompt,
        system_prompt=mode["system_prompt"],
        max_tokens=mode["config"]["max_tokens"],
        temperature=mode["config"]["temperature"],
        agent_type="pm",
        force_provider="anthropic/claude-sonnet-4-6",
        # user_id is None — visitor has no account, no credit accounting.
        metadata={"feature": "concierge", "session_uuid": session_uuid},
    )

    try:
        response = await router.complete(request)
    except Exception as e:
        logger.exception("Sophie LLM call failed")
        return ConciergeReply(
            text=(
                "Sorry, something went wrong on my side. "
                "Please try again in a moment."
                if visitor_language == "en"
                else "Désolée, j'ai eu un souci technique. "
                "Réessaie dans un instant."
            ),
            ended=False,
        )

    raw_text = response.content if hasattr(response, "content") else str(response)
    clean_text, meta = _split_message_and_meta(raw_text)

    # 6. Persist the assistant turn with metadata + cost.
    cost_micro = int((response.cost_usd or 0) * 1_000_000) if hasattr(response, "cost_usd") else 0
    assistant_log = ChatLog(
        session_uuid=session_uuid,
        ip_hash=ip_hash,
        visitor_language=visitor_language,
        role="assistant",
        message=clean_text,
        intent=meta.get("intent"),
        next_action=meta.get("next_action"),
        email_collected=meta.get("email") or None,
        tokens_in=getattr(response, "tokens_input", None),
        tokens_out=getattr(response, "tokens_output", None),
        cost_usd=cost_micro,
    )
    db.add(assistant_log)
    db.commit()

    # 7. If the visitor shared their email, mirror it to the leads table
    #    (deduped by email — ignore if already there).
    if meta.get("email"):
        _maybe_create_lead(db, meta["email"], meta.get("intent"), session_uuid)

    return ConciergeReply(
        text=clean_text,
        intent=meta.get("intent"),
        next_action=meta.get("next_action"),
        email_collected=meta.get("email") or None,
        tokens_in=getattr(response, "tokens_input", 0) or 0,
        tokens_out=getattr(response, "tokens_output", 0) or 0,
        cost_usd=response.cost_usd if hasattr(response, "cost_usd") else 0.0,
        ended=meta.get("next_action") == "end",
    )


def _maybe_create_lead(db: Session, email: str, intent: Optional[str], session_uuid: str) -> None:
    """Insert into the leads table if this email isn't already there."""
    from sqlalchemy import text
    try:
        existing = db.execute(
            text("SELECT id FROM leads WHERE email = :email"),
            {"email": email},
        ).fetchone()
        if existing:
            return
        db.execute(
            text("""
                INSERT INTO leads (email, source, subscribed_newsletter, score_reason, created_at)
                VALUES (:email, :source, :sub, :reason, NOW())
            """),
            {
                "email": email,
                "source": "marketing_chat_sophie",
                "sub": intent == "newsletter_only",
                "reason": f"Captured by Sophie concierge, intent={intent}, session={session_uuid}",
            },
        )
        db.commit()
    except Exception:
        logger.exception("Failed to mirror chat email to leads table")
        db.rollback()
