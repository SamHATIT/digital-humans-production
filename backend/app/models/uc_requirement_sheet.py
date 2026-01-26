"""
UC Requirement Sheet model for SDS v3 micro-analysis

Each Use Case is analyzed individually by Mistral Nemo (local, free)
to produce a structured "Fiche Besoin" JSON.
These sheets are then synthesized by Claude for the final SDS.

Version: 1.0.0
Created: 2026-01-26
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UCRequirementSheet(Base):
    """
    Fiche Besoin generated from individual UC analysis.
    
    SDS v3 Pipeline:
    1. Olivia generates UCs
    2. Each UC is analyzed by Nemo → UCRequirementSheet
    3. Claude synthesizes all sheets → Final SDS
    
    Cost optimization: Nemo is free, only Claude synthesis is charged.
    """
    __tablename__ = "uc_requirement_sheets"
    
    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # UC reference
    uc_id = Column(String(50), nullable=False, index=True)  # 'UC-001', 'UC-002', etc.
    uc_title = Column(String(500))                          # Use Case title
    parent_br_id = Column(String(50), index=True)           # Parent BR reference
    
    # Fiche Besoin content (structured JSON)
    sheet_content = Column(JSONB, nullable=False)
    """
    Expected JSON structure:
    {
        "business_context": "...",           # Contexte métier
        "actors": ["..."],                   # Acteurs impliqués
        "sf_objects": [                      # Objets Salesforce
            {"name": "Account", "purpose": "..."}
        ],
        "sf_fields": [                       # Champs requis
            {"object": "Account", "field": "Industry", "type": "Picklist", "required": true}
        ],
        "automations": [                     # Automatisations suggérées
            {"type": "flow", "trigger": "...", "purpose": "..."}
        ],
        "ui_components": [                   # Composants UI
            {"type": "lwc", "name": "...", "purpose": "..."}
        ],
        "acceptance_criteria": ["..."],      # Critères d'acceptation
        "dependencies": ["..."],             # Dépendances UC
        "complexity_score": 3,               # 1-5
        "estimated_effort_hours": 8
    }
    """
    
    # Analysis quality
    analysis_complete = Column(Boolean, default=False)
    analysis_error = Column(Text)           # Error if analysis failed
    confidence_score = Column(Float)        # 0.0-1.0, quality of analysis
    
    # LLM tracking
    llm_provider = Column(String(100))      # 'local/mistral-nemo'
    llm_model = Column(String(100))         # 'mistral-nemo:latest'
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)   # 0 for local
    latency_ms = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    execution = relationship("Execution", back_populates="uc_requirement_sheets")
    
    def __repr__(self):
        return f"<UCRequirementSheet {self.uc_id} - complete={self.analysis_complete}>"
    
    @property
    def sf_object_names(self) -> list:
        """Extract Salesforce object names from sheet"""
        if not self.sheet_content:
            return []
        return [obj.get("name") for obj in self.sheet_content.get("sf_objects", [])]
    
    @property
    def automation_types(self) -> list:
        """Extract automation types from sheet"""
        if not self.sheet_content:
            return []
        return [auto.get("type") for auto in self.sheet_content.get("automations", [])]
