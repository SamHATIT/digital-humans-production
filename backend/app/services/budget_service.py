"""
Budget tracking and enforcement for LLM API calls.
Checked before every LLM call, updated after every response.

P1.1: BudgetService — financial guardrails per execution/project.
P1.2: CircuitBreaker — prevents infinite agent loops.
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.execution import Execution

logger = logging.getLogger(__name__)

# Pricing per 1M tokens (approximate, Anthropic Feb 2026)
MODEL_PRICING = {
    # Anthropic
    "claude-opus-4-20250514":       {"input": 15.0,  "output": 75.0},
    "claude-opus-4-5-20251101":     {"input": 15.0,  "output": 75.0},
    "claude-sonnet-4-20250514":     {"input": 3.0,   "output": 15.0},
    "claude-sonnet-4-5-20250929":   {"input": 3.0,   "output": 15.0},
    "claude-haiku-4-20250514":      {"input": 0.25,  "output": 1.25},
    "claude-haiku-4-5-20251001":    {"input": 0.25,  "output": 1.25},
    # OpenAI
    "gpt-4o":                       {"input": 2.5,   "output": 10.0},
    "gpt-4o-mini":                  {"input": 0.15,  "output": 0.6},
    # Default fallback
    "default":                      {"input": 3.0,   "output": 15.0},
}

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
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
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

        # Check execution-level limit
        if execution_cost + estimated_cost > execution_limit:
            raise BudgetExceededError("execution", execution_cost, execution_limit)

        # Check project-level limit (sum of all executions for this project)
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
                    input_tokens: int, output_tokens: int) -> float:
        """
        Record cost after an LLM call. Returns the cost in USD.

        Does NOT commit — caller manages transaction.
        """
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        execution = self.db.query(Execution).get(execution_id)
        if execution:
            execution.total_cost = (execution.total_cost or 0.0) + cost
            execution.total_tokens_used = (
                (execution.total_tokens_used or 0) + input_tokens + output_tokens
            )
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
        """
        Check if an agent has exceeded retry limit.

        Returns True if allowed, False if circuit is open (limit reached).
        """
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
        """
        Check if total LLM calls exceed safety threshold.

        Returns True if allowed, False if limit reached.
        """
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
        """Increment retry counter for an agent."""
        execution = self.db.query(Execution).get(execution_id)
        if execution:
            status = execution.agent_execution_status or {}
            if agent_id not in status:
                status[agent_id] = {}
            status[agent_id]["retry_count"] = status[agent_id].get("retry_count", 0) + 1
            execution.agent_execution_status = status
