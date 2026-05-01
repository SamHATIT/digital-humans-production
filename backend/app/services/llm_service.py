"""
LLM Service — thin wrapper around LLMRouterService (session3 / Agent C).

Historique : ce module hébergeait auparavant une classe LLMService de 752 lignes
qui dupliquait ANTHROPIC_MODELS / AGENT_TIER_MAP / continuation logic / pricing.
Depuis C-0, la source de vérité unique est `config/llm_routing.yaml` consommée
par `app.services.llm_router_service.LLMRouterService`.

Symbols publics conservés pour backward compatibility :
    - generate_llm_response(...)           — appel sync, utilisé par tous les agents
    - generate_llm_response_async(...)     — appel async (sds_section_writer)
    - generate_json_response(...)          — wrapper qui parse la sortie en JSON
    - LLMProvider (enum)                   — importé par les agents pour compat signatures
"""

import logging
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tier resolution helpers (Phase 3.4 — tier-based LLM routing)
# ---------------------------------------------------------------------------
# Cached by execution_id : un SDS = ~7 LLM calls Marcus, ~5 Olivia, etc. On
# ne veut pas requêter DB à chaque appel. Dans une exécution donnée, le tier
# du user est figé (changement Stripe ne s'applique qu'aux runs suivants).

@lru_cache(maxsize=512)
def _resolve_tier_for_execution(execution_id: int) -> Optional[str]:
    """Look up subscription_tier from execution_id → project → user.

    Returns the tier string (free/pro/team/enterprise) or None on any error
    (lookup failure, missing user, etc.). None means "no tier-based override
    will be applied" — equivalent to pre-Phase 3.4 behavior.
    """
    if not execution_id:
        return None
    try:
        from app.database import SessionLocal
        from app.models.execution import Execution
        from app.models.project import Project
        from app.models.user import User

        db = SessionLocal()
        try:
            execution = db.query(Execution).filter(Execution.id == execution_id).first()
            if not execution or not execution.project_id:
                return None
            project = db.query(Project).filter(Project.id == execution.project_id).first()
            if not project or not project.user_id:
                return None
            user = db.query(User).filter(User.id == project.user_id).first()
            if not user:
                return None
            tier = (user.subscription_tier or "free").lower().strip()
            return tier
        finally:
            db.close()
    except Exception as e:
        logger.warning("Tier resolution failed for execution %s: %s", execution_id, e)
        return None


def invalidate_tier_cache(execution_id: Optional[int] = None) -> None:
    """Invalidate cached tier(s). Called by Stripe webhook on subscription change."""
    _resolve_tier_for_execution.cache_clear()


class LLMProvider(str, Enum):
    """Kept for backward-compat with agent imports (`from ... import LLMProvider`)."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


# === DEBUG LOGGING FOR AGENT TESTS ===
def _log_llm_debug(step: str, data: dict):
    """Log LLM data to debug file if AGENT_TEST_LOG_FILE is set (preserved from V1)."""
    import os
    import json as _json
    from pathlib import Path as _Path
    from datetime import datetime as _dt

    log_file = os.environ.get("AGENT_TEST_LOG_FILE")
    if not log_file:
        return
    try:
        log_path = _Path(log_file)
        existing = {"steps": []}
        if log_path.exists():
            with open(log_path, "r") as f:
                existing = _json.load(f)
        existing["steps"].append({
            "timestamp": _dt.now().isoformat(),
            "component": "llm_service",
            "step": step,
            "data": data,
        })
        with open(log_path, "w") as f:
            _json.dump(existing, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning("LLM debug log error: %s", e)


def _strip_legacy_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove kwargs that the router doesn't accept but legacy callers still pass.

    `model`, `model_override`, `provider` are ignored : the router decides the
    model/provider based on `agent_type` + active profile (YAML).
    """
    out = dict(kwargs)
    for k in ("model", "model_override", "provider"):
        out.pop(k, None)
    return out


