"""
Output model for storing generated specification files.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Output(Base):
    """Output model for storing generated specification files."""

    __tablename__ = "outputs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"), nullable=True)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger)  # File size in bytes
    mime_type = Column(String, default="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="outputs")
    execution = relationship("Execution", back_populates="outputs")
    agent = relationship("Agent", back_populates="outputs")
