"""
Credit ledger models — Phase 3.1 of MASTER_PLAN_V4.

1 credit = 1 000 input tokens of Claude Sonnet equivalent.
- Haiku   : 0.3x input / 1.5x output
- Sonnet  : 1.0x input / 5.0x output
- Opus    : 5.0x input / 25.0x output

Tables :
    credit_balances     — current balance per user (1 row / user)
    credit_transactions — audit log of every charge/refund/reset
    model_pricing       — per-model credit cost + tier authorization (seed)
    tier_config         — monthly allotment & daily cap per tier (seed)
"""
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import backref, relationship
from sqlalchemy.sql import func

from app.database import Base


# Transaction type constants (kept as plain strings — DB stores VARCHAR(20))
TRANSACTION_TYPE_CHARGE = "charge"
TRANSACTION_TYPE_REFUND = "refund"
TRANSACTION_TYPE_RESET = "reset"
TRANSACTION_TYPE_ADJUSTMENT = "adjustment"


class CreditBalance(Base):
    """Current credit balance for a user. Exactly one row per user."""

    __tablename__ = "credit_balances"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    included_credits = Column(Integer, nullable=False, default=0, server_default="0")
    used_credits = Column(Integer, nullable=False, default=0, server_default="0")
    overage_credits = Column(Integer, nullable=False, default=0, server_default="0")
    last_reset_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship(
        "User",
        backref=backref("credit_balance", uselist=False),
    )

    @property
    def available(self) -> int:
        return max(0, (self.included_credits or 0) + (self.overage_credits or 0) - (self.used_credits or 0))


class CreditTransaction(Base):
    """Append-only ledger of every credit movement."""

    __tablename__ = "credit_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_type = Column(String(20), nullable=False)
    model_used = Column(String(50))
    tokens_input = Column(Integer)
    tokens_output = Column(Integer)
    credits_consumed = Column(Integer, nullable=False)
    execution_id = Column(
        Integer,
        ForeignKey("executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    note = Column(Text)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("idx_credit_transactions_user", "user_id", "created_at"),
        Index("idx_credit_transactions_execution", "execution_id"),
    )


class ModelPricing(Base):
    """Per-model credit cost + tier authorization. Seeded in the migration."""

    __tablename__ = "model_pricing"

    model_name = Column(String(50), primary_key=True)
    credits_per_1k_input = Column(Numeric(10, 3), nullable=False)
    credits_per_1k_output = Column(Numeric(10, 3), nullable=False)
    allowed_tiers = Column(String(255), nullable=False)  # CSV: "free,pro,team"
    requires_opt_in = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def tier_allowed(self, tier_name: str) -> bool:
        if not self.allowed_tiers:
            return False
        allowed = {t.strip() for t in self.allowed_tiers.split(",")}
        return tier_name in allowed


class TierConfig(Base):
    """Monthly allotment + daily cap + price per tier. Seeded in the migration."""

    __tablename__ = "tier_config"

    tier_name = Column(String(20), primary_key=True)
    monthly_credits = Column(Integer, nullable=False)
    daily_credits_cap = Column(Integer, nullable=True)
    price_eur_monthly = Column(Numeric(10, 2), nullable=False)
    description = Column(Text)
