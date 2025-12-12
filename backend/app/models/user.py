"""
User model for authentication and user management.
Updated with subscription tier for freemium model (Section 9).
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

    # Section 9: Subscription tier for freemium model
    # Using VARCHAR for flexibility, validated at application level
    subscription_tier = Column(String(20), default="free", nullable=False, server_default='free')
    
    # Subscription metadata
    subscription_started_at = Column(DateTime(timezone=True))
    subscription_expires_at = Column(DateTime(timezone=True))
    stripe_customer_id = Column(String(255))  # For payment integration

    # Relationships
    projects = relationship("Project", back_populates="user", cascade="all, delete-orphan")
    executions = relationship("Execution", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User {self.email} ({self.subscription_tier})>"
    
    @property
    def is_premium(self) -> bool:
        """Check if user has premium or enterprise subscription."""
        return self.subscription_tier in ["premium", "enterprise"]
    
    @property
    def is_enterprise(self) -> bool:
        """Check if user has enterprise subscription."""
        return self.subscription_tier == "enterprise"
    
    @property
    def tier(self):
        """Get subscription tier as enum."""
        from app.models.subscription import SubscriptionTier
        try:
            return SubscriptionTier(self.subscription_tier)
        except ValueError:
            return SubscriptionTier.FREE
