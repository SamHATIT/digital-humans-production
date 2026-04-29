"""
User model for authentication and user management.
Updated 29 avril 2026 : 4-tier subscription model (free / pro / team / enterprise).
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    """User model for storing user account information."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # 4-tier freemium model — values: free / pro / team / enterprise
    # Validated at application level (see app.models.subscription.SubscriptionTier).
    subscription_tier = Column(String(20), default="free", nullable=False, server_default="free")

    # Subscription metadata
    subscription_started_at = Column(DateTime(timezone=True))
    subscription_expires_at = Column(DateTime(timezone=True))
    stripe_customer_id = Column(String(255))  # Created on first checkout / signup hook

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.email} ({self.subscription_tier})>"

    # ------------------------------------------------------------------
    # Tier predicates
    # ------------------------------------------------------------------

    @property
    def tier(self):
        """Return the user's tier as a SubscriptionTier enum (defaults to FREE)."""
        from app.models.subscription import SubscriptionTier
        try:
            return SubscriptionTier(self.subscription_tier)
        except ValueError:
            return SubscriptionTier.FREE

    @property
    def is_free(self) -> bool:
        return self.subscription_tier == "free"

    @property
    def is_pro(self) -> bool:
        return self.subscription_tier == "pro"

    @property
    def is_team(self) -> bool:
        return self.subscription_tier == "team"

    @property
    def is_enterprise(self) -> bool:
        return self.subscription_tier == "enterprise"

    @property
    def has_build_access(self) -> bool:
        """Tiers that can run the BUILD phase (Apex/LWC/Admin generation + SFDX)."""
        return self.subscription_tier in ("team", "enterprise")

    @property
    def has_full_team_access(self) -> bool:
        """Tiers that can talk to all 11 agents (not just Sophie + Olivia)."""
        return self.subscription_tier in ("pro", "team", "enterprise")

    @property
    def is_paying(self) -> bool:
        """Any tier above Free."""
        return self.subscription_tier != "free"

    # ------------------------------------------------------------------
    # Backward-compatibility shims (DEPRECATED — to be removed once all
    # callers migrate to the explicit predicates above).
    # ------------------------------------------------------------------

    @property
    def is_premium(self) -> bool:
        """DEPRECATED. Old 3-tier semantic: 'has BUILD access'.

        Kept for compatibility while migrating callers. New code should use
        :attr:`has_build_access` (semantic) or :attr:`is_pro` / :attr:`is_team`
        (concrete tier check).
        """
        return self.has_build_access
