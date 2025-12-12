"""
Project model for managing user projects and requirements.
Enhanced for Wizard Configuration (Phase 5).
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class ProjectStatus(str, enum.Enum):
    """Project status enumeration."""
    DRAFT = "draft"
    READY = "ready"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"
    # Post-SDS workflow statuses
    SDS_GENERATED = "sds_generated"
    SDS_IN_REVIEW = "sds_in_review"
    SDS_APPROVED = "sds_approved"
    BUILD_READY = "build_ready"
    BUILD_IN_PROGRESS = "build_in_progress"
    BUILD_COMPLETED = "build_completed"


class ProjectType(str, enum.Enum):
    """Type of Salesforce project."""
    GREENFIELD = "greenfield"      # New implementation from scratch
    EXISTING = "existing"          # Evolution of existing org


class TargetObjective(str, enum.Enum):
    """Project target objective."""
    SDS_ONLY = "sds_only"          # Only generate SDS document
    SDS_AND_BUILD = "sds_and_build"  # Generate SDS + automated build


class Project(Base):
    """Project model for storing project information and requirements."""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # ========================================
    # STEP 1: Basic Information
    # ========================================
    name = Column(String(200), nullable=False)
    description = Column(Text)
    project_code = Column(String(50))  # Internal project code (e.g., "PRJ-2025-001")
    
    # Client information
    client_name = Column(String(200))
    client_contact_name = Column(String(200))
    client_contact_email = Column(String(200))
    client_contact_phone = Column(String(50))
    
    # Timeline
    start_date = Column(DateTime(timezone=True))
    end_date = Column(DateTime(timezone=True))

    # ========================================
    # STEP 2: Project Type
    # ========================================
    project_type = Column(Enum(ProjectType), default=ProjectType.GREENFIELD)
    salesforce_product = Column(String(100))  # Service Cloud, Sales Cloud, etc.
    organization_type = Column(String(100))   # Legacy - kept for compatibility

    # ========================================
    # STEP 3: Target Objective
    # ========================================
    target_objective = Column(Enum(TargetObjective), default=TargetObjective.SDS_ONLY)
    is_premium = Column(Boolean, default=False)  # Premium account for BUILD

    # ========================================
    # STEP 4: Salesforce Connection (if existing org)
    # ========================================
    sf_instance_url = Column(String(500))     # e.g., https://mycompany.my.salesforce.com
    sf_username = Column(String(200))
    sf_connected = Column(Boolean, default=False)
    sf_connection_date = Column(DateTime(timezone=True))
    sf_org_id = Column(String(50))            # 18-char org ID when connected
    # Note: sf_access_token stored in encrypted_credentials table

    # ========================================
    # STEP 5: Git Repository (if BUILD)
    # ========================================
    git_repo_url = Column(String(500))        # e.g., https://github.com/org/repo
    git_branch = Column(String(100), default="main")
    git_connected = Column(Boolean, default=False)
    git_connection_date = Column(DateTime(timezone=True))
    # Note: git_token stored in encrypted_credentials table

    # ========================================
    # Business Requirements (3-7 lines max)
    # ========================================
    business_requirements = Column(Text)

    # Technical Context (optional)
    existing_systems = Column(Text)
    compliance_requirements = Column(Text)
    expected_users = Column(Integer)
    expected_data_volume = Column(String(100))

    # Architecture Preferences (stored as JSON)
    architecture_preferences = Column(JSON)
    architecture_notes = Column(Text)

    # ========================================
    # Agent Configuration
    # ========================================
    # Selected SDS expert agents (JSON array of agent_ids)
    # Default: ["qa", "devops", "data", "trainer"]
    selected_sds_agents = Column(JSON, default=["qa", "devops", "data", "trainer"])
    
    # Custom agent parameters (JSON object)
    agent_parameters = Column(JSON)

    # ========================================
    # Wizard Progress Tracking
    # ========================================
    wizard_step = Column(Integer, default=1)  # Current wizard step (1-6)
    wizard_completed = Column(Boolean, default=False)

    # Legacy fields (for backwards compatibility)
    requirements_text = Column(Text)
    requirements_file_path = Column(String)

    # ========================================
    # Metadata
    # ========================================
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT, nullable=False)
    current_sds_version = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # ========================================
    # Relationships
    # ========================================
    user = relationship("User", back_populates="projects")
    executions = relationship("Execution", back_populates="project", cascade="all, delete-orphan")
    outputs = relationship("Output", back_populates="project", cascade="all, delete-orphan")
    br_items = relationship("BusinessRequirement", back_populates="project", cascade="all, delete-orphan")
    # Post-SDS workflow relationships
    sds_versions = relationship("SDSVersion", back_populates="project", cascade="all, delete-orphan")
    change_requests = relationship("ChangeRequest", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("ProjectConversation", back_populates="project", cascade="all, delete-orphan")
    # Credentials relationship
    credentials = relationship("ProjectCredential", back_populates="project", cascade="all, delete-orphan")
    
    # Section 6.2: Multi-environment support
    environments = relationship("ProjectEnvironment", back_populates="project", cascade="all, delete-orphan")
    
    # Section 6.3: Git configuration (one per project)
    git_config = relationship("ProjectGitConfig", back_populates="project", uselist=False, cascade="all, delete-orphan")
