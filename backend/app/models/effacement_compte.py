"""
Tâche durable d'effacement RGPD d'un compte — vague 2, file A, RGPD-03
(audit Astra du 06/09, L870).

Un effacement touche trois mondes : Chroma, des fichiers, la base. Les deux
premiers ne sont pas transactionnels. Avant ce modèle, une erreur Chroma était
comptée « zéro chunk », puis les lignes SQL qui désignaient les chunks étaient
détruites : l'effacement devenait partiel ET définitif.

Désormais `AccountService.supprimer` :
  1. désactive le compte et enregistre ici le PÉRIMÈTRE (projets, exécutions,
     documents et leurs collections, fichiers) dans la même transaction ;
  2. purge Chroma puis les fichiers — chaque échec est un échec, noté ici ;
  3. efface/anonymise la base et passe la tâche à `termine` dans UNE
     transaction ; le périmètre détaillé (chemins) est alors réduit à des
     compteurs.
Une tâche `partiel` se reprend (`AccountService.reprendre`,
`reprendre_effacements_en_attente`) ; chaque étape est idempotente.

Données personnelles : le périmètre contient des chemins de fichiers tant que
la tâche n'est pas terminée ; c'est précisément ce qui permet la reprise.
"""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base

STATUT_EN_COURS = "en_cours"
STATUT_PARTIEL = "partiel"
STATUT_TERMINE = "termine"
STATUTS_OUVERTS = (STATUT_EN_COURS, STATUT_PARTIEL)


class EffacementCompte(Base):
    __tablename__ = "effacements_comptes"

    id = Column(Integer, primary_key=True, index=True)
    # La ligne `users` est conservée (anonymisée), la clé reste donc valide ;
    # SET NULL si un jour elle était supprimée.
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    statut = Column(String(20), nullable=False, default=STATUT_EN_COURS, index=True)
    perimetre = Column(JSON, nullable=False, default=dict)
    etapes = Column(JSON, nullable=False, default=dict)
    erreurs = Column(JSON, nullable=False, default=list)
    tentatives = Column(Integer, nullable=False, default=0)
    cree_le = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    maj_le = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    termine_le = Column(DateTime(timezone=True), nullable=True)
