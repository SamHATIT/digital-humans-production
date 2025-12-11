"""
Audit Log Model - Comprehensive logging of all system activities.
CORE-001: Essential for debugging, security, and incremental execution.
"""
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database import Base


class ActorType(str, Enum):
    """Who performed the action"""
    USER = "user"           # Human user via API/UI
    AGENT = "agent"         # AI agent (Sophie, Marcus, Diego, etc.)
    SYSTEM = "system"       # Background job, scheduler, webhook
    API = "api"             # External API call


class ActionCategory(str, Enum):
    """High-level action categories"""
    # Project lifecycle
    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"
    
    # Execution lifecycle
    EXECUTION_START = "execution.start"
    EXECUTION_PAUSE = "execution.pause"
    EXECUTION_RESUME = "execution.resume"
    EXECUTION_COMPLETE = "execution.complete"
    EXECUTION_FAIL = "execution.fail"
    EXECUTION_CANCEL = "execution.cancel"
    
    # Agent activities
    AGENT_START = "agent.start"
    AGENT_COMPLETE = "agent.complete"
    AGENT_FAIL = "agent.fail"
    AGENT_SKIP = "agent.skip"
    
    # BUILD phase
    TASK_START = "task.start"
    TASK_DEPLOY = "task.deploy"
    TASK_TEST = "task.test"
    TASK_COMMIT = "task.commit"
    TASK_COMPLETE = "task.complete"
    TASK_FAIL = "task.fail"
    TASK_RETRY = "task.retry"
    TASK_SKIP = "task.skip"
    
    # LLM interactions
    LLM_REQUEST = "llm.request"
    LLM_RESPONSE = "llm.response"
    LLM_ERROR = "llm.error"
    
    # SFDX operations
    SFDX_DEPLOY = "sfdx.deploy"
    SFDX_TEST = "sfdx.test"
    SFDX_RETRIEVE = "sfdx.retrieve"
    SFDX_ERROR = "sfdx.error"
    
    # Git operations
    GIT_CLONE = "git.clone"
    GIT_COMMIT = "git.commit"
    GIT_PUSH = "git.push"
    GIT_PR_CREATE = "git.pr_create"
    GIT_PR_MERGE = "git.pr_merge"
    GIT_ERROR = "git.error"
    
    # Data modifications
    DATA_CREATE = "data.create"
    DATA_UPDATE = "data.update"
    DATA_DELETE = "data.delete"
    
    # BR/UC validation
    BR_VALIDATE = "br.validate"
    BR_REJECT = "br.reject"
    UC_VALIDATE = "uc.validate"
    UC_REJECT = "uc.reject"
    
    # Authentication
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAIL = "auth.fail"
    
    # Generic
    OTHER = "other"


class AuditLog(Base):
    """
    Central audit log for all system activities.
    
    Enables:
    - Debugging: trace what happened and when
    - Security: audit trail for compliance
    - Analytics: understand system usage patterns
    - Recovery: identify what needs to be re-done after failures
    """
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # When
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Who
    actor_type = Column(String(20), nullable=False, index=True)  # ActorType enum value
    actor_id = Column(String(100), nullable=True, index=True)    # user_id, agent_id, or system identifier
    actor_name = Column(String(200), nullable=True)              # Human-readable name
    
    # What
    action = Column(String(50), nullable=False, index=True)      # ActionCategory enum value
    action_detail = Column(String(500), nullable=True)           # Additional description
    
    # On what
    entity_type = Column(String(50), nullable=True, index=True)  # project, execution, task, br, etc.
    entity_id = Column(String(100), nullable=True, index=True)   # ID of the entity
    entity_name = Column(String(500), nullable=True)             # Human-readable name
    
    # Changes (for data modifications)
    old_value = Column(JSONB, nullable=True)                     # Previous state
    new_value = Column(JSONB, nullable=True)                     # New state
    
    # Context
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="SET NULL"), nullable=True, index=True)
    task_id = Column(String(50), nullable=True, index=True)      # For BUILD tasks
    
    # Additional metadata
    extra_data = Column(JSONB, nullable=True)                      # Flexible additional data
    
    # Request context (for API calls)
    request_id = Column(String(100), nullable=True)              # Correlation ID
    ip_address = Column(String(45), nullable=True)               # Client IP
    user_agent = Column(String(500), nullable=True)              # Browser/client info
    
    # Outcome
    success = Column(String(10), default="true")                 # true, false, partial
    error_message = Column(Text, nullable=True)                  # If failed
    duration_ms = Column(Integer, nullable=True)                 # Operation duration
    
    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_audit_project_timestamp', 'project_id', 'timestamp'),
        Index('ix_audit_execution_timestamp', 'execution_id', 'timestamp'),
        Index('ix_audit_actor_action', 'actor_type', 'action'),
        Index('ix_audit_entity', 'entity_type', 'entity_id'),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.id} {self.action} by {self.actor_type}:{self.actor_id}>"
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "action": self.action,
            "action_detail": self.action_detail,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "project_id": self.project_id,
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "extra_data": self.extra_data,
            "success": self.success,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
        }
