"""
ProjectDocument model — tracks files uploaded to the project RAG.
Each document is chunked and ingested into ChromaDB with project_id metadata
for isolation between projects.
"""
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ProjectDocument(Base):
    """Uploaded document associated with a project's RAG context."""

    __tablename__ = "project_documents"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # bytes
    content_type = Column(String(100))  # MIME type
    collection_name = Column(String(100), default="technical")  # target ChromaDB collection
    chunk_count = Column(Integer, default=0)
    status = Column(String(50), default="processing")  # processing, ready, error
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    project = relationship("Project", back_populates="documents")
