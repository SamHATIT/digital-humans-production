"""
ProjectCredential model for storing encrypted credentials.
Used for Salesforce and Git connections.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class CredentialType(str, enum.Enum):
    """Type of credential."""
    SALESFORCE_TOKEN = "salesforce_token"
    SALESFORCE_REFRESH_TOKEN = "salesforce_refresh_token"
    GIT_TOKEN = "git_token"
    GIT_SSH_KEY = "git_ssh_key"


class ProjectCredential(Base):
    """Encrypted credentials storage for project connections."""
    
    __tablename__ = "project_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    credential_type = Column(Enum(CredentialType), nullable=False)
    
    # Encrypted value (using Fernet symmetric encryption)
    encrypted_value = Column(Text, nullable=False)
    
    # Metadata
    label = Column(String(200))  # User-friendly label
    expires_at = Column(DateTime(timezone=True))  # Token expiration
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationship
    project = relationship("Project", back_populates="credentials")
