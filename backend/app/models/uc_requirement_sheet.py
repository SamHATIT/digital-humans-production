"""
UC Requirement Sheet model - Stockage des Fiches Besoin générées par micro-analyse (SDS v3)
Chaque UC analysé par LLM local produit une fiche stockée ici.
"""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UCRequirementSheet(Base):
    """Fiche Besoin générée pour chaque Use Case - SDS v3 Pipeline"""

    __tablename__ = "uc_requirement_sheets"

    id = Column(Integer, primary_key=True, index=True)
    
    # Relations
    execution_id = Column(Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Identifiant UC source (UC-001, etc.)
    uc_id = Column(String(50), nullable=False, index=True)
    uc_title = Column(String(500))
    parent_br_id = Column(String(50), index=True)  # BR parent (BR-001, etc.)
    
    # Contenu complet de la fiche (JSON)
    # Structure: {titre, acteur, objectif, objets_salesforce, champs_cles, 
    #             automatisations, regles_metier, complexite, agent_suggere, justification_agent}
    sheet_content = Column(JSON, nullable=False)
    
    # Status analyse
    analysis_complete = Column(Boolean, default=False)
    analysis_error = Column(Text)
    confidence_score = Column(Float)  # 0.0 - 1.0
    
    # Méta-données LLM
    llm_provider = Column(String(100))  # ollama/mistral-7b, anthropic/haiku, etc.
    llm_model = Column(String(100))
    tokens_in = Column(Integer, default=0)
    tokens_out = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relation vers Execution (back_populates défini dans execution.py)
    execution = relationship("Execution", back_populates="uc_requirement_sheets")
    
    def to_dict(self):
        """Sérialisation complète pour API"""
        content = self.sheet_content or {}
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "uc_id": self.uc_id,
            "uc_title": self.uc_title,
            "parent_br_id": self.parent_br_id,
            "titre": content.get("titre", self.uc_title),
            "acteur": content.get("acteur", ""),
            "objectif": content.get("objectif", ""),
            "objets_salesforce": content.get("objets_salesforce", []),
            "champs_cles": content.get("champs_cles", []),
            "automatisations": content.get("automatisations", []),
            "regles_metier": content.get("regles_metier", []),
            "complexite": content.get("complexite", "moyenne"),
            "agent_suggere": content.get("agent_suggere", "raj"),
            "justification_agent": content.get("justification_agent", ""),
            "analysis_complete": self.analysis_complete,
            "llm_provider": self.llm_provider,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd
        }
    
    def to_sds_format(self):
        """Format compact pour inclusion dans le SDS/WBS"""
        content = self.sheet_content or {}
        return {
            "uc_id": self.uc_id,
            "titre": content.get("titre", self.uc_title),
            "objets": content.get("objets_salesforce", []),
            "champs": content.get("champs_cles", []),
            "automatisations": content.get("automatisations", []),
            "agent": content.get("agent_suggere", "raj"),
            "complexite": content.get("complexite", "moyenne")
        }
