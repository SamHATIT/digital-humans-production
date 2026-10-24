"""Trace du consentement Opus — GL-22 (vague 2 / file C).

Le site promet « Opus on opt-in, cost shown before each call ». Une ligne par
(exécution, modèle) : qui a décidé, pour quelle exécution, quand, et pour quel
montant affiché. La ligne n'est jamais modifiée : une nouvelle décision pour la
même exécution est refusée par la contrainte d'unicité.

  - ``decision`` : ``accepte`` ou ``refuse`` — aucune autre valeur (contrainte
    CHECK). Un refus est tracé autant qu'une acceptation : c'est lui qui
    justifie le repli sur Sonnet.
  - ``credits_presentes`` : le montant affiché à l'écran, en crédits, que la
    décision soit une acceptation ou un refus (reprise R5).
  - ``credits_estimes`` : le plafond ACCEPTÉ (égal au montant présenté si
    accepté, 0 si refusé). Le routeur ne sert plus Opus pour cette exécution
    dès que le cumul mesuré + l'estimation de l'appel suivant le dépasserait.
  - ``texte_version`` : version du texte de l'écran présenté, pour pouvoir
    dire plus tard ce que l'utilisateur a lu.

Migration : ``023c_consentement_opus``.
"""
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.database import Base

DECISION_ACCEPTE = "accepte"
DECISION_REFUSE = "refuse"
DECISIONS = (DECISION_ACCEPTE, DECISION_REFUSE)


class ConsentementOpus(Base):
    __tablename__ = "opus_consents"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    execution_id = Column(
        Integer, ForeignKey("executions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model_name = Column(String(50), nullable=False)
    decision = Column(String(16), nullable=False)
    credits_estimes = Column(Integer, nullable=False)
    credits_presentes = Column(Integer, nullable=False)
    texte_version = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("execution_id", "model_name", name="uq_opus_consents_execution_modele"),
        CheckConstraint("decision IN ('accepte', 'refuse')", name="ck_opus_consents_decision"),
        CheckConstraint("credits_estimes >= 0", name="ck_opus_consents_credits"),
        CheckConstraint("credits_presentes >= 0", name="ck_opus_consents_presentes"),
    )
