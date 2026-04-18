"""
Budget tracking and enforcement for LLM API calls.
Checked before every LLM call, updated after every response.

P1.1: BudgetService — financial guardrails per execution/project.
P1.2: CircuitBreaker — prevents infinite agent loops.

C-5 (session3): pricing is now loaded from config/llm_routing.yaml (source unique).
Keys are indexed both by provider/alias (e.g. "anthropic/claude-opus") and by
resolved model_id (e.g. "claude-opus-4-6") so callers can pass either form.
"""
import logging
from pathlib import Path
from typing import Dict

import yaml
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.models.execution import Execution

logger = logging.getLogger(__name__)


def _load_pricing_from_yaml() -> Dict[str, Dict[str, float]]:
    """
    Build the runtime pricing dict from config/llm_routing.yaml.

    The YAML has entries like:
        pricing:
          "anthropic/claude-opus":
            input: 15.0
            output: 75.0

    We also index each entry by its resolved model_id (e.g. "claude-opus-4-6")
    so callers that pass the bare model string from the API response still
    resolve correctly.
    """
    candidates = [
        Path(__file__).parent.parent.parent / "config" / "llm_routing.yaml",
        Path(settings.LLM_CONFIG_PATH),
    ]
    config_path = next((p for p in candidates if p.exists()), None)
    if config_path is None:
        logger.warning("llm_routing.yaml not found, using fallback pricing")
        return _FALLBACK_PRICING

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.error("Failed to load pricing from %s: %s", config_path, exc)
        return _FALLBACK_PRICING

    pricing: Dict[str, Dict[str, float]] = {}
    yaml_pricing = config.get("pricing", {}) or {}
    providers = config.get("providers", {}) or {}

    for key, prices in yaml_pricing.items():
        input_price = float(prices.get("input", 0))
        output_price = float(prices.get("output", 0))
        entry = {"input": input_price, "output": output_price}
        pricing[key] = entry

        # Also index by resolved model_id
        if "/" in key:
            provider_name, model_alias = key.split("/", 1)
            model_cfg = (
                providers.get(provider_name, {}).get("models", {}).get(model_alias, {})
            )
            model_id = model_cfg.get("model_id")
            if model_id and model_id not in pricing:
                pricing[model_id] = entry
            # For local/Ollama, the model alias IS the model_id
            if provider_name == "local" and model_alias not in pricing:
                pricing[model_alias] = entry

    # Default fallback — Sonnet-level
    pricing.setdefault("default", pricing.get("anthropic/claude-sonnet", {"input": 3.0, "output": 15.0}))
    return pricing


# Minimal fallback used if YAML load fails (keeps the service operational in CI)
_FALLBACK_PRICING: Dict[str, Dict[str, float]] = {
    "anthropic/claude-opus":   {"input": 15.0, "output": 75.0},
    "anthropic/claude-sonnet": {"input":  3.0, "output": 15.0},
    "anthropic/claude-haiku":  {"input":  1.0, "output":  5.0},
    "claude-opus-4-6":         {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0},
    "default":                 {"input":  3.0, "output": 15.0},
}


# Loaded once at module import. Use reload_pricing() in tests to force re-read.
MODEL_PRICING: Dict[str, Dict[str, float]] = _load_pricing_from_yaml()


def reload_pricing():
    """Force reload of MODEL_PRICING from YAML (useful after config changes / tests)."""
    global MODEL_PRICING
    MODEL_PRICING = _load_pricing_from_yaml()
    return MODEL_PRICING


# Default limits
DEFAULT_EXECUTION_LIMIT_USD = 50.0
DEFAULT_PROJECT_LIMIT_USD = 200.0
DEFAULT_MONTHLY_LIMIT_USD = 500.0


class BudgetExceededError(Exception):
    """Raised when a budget limit is reached."""
    def __init__(self, limit_type: str, current: float, limit: float):
        self.limit_type = limit_type
        self.current = current
        self.limit = limit
        super().__init__(
            f"Budget exceeded: {limit_type} — ${current:.2f} / ${limit:.2f}"
        )


def _resolve_pricing(model_or_provider: str) -> Dict[str, float]:
    """
    Resolve pricing for a given key. Accepts either:
      - provider/alias form : "anthropic/claude-opus"
      - raw model_id        : "claude-opus-4-6"
      - Ollama model name   : "mistral:7b-instruct"
    Falls back to substring match on "opus"/"haiku"/"sonnet" then "default".
    """
    if not model_or_provider:
        return MODEL_PRICING["default"]

    pricing = MODEL_PRICING.get(model_or_provider)
    if pricing is not None:
        return pricing

    lowered = model_or_provider.lower()
    if "opus" in lowered:
        return MODEL_PRICING.get("anthropic/claude-opus", MODEL_PRICING["default"])
    if "haiku" in lowered:
        return MODEL_PRICING.get("anthropic/claude-haiku", MODEL_PRICING["default"])
    if "sonnet" in lowered:
        return MODEL_PRICING.get("anthropic/claude-sonnet", MODEL_PRICING["default"])
    if lowered.startswith("local/") or lowered.startswith("mistral") or lowered.startswith("mixtral"):
        return {"input": 0.0, "output": 0.0}
    return MODEL_PRICING["default"]