def generate_llm_response(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Sync LLM call. Delegates to LLMRouterService.generate().

    `execution_id` in kwargs triggers budget tracking via BudgetService.
    `project_id` is passed through for cost reporting.
    """
    from app.services.llm_router_service import get_llm_router

    router = get_llm_router()
    clean_kwargs = _strip_legacy_kwargs(kwargs)

    # Auto-create DB session for budget tracking if execution_id provided
    execution_id = clean_kwargs.get("execution_id")
    db_session = clean_kwargs.get("db")
    auto_created_db = False
    if execution_id and not db_session:
        try:
            from app.database import SessionLocal
            db_session = SessionLocal()
            auto_created_db = True
        except Exception:
            db_session = None

    _log_llm_debug("llm_request", {
        "agent_type": agent_type,
        "profile": router.get_active_profile(),
        "max_tokens": clean_kwargs.get("max_tokens", 16000),
        "system_prompt_length": len(system_prompt) if system_prompt else 0,
        "user_prompt_length": len(prompt),
        "user_prompt_preview": prompt[:500],
    })

    # Auto-resolve subscription_tier from execution_id if not explicitly passed
    # (Phase 3.4 — tier-based LLM routing, cached per execution).
    if "subscription_tier" not in clean_kwargs and execution_id:
        resolved_tier = _resolve_tier_for_execution(execution_id)
        if resolved_tier:
            clean_kwargs["subscription_tier"] = resolved_tier
            logger.debug("Resolved tier=%s for execution=%s", resolved_tier, execution_id)

    try:
        response = router.generate(
            prompt=prompt,
            agent_type=agent_type,
            system_prompt=system_prompt,
            max_tokens=clean_kwargs.pop("max_tokens", 16000),
            temperature=clean_kwargs.pop("temperature", 0.7),
            **{k: v for k, v in clean_kwargs.items() if k in ("project_id", "execution_id", "user_id", "subscription_tier", "cache_system")},
        )

        # Budget tracking post-call
        if execution_id and db_session and response.get("success"):
            try:
                from app.services.budget_service import BudgetService
                budget = BudgetService(db_session)
                cost = budget.record_cost(
                    execution_id,
                    response.get("model") or response.get("provider", ""),
                    response.get("input_tokens", 0),
                    response.get("output_tokens", 0),
                )
                db_session.commit()
                logger.info("[Budget] +$%.4f (execution %d)", cost, execution_id)
            except Exception as e:
                logger.warning("Budget recording failed (non-blocking): %s", e)

        _log_llm_debug("llm_response", {
            "provider": response.get("provider"),
            "model": response.get("model"),
            "input_tokens": response.get("input_tokens"),
            "output_tokens": response.get("output_tokens"),
            "response_length": len(response.get("content", "")),
            "response_preview": (response.get("content", "") or "")[:1000],
            "stop_reason": response.get("stop_reason"),
            "continuations": response.get("continuations", 0),
        })
        return response
    finally:
        if auto_created_db and db_session:
            try:
                db_session.close()
            except Exception:
                pass


async def generate_llm_response_async(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Async variant — delegates to LLMRouterService.generate_async()."""
    from app.services.llm_router_service import get_llm_router

    router = get_llm_router()
    clean_kwargs = _strip_legacy_kwargs(kwargs)

    # Auto-resolve subscription_tier from execution_id (Phase 3.4)
    execution_id = clean_kwargs.get("execution_id")
    if "subscription_tier" not in clean_kwargs and execution_id:
        resolved_tier = _resolve_tier_for_execution(execution_id)
        if resolved_tier:
            clean_kwargs["subscription_tier"] = resolved_tier
            logger.debug("Resolved tier=%s for execution=%s (async)", resolved_tier, execution_id)

    return await router.generate_async(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system_prompt,
        max_tokens=clean_kwargs.pop("max_tokens", 16000),
        temperature=clean_kwargs.pop("temperature", 0.7),
        **{k: v for k, v in clean_kwargs.items() if k in ("project_id", "execution_id", "user_id", "subscription_tier", "cache_system")},
    )


def generate_json_response(
    prompt: str,
    agent_type: str = "worker",
    system_prompt: Optional[str] = None,
    agent_id: str = "unknown",
    mode: str = "unknown",
    **kwargs,
) -> Dict[str, Any]:
    """
    Generate LLM response and parse it as JSON with robust cleaning.

    Returns the same shape as generate_llm_response(), but `content` is the
    parsed JSON object (or `{"raw": ..., "parse_error": ...}` on failure) and
    `content_raw` holds the original string.
    """
    from app.utils.json_cleaner import clean_llm_json_response

    response = generate_llm_response(
        prompt=prompt,
        agent_type=agent_type,
        system_prompt=system_prompt,
        **kwargs,
    )

    raw_content = response.get("content", "")
    parsed, error = clean_llm_json_response(raw_content)
    if parsed is not None:
        response["content"] = parsed
        response["content_raw"] = raw_content
        response["json_parsed"] = True
        logger.debug("[%s/%s] JSON parsed successfully", agent_id, mode)
    else:
        response["content"] = {"raw": raw_content, "parse_error": error}
        response["content_raw"] = raw_content
        response["json_parsed"] = False
        logger.warning("[%s/%s] JSON parse failed: %s", agent_id, mode, error)
    return response
