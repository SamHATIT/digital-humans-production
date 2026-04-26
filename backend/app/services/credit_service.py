"""
Credit Service — Phase 3.1+3.2 of MASTER_PLAN_V4.

Source de vérité pour la consommation de crédits LLM.

Public API
----------
- CreditService.charge(user_id, model, tokens_in, tokens_out, ...)
- CreditService.get_balance(user_id)
- CreditService.reset_monthly(user_id)
- preflight_check(user_id, model, max_tokens) — used by LLM router

Le mapping User.subscription_tier (free/premium/enterprise) → credit tier
(free/pro/team) est centralisé dans :func:`resolve_credit_tier`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    TRANSACTION_TYPE_RESET,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CreditError(Exception):
    """Base class for credit-system errors."""


class InsufficientCreditsError(CreditError):
    """User does not have enough credits for the requested operation."""

    def __init__(self, user_id: int, requested: int, available: int):
        self.user_id = user_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient credits for user {user_id}: requested={requested}, available={available}"
        )


class ModelNotAllowedError(CreditError):
    """The user's tier is not authorized to use this model."""

    def __init__(self, user_id: int, model: str, tier: str):
        self.user_id = user_id
        self.model = model
        self.tier = tier
        super().__init__(
            f"Model '{model}' not allowed for tier '{tier}' (user {user_id})"
        )


class UnknownModelError(CreditError):
    """No pricing row found for the requested model."""


# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------

# Existing User.subscription_tier values (free/premium/enterprise) → credit
# tier names (free/pro/team). Phase 3 keeps both vocabularies alive : Stripe
# upgrade flow (A6) will rename the user-facing tier later.
_TIER_ALIAS = {
    "free": "free",
    "premium": "pro",
    "pro": "pro",
    "enterprise": "team",
    "team": "team",
}


def resolve_credit_tier(user: User) -> str:
    """Map a User to its credit tier (free/pro/team). Defaults to ``free``."""
    raw = (user.subscription_tier or "free").lower()
    return _TIER_ALIAS.get(raw, "free")


# ---------------------------------------------------------------------------
# Model name normalisation
# ---------------------------------------------------------------------------

def _normalize_model_name(model: str) -> str:
    """Strip provider prefix and trim."""
    if not model:
        return ""
    if "/" in model:
        model = model.split("/", 1)[1]
    return model.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _credits_for_tokens(
    pricing: ModelPricing, tokens_in: int, tokens_out: int
) -> int:
    """
    Compute integer credits consumed for a (input, output) token pair.

    Uses Decimal to avoid float drift, rounds half-up, minimum 1 credit if the
    raw cost is positive (so a 1-token call still costs something).
    """
    # Use str() to keep Decimal precision when SQLAlchemy returns NUMERIC as float (SQLite).
    in_credits = (Decimal(int(tokens_in or 0)) / Decimal(1000)) * Decimal(
        str(pricing.credits_per_1k_input or 0)
    )
    out_credits = (Decimal(int(tokens_out or 0)) / Decimal(1000)) * Decimal(
        str(pricing.credits_per_1k_output or 0)
    )
    raw = in_credits + out_credits
    if raw <= 0:
        return 0
    rounded = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(rounded, 1)


def _is_daily_cap_quota_tier(tier_cfg: Optional[TierConfig]) -> bool:
    """
    True when the tier's spendable quota is the daily cap itself, with no
    monthly allotment (Free today). For such tiers ``balance.available`` is
    structurally 0 and must be ignored — the daily cap is the quota.
    """
    return (
        tier_cfg is not None
        and tier_cfg.daily_credits_cap is not None
        and (tier_cfg.monthly_credits or 0) == 0
    )


