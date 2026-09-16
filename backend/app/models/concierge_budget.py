"""
Budget opérationnel du concierge public — BILL-09 (vague 1 / file B, L777).

Le plafond de dépense du concierge était la somme de ``chat_logs.cost_usd``.
Or ``POST /api/public/concierge/forget`` supprime ces lignes : le visiteur
effaçait le garde-fou en exerçant son droit à l'effacement. Les deux besoins
sont légitimes et incompatibles dans la même table.

D'où une table séparée, **sans aucune donnée personnelle** : un compteur par
jour, que l'effacement RGPD ne touche pas et n'a aucune raison de toucher. Elle
ne porte ni identifiant de session, ni adresse, ni message — seulement des
totaux.

Le total du jour sert aussi de point de sérialisation : la vérification du
plafond et la dépense se font sous ``SELECT … FOR UPDATE`` de la ligne du
jour, ce qui empêche N tours simultanés de passer sur le même reste.
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, Integer
from sqlalchemy.sql import func

from app.database import Base


class ConciergeBudgetJour(Base):
    """Un jour = une ligne. Aucune donnée personnelle."""

    __tablename__ = "concierge_budget_jours"

    jour = Column(Date, primary_key=True)
    # Dépense du jour en micro-dollars (même unité que chat_logs.cost_usd).
    cout_micro_usd = Column(BigInteger, nullable=False, default=0, server_default="0")
    # Nombre de tours servis : un coût monétaire nul n'est pas une capacité
    # infinie (le modèle local ne coûte rien mais occupe le GPU).
    requetes = Column(Integer, nullable=False, default=0, server_default="0")
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now(), onupdate=func.now())
