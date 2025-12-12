"""
SDSTemplate Model - Section 6.4
Customizable SDS document templates.
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


# Default template structure
DEFAULT_SDS_TEMPLATE = {
    "sections": [
        {"id": "1", "title": "Résumé Exécutif", "required": True},
        {"id": "2", "title": "Contexte Métier", "required": True},
        {"id": "3", "title": "Exigences Métier", "required": True},
        {"id": "4", "title": "Spécifications Fonctionnelles", "required": True},
        {"id": "5", "title": "Architecture Technique", "required": True},
        {"id": "6", "title": "Plan d'Implémentation", "required": True},
        {"id": "7", "title": "Stratégie de Test", "required": False},
        {"id": "8", "title": "Déploiement et Opérations", "required": False},
        {"id": "9", "title": "Formation et Adoption", "required": False},
        {"id": "A", "title": "Annexes", "required": True}
    ]
}


class SDSTemplate(Base):
    """
    SDS document templates.
    Supports custom templates for Enterprise tier.
    """
    __tablename__ = "sds_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(String(50), unique=True, nullable=False, index=True)
    
    # Basic info
    name = Column(String(255), nullable=False)
    description = Column(Text)
    language = Column(String(10), default="fr")
    
    # Template structure (JSON)
    template_structure = Column(JSONB, nullable=False, default=DEFAULT_SDS_TEMPLATE)
    
    # Styling
    header_logo_url = Column(Text)
    primary_color = Column(String(7), default="#1F4E79")
    secondary_color = Column(String(7), default="#2E75B6")
    font_family = Column(String(100), default="Calibri")
    
    # Document settings
    include_toc = Column(Boolean, default=True)
    include_cover_page = Column(Boolean, default=True)
    include_version_history = Column(Boolean, default=True)
    page_numbering = Column(Boolean, default=True)
    
    # Metadata
    is_default = Column(Boolean, default=False)
    is_system = Column(Boolean, default=True)  # False = custom template
    
    # Owner (for custom templates)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id = Column(Integer, nullable=True)  # For enterprise multi-tenant
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    creator = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<SDSTemplate {self.template_id} ({self.name})>"
    
    def get_sections(self):
        """Get list of sections from template structure."""
        return self.template_structure.get("sections", [])
    
    def get_required_sections(self):
        """Get only required sections."""
        return [s for s in self.get_sections() if s.get("required", True)]


# Default templates to seed
SYSTEM_TEMPLATES = [
    {
        "template_id": "default",
        "name": "Template Standard",
        "description": "Template standard pour les documents SDS",
        "language": "fr",
        "template_structure": DEFAULT_SDS_TEMPLATE,
        "is_default": True,
        "is_system": True
    },
    {
        "template_id": "default_en",
        "name": "Standard Template",
        "description": "Standard template for SDS documents",
        "language": "en",
        "template_structure": {
            "sections": [
                {"id": "1", "title": "Executive Summary", "required": True},
                {"id": "2", "title": "Business Context", "required": True},
                {"id": "3", "title": "Business Requirements", "required": True},
                {"id": "4", "title": "Functional Specifications", "required": True},
                {"id": "5", "title": "Technical Architecture", "required": True},
                {"id": "6", "title": "Implementation Plan", "required": True},
                {"id": "7", "title": "Testing Strategy", "required": False},
                {"id": "8", "title": "Deployment & Operations", "required": False},
                {"id": "9", "title": "Training & Adoption", "required": False},
                {"id": "A", "title": "Appendices", "required": True}
            ]
        },
        "is_default": False,
        "is_system": True
    },
    {
        "template_id": "minimal",
        "name": "Template Minimal",
        "description": "Template simplifié pour petits projets",
        "language": "fr",
        "template_structure": {
            "sections": [
                {"id": "1", "title": "Résumé", "required": True},
                {"id": "2", "title": "Exigences", "required": True},
                {"id": "3", "title": "Solution", "required": True},
                {"id": "4", "title": "Planning", "required": True}
            ]
        },
        "is_default": False,
        "is_system": True
    }
]