def _start_of_day_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_month_start(reference: datetime) -> datetime:
    """First day of the calendar month following ``reference`` (UTC, midnight)."""
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if reference.month == 12:
        return reference.replace(
            year=reference.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    return reference.replace(
        month=reference.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


# ---------------------------------------------------------------------------
# CreditService
# ---------------------------------------------------------------------------


class CreditService:
    """Business logic for credit consumption, balance and reset."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_balance(self, user_id: int) -> dict:
        """
        Return the user's current credit picture. Lazy-creates the balance
        row (and its initial allotment) if missing.
        """
        balance = self._ensure_balance(user_id)
        user = self.db.query(User).get(user_id)
        tier_name = resolve_credit_tier(user) if user else "free"
        tier = self._get_tier_config(tier_name)

        daily_used = self._daily_used_credits(user_id)
        next_reset = _next_month_start(balance.last_reset_at)

        # For daily-cap quota tiers (Free), the spendable balance is what's
        # left of today's cap, not the (always 0) included balance.
        if _is_daily_cap_quota_tier(tier):
            available = max(0, tier.daily_credits_cap - daily_used)
        else:
            available = balance.available

        return {
            "user_id": user_id,
            "tier": tier_name,
            "included_credits": balance.included_credits,
            "used_credits": balance.used_credits,
            "overage_credits": balance.overage_credits,
            "available": available,
            "daily_cap": tier.daily_credits_cap if tier else None,
            "daily_used": daily_used,
            "last_reset_at": balance.last_reset_at,
            "next_reset_at": next_reset,
        }

    def charge(
        self,
        user_id: int,
        model: str,
        tokens_in: int,
        tokens_out: int,
        execution_id: Optional[int] = None,
        project_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> CreditTransaction:
        """
        Debit the user's balance for an LLM call.

        Raises:
            UnknownModelError       — no pricing row matches ``model``.
            ModelNotAllowedError    — user's tier cannot use this model.
            InsufficientCreditsError — balance (or daily cap for free tier)
                                       cannot cover the cost.
        """
        user = self.db.query(User).get(user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")

        tier_name = resolve_credit_tier(user)
        pricing = self._resolve_pricing(model)
        if not pricing.tier_allowed(tier_name):
            raise ModelNotAllowedError(user_id, pricing.model_name, tier_name)

        credits = _credits_for_tokens(pricing, tokens_in, tokens_out)

        balance = self._ensure_balance(user_id)

        # Daily cap enforcement (currently only the free tier sets one).
        tier_cfg = self._get_tier_config(tier_name)
        daily_cap = tier_cfg.daily_credits_cap if tier_cfg else None
        if daily_cap is not None and credits > 0:
            daily_used = self._daily_used_credits(user_id)
            if daily_used + credits > daily_cap:
                raise InsufficientCreditsError(
                    user_id=user_id,
                    requested=credits,
                    available=max(0, daily_cap - daily_used),
                )

        # Available balance check — skipped for daily-cap quota tiers (Free)
        # where the daily cap above IS the spendable quota and included=0.
        if not _is_daily_cap_quota_tier(tier_cfg) and credits > balance.available:
            raise InsufficientCreditsError(
                user_id=user_id, requested=credits, available=balance.available
            )

        balance.used_credits = (balance.used_credits or 0) + credits

        tx = CreditTransaction(
            user_id=user_id,
            transaction_type=TRANSACTION_TYPE_CHARGE,
            model_used=pricing.model_name,
            tokens_input=tokens_in,
            tokens_output=tokens_out,
            credits_consumed=credits,
            execution_id=execution_id,
            project_id=project_id,
            note=note,
        )
        self.db.add(tx)

        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

        self.db.refresh(tx)
        logger.info(
            "[CreditService] charged user=%s model=%s credits=%s tokens=(%s,%s)",
            user_id, pricing.model_name, credits, tokens_in, tokens_out,
        )
        return tx

    def reset_monthly(self, user_id: int) -> CreditBalance:
        """
        Reset ``used_credits`` to 0 and refill ``included_credits`` based on
        the user's tier. Logs a reset transaction for traceability.
        """
        user = self.db.query(User).get(user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        tier_cfg = self._get_tier_config(tier_name)
        monthly = tier_cfg.monthly_credits if tier_cfg else 0

        balance = self._ensure_balance(user_id)
        previous_used = balance.used_credits or 0
        balance.used_credits = 0
        balance.included_credits = monthly
        balance.last_reset_at = datetime.now(timezone.utc)

        tx = CreditTransaction(
            user_id=user_id,
            transaction_type=TRANSACTION_TYPE_RESET,
            credits_consumed=0,
            note=f"Monthly reset (tier={tier_name}, refilled {monthly}, previously used {previous_used})",
        )
        self.db.add(tx)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(balance)
        return balance

    # ------------------------------------------------------------------
    # Pre-flight (used by LLM router)
    # ------------------------------------------------------------------

    def preflight(
        self,
        user_id: int,
        model: str,
        max_tokens: int,
    ) -> None:
        """
        Cheap check before an LLM call. Raises the same errors as
        :meth:`charge` but does NOT persist anything.

        Estimation : assume the prompt + response will consume up to
        ``max_tokens`` of OUTPUT and the same of INPUT (worst case for the
        common case where prompts are short and outputs are long).
        """
        user = self.db.query(User).get(user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        pricing = self._resolve_pricing(model)
        if not pricing.tier_allowed(tier_name):
            raise ModelNotAllowedError(user_id, pricing.model_name, tier_name)

        # Rough estimate — caller pays exact cost in charge() afterwards.
        estimate = _credits_for_tokens(pricing, max_tokens, max_tokens)
        balance = self._ensure_balance(user_id)
        tier_cfg = self._get_tier_config(tier_name)

        # Daily cap pre-check — mirrors charge() so that pre-flight rejects
        # what charge() would reject (and accepts what charge() accepts).
        daily_cap = tier_cfg.daily_credits_cap if tier_cfg else None
        if daily_cap is not None and estimate > 0:
            daily_used = self._daily_used_credits(user_id)
            if daily_used + estimate > daily_cap:
                raise InsufficientCreditsError(
                    user_id=user_id,
                    requested=estimate,
                    available=max(0, daily_cap - daily_used),
                )

        # Available balance check — skipped for daily-cap quota tiers (Free).
        if not _is_daily_cap_quota_tier(tier_cfg) and estimate > balance.available:
            raise InsufficientCreditsError(
                user_id=user_id, requested=estimate, available=balance.available
            )

    # ------------------------------------------------------------------
    # Usage helpers (for /api/billing/usage)
    # ------------------------------------------------------------------

    def get_usage(self, user_id: int, days: int = 30) -> dict:
        """
        Aggregated usage report : total credits, breakdown by model, daily
        time series. ``days`` clamped between 1 and 365.
        """
        days = max(1, min(int(days or 30), 365))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            self.db.query(CreditTransaction)
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.created_at >= since,
                CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
            )
            .all()
        )

        total_credits = 0
        total_tokens_in = 0
        total_tokens_out = 0
        by_model: dict[str, dict] = {}
        by_day: dict[str, int] = {}

        for r in rows:
            credits = r.credits_consumed or 0
            total_credits += credits
            total_tokens_in += r.tokens_input or 0
            total_tokens_out += r.tokens_output or 0

            model_key = r.model_used or "unknown"
            bucket = by_model.setdefault(
                model_key,
                {"credits": 0, "calls": 0, "tokens_input": 0, "tokens_output": 0},
            )
            bucket["credits"] += credits
            bucket["calls"] += 1
            bucket["tokens_input"] += r.tokens_input or 0
            bucket["tokens_output"] += r.tokens_output or 0

            day = r.created_at.date().isoformat() if r.created_at else "unknown"
            by_day[day] = by_day.get(day, 0) + credits

        timeline = [
            {"day": day, "credits": value}
            for day, value in sorted(by_day.items())
        ]

        return {
            "user_id": user_id,
            "period_days": days,
            "since": since,
            "total_credits": total_credits,
            "total_tokens_input": total_tokens_in,
            "total_tokens_output": total_tokens_out,
            "by_model": by_model,
            "timeline": timeline,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ensure_balance(self, user_id: int) -> CreditBalance:
        balance = self.db.query(CreditBalance).filter_by(user_id=user_id).first()
        if balance is not None:
            return balance

        user = self.db.query(User).get(user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        tier_cfg = self._get_tier_config(tier_name)
        included = tier_cfg.monthly_credits if tier_cfg else 0

        balance = CreditBalance(
            user_id=user_id,
            included_credits=included,
            used_credits=0,
            overage_credits=0,
            last_reset_at=datetime.now(timezone.utc),
        )
        self.db.add(balance)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(balance)
        return balance

    def _resolve_pricing(self, model: str) -> ModelPricing:
        """
        Look up pricing by exact model name, then by substring fallback on
        opus / sonnet / haiku — same approach as :mod:`budget_service`.
        """
        normalized = _normalize_model_name(model)
        if normalized:
            row = self.db.query(ModelPricing).filter_by(model_name=normalized).first()
            if row is not None and row.is_active:
                return row

        lowered = (normalized or "").lower()
        substring = None
        if "opus" in lowered:
            substring = "opus"
        elif "sonnet" in lowered:
            substring = "sonnet"
        elif "haiku" in lowered:
            substring = "haiku"

        if substring:
            row = (
                self.db.query(ModelPricing)
                .filter(
                    ModelPricing.is_active.is_(True),
                    ModelPricing.model_name.ilike(f"%{substring}%"),
                )
                .order_by(ModelPricing.model_name.asc())
                .first()
            )
            if row is not None:
                return row

        raise UnknownModelError(f"No pricing row for model '{model}'")

    def _get_tier_config(self, tier_name: str) -> Optional[TierConfig]:
        return self.db.query(TierConfig).filter_by(tier_name=tier_name).first()

    def _daily_used_credits(self, user_id: int) -> int:
        """Sum of credits consumed today (UTC) for charge transactions."""
        start = _start_of_day_utc()
        result = (
            self.db.query(func.coalesce(func.sum(CreditTransaction.credits_consumed), 0))
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
                CreditTransaction.created_at >= start,
            )
            .scalar()
        )
        return int(result or 0)
