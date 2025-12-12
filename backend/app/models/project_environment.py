"""
ProjectEnvironment Model - Section 6.2
Manages SFDX environments per project (dev, qa, uat, staging, prod).
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class EnvironmentType(str, enum.Enum):
    """Type of Salesforce environment."""
    DEV = "dev"
    QA = "qa"
    UAT = "uat"
    STAGING = "staging"
    PROD = "prod"


class AuthMethod(str, enum.Enum):
    """Authentication method for SFDX."""
    JWT = "jwt"
    WEB_LOGIN = "web_login"
    PASSWORD = "password"
    ACCESS_TOKEN = "access_token"


class ConnectionStatus(str, enum.Enum):
    """Connection status for environment."""
    NOT_TESTED = "not_tested"
    CONNECTED = "connected"
    FAILED = "failed"
    EXPIRED = "expired"


class ProjectEnvironment(Base):
    """
    Manages Salesforce environments for a project.
    Supports multiple environments (dev, qa, uat, staging, prod).
    """
    __tablename__ = "project_environments"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Identification
    environment_type = Column(Enum(EnvironmentType), nullable=False)
    alias = Column(String(100), nullable=False)
    display_name = Column(String(255))
    
    # Salesforce Connection
    instance_url = Column(Text, nullable=False)
    org_id = Column(String(18))
    username = Column(String(255), nullable=False)
    
    # Authentication (encrypted values stored in project_credentials)
    auth_method = Column(Enum(AuthMethod), default=AuthMethod.WEB_LOGIN, nullable=False)
    
    # Encrypted credentials references (actual values in project_credentials table)
    # These are labels/references, not the actual encrypted values
    client_id_label = Column(String(100))  # e.g., "sf_client_id_dev"
    private_key_label = Column(String(100))
    refresh_token_label = Column(String(100))
    
    # Connection Status
    connection_status = Column(Enum(ConnectionStatus), default=ConnectionStatus.NOT_TESTED)
    last_connection_test = Column(DateTime(timezone=True))
    last_connection_error = Column(Text)
    
    # Metadata
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="environments")
    
    def __repr__(self):
        return f"<ProjectEnvironment {self.alias} ({self.environment_type.value})>"
