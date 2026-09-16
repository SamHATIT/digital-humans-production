"""SDS Version model for document versioning."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SDSVersion(Base):
    """Model for SDS document versions."""
    __tablename__ = "sds_versions"

    # SEC-06 (audit du 06/09, vague 1 / file A) : deux snapshots concurrents du
    # meme projet calculaient le meme `max(version_number)+1`. Aucune
    # contrainte ne l'empechait. L'allocation se fait desormais sous verrou de
    # ligne (routes) et cette contrainte ferme la course restante.
    __table_args__ = (
        UniqueConstraint("project_id", "version_number", name="uq_sds_versions_project_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="SET NULL"), nullable=True)
    version_number = Column(Integer, nullable=False)
    file_path = Column(String(500))
    file_name = Column(String(255))
    file_size = Column(Integer)
    change_request_id = Column(Integer, ForeignKey("change_requests.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    project = relationship("Project", back_populates="sds_versions")
    execution = relationship("Execution", back_populates="sds_versions")
    change_request = relationship("ChangeRequest", back_populates="resulting_sds")