class BudgetService:
    """
    Financial guardrails for LLM API usage.

    Usage:
        service = BudgetService(db)
        service.check_budget(execution_id, estimated_cost=0.5)
        # ... make LLM call ...
        service.record_cost(execution_id, model, input_tokens, output_tokens)
    """

    def __init__(self, db: Session):
        self.db = db

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost of an LLM call in USD."""
        pricing = _resolve_pricing(model)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        return round(cost, 6)

    def check_budget(self, execution_id: int, estimated_cost: float = 0.0) -> dict:
        """
        Check if execution is within budget. Call BEFORE every LLM call.

        Returns:
            {"allowed": True, "execution_cost": float, "project_cost": float, ...}

        Raises:
            BudgetExceededError if any limit is exceeded.
        """
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return {"allowed": True, "execution_cost": 0, "project_cost": 0}

        execution_cost = execution.total_cost or 0.0
        execution_limit = DEFAULT_EXECUTION_LIMIT_USD

        if execution_cost + estimated_cost > execution_limit:
            raise BudgetExceededError("execution", execution_cost, execution_limit)

        project_cost = self.db.query(
            func.coalesce(func.sum(Execution.total_cost), 0)
        ).filter(
            Execution.project_id == execution.project_id
        ).scalar()

        if project_cost + estimated_cost > DEFAULT_PROJECT_LIMIT_USD:
            raise BudgetExceededError("project", project_cost, DEFAULT_PROJECT_LIMIT_USD)

        return {
            "allowed": True,
            "execution_cost": execution_cost,
            "project_cost": float(project_cost),
            "remaining_execution": execution_limit - execution_cost,
            "remaining_project": DEFAULT_PROJECT_LIMIT_USD - float(project_cost),
        }

    def record_cost(self, execution_id: int, model: str,
                    input_tokens: int, output_tokens: int,
                    commit: bool = True) -> float:
        """
        Record cost after an LLM call. Returns the cost in USD.

        `model` accepts either provider/alias ("anthropic/claude-opus") or
        raw model_id ("claude-opus-4-6") — both resolve to the same pricing.

        P7: commits by default so the cost is persisted even when the caller
        auto-created a short-lived DB session (as generate_llm_response does).
        Pass commit=False when the caller owns the transaction lifecycle.
        """
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        execution = self.db.query(Execution).get(execution_id)
        if execution:
            execution.total_cost = (execution.total_cost or 0.0) + cost
            execution.total_tokens_used = (
                (execution.total_tokens_used or 0) + input_tokens + output_tokens
            )
            if commit:
                try:
                    self.db.commit()
                except Exception:
                    self.db.rollback()
                    raise
        return cost


# ---------------------------------------------------------------------------
# P1.2 — Circuit Breaker
# ---------------------------------------------------------------------------

class CircuitBreaker:
    """
    Prevents infinite loops in agent interactions.
    Tracks retries per agent per execution and total LLM calls.
    """
    MAX_AGENT_RETRIES = 3
    MAX_REVISION_LOOPS = 2   # Emma<->Marcus maximum
    MAX_TOTAL_LLM_CALLS = 80  # Per execution (~43 is normal for SDS)

    def __init__(self, db: Session):
        self.db = db

    def check_agent_retry(self, execution_id: int, agent_id: str) -> bool:
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return True

        retries = execution.agent_execution_status or {}
        agent_status = retries.get(agent_id, {})
        retry_count = agent_status.get("retry_count", 0)

        if retry_count >= self.MAX_AGENT_RETRIES:
            logger.warning(
                "[CircuitBreaker] Agent %s exceeded %d retries in execution %d",
                agent_id, self.MAX_AGENT_RETRIES, execution_id,
            )
            return False
        return True

    def check_total_calls(self, execution_id: int) -> bool:
        execution = self.db.query(Execution).get(execution_id)
        if not execution:
            return True

        total_calls = sum(
            s.get("llm_calls", 0)
            for s in (execution.agent_execution_status or {}).values()
        )

        if total_calls >= self.MAX_TOTAL_LLM_CALLS:
            logger.error(
                "[CircuitBreaker] Execution %d: %d LLM calls exceeds safety limit (%d)",
                execution_id, total_calls, self.MAX_TOTAL_LLM_CALLS,
            )
            return False
        return True

    def increment_retry(self, execution_id: int, agent_id: str):
        execution = self.db.query(Execution).get(execution_id)
        if execution:
            status = execution.agent_execution_status or {}
            if agent_id not in status:
                status[agent_id] = {}
            status[agent_id]["retry_count"] = status[agent_id].get("retry_count", 0) + 1
            execution.agent_execution_status = status
