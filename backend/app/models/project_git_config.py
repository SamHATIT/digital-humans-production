"""
ProjectGitConfig Model - Section 6.3
Git repository configuration per project.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.database import Base


class GitProvider(str, enum.Enum):
    """Git provider types."""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    AZURE_DEVOPS = "azure_devops"


class BranchStrategy(str, enum.Enum):
    """Git branching strategy."""
    TRUNK = "trunk"
    FEATURE_BRANCH = "feature_branch"
    GITFLOW = "gitflow"


class GitConnectionStatus(str, enum.Enum):
    """Git connection status."""
    NOT_TESTED = "not_tested"
    CONNECTED = "connected"
    FAILED = "failed"


class ProjectGitConfig(Base):
    """
    Git repository configuration for a project.
    One config per project (unique constraint).
    """
    __tablename__ = "project_git_config"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Provider
    git_provider = Column(Enum(GitProvider), nullable=False)
    
    # Repository
    repo_url = Column(Text, nullable=False)
    repo_name = Column(String(255))
    default_branch = Column(String(100), default="main")
    
    # Authentication (encrypted - actual token stored in project_credentials)
    access_token_label = Column(String(100))  # Reference to credential
    ssh_key_label = Column(String(100))
    
    # Connection Status
    connection_status = Column(Enum(GitConnectionStatus), default=GitConnectionStatus.NOT_TESTED)
    last_connection_test = Column(DateTime(timezone=True))
    last_connection_error = Column(Text)
    
    # Configuration
    auto_commit = Column(Boolean, default=True)
    commit_message_template = Column(Text, default="[Digital Humans] {action}: {description}")
    branch_strategy = Column(Enum(BranchStrategy), default=BranchStrategy.FEATURE_BRANCH)
    
    # Feature branch naming
    feature_branch_prefix = Column(String(50), default="feature/dh-")
    
    # Metadata
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="git_config")
    
    def __repr__(self):
        return f"<ProjectGitConfig {self.repo_name} ({self.git_provider.value})>"
    
    def get_authenticated_url(self, token: str) -> str:
        """Build authenticated Git URL with token."""
        if not self.repo_url or not token:
            return self.repo_url
        
        url = self.repo_url
        if self.git_provider == GitProvider.GITHUB:
            return url.replace("https://", f"https://{token}@")
        elif self.git_provider == GitProvider.GITLAB:
            return url.replace("https://", f"https://oauth2:{token}@")
        elif self.git_provider == GitProvider.BITBUCKET:
            return url.replace("https://", f"https://x-token-auth:{token}@")
        else:
            return url.replace("https://", f"https://{token}@")
