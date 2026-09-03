"""
Routes du compte — droits RGPD (vague B, lot B4).

  GET    /api/account/export  — art. 15 (accès) et art. 20 (portabilité)
  DELETE /api/account         — art. 17 (effacement)

Art. 22 (décision automatisée) : hors périmètre, décision D11 de Sam du 30/08.

Sur l'état du jeton après effacement
------------------------------------
Le JWT est sans état : aucune liste de révocation n'existe. Ce qui le rend
inopérant, c'est `_authenticate_user` (app/utils/dependencies.py:17-62), qui
relit la ligne `users` à chaque appel et refuse un compte inactif. L'effacement
pose `is_active = False` : tout jeton encore valide reçoit alors **403** sur
l'ensemble de l'API — révocation de fait, sans toucher à `auth.py`.

Sur les deux routes de ce fichier, un compte effacé doit répondre **404** et non
403 : il n'existe plus, et un 403 laisserait entendre le contraire. La
dépendance `proprietaire_du_compte` ci-dessous ajoute donc ce seul cas devant
`get_current_user`, à qui elle délègue ensuite toutes les décisions
d'authentification — elle ne réimplémente rien.

Limite connue : la révocation **stricte** d'un jeton encore valide (une liste
noire de `jti`) demanderait de modifier `app/utils/auth.py`, hors périmètre du
lot. Voir la section « Ouvert » du rapport B4.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.account_service import AccountService, est_anonymise
from app.utils.auth import decode_access_token
from app.utils.dependencies import get_current_user, security

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["account", "rgpd"])


def _utilisateur_du_jeton(
    credentials: Optional[HTTPAuthorizationCredentials], db: Session
) -> Optional[User]:
    """Retrouve la ligne `users` visée par le jeton, sans rien décider.

    Ne lève jamais : l'authentification proprement dite reste l'affaire de
    `get_current_user`. Cette fonction sert uniquement à distinguer « compte
    effacé » (404) de « compte désactivé » (403).
    """
    if credentials is None or not credentials.credentials:
        return None
    charge = decode_access_token(credentials.credentials)
    if not charge:
        return None
    identifiant = charge.get("sub")
    try:
        identifiant = int(identifiant)
    except (TypeError, ValueError):
        return None
    return db.query(User).filter(User.id == identifiant).first()


async def proprietaire_du_compte(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """`get_current_user`, plus un 404 pour un compte déjà effacé."""
    utilisateur = _utilisateur_du_jeton(credentials, db)
    if utilisateur is not None and est_anonymise(utilisateur):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte supprimé — aucune donnée à ce nom.",
        )
    return await get_current_user(credentials, db)


@router.get("/export")
async def exporter_mon_compte(
    utilisateur: User = Depends(proprietaire_du_compte),
    db: Session = Depends(get_db),
):
    """RGPD art. 15 et 20 — rend en JSON toutes les données du compte."""
    logger.info("RGPD art.15/20 : export demandé par le compte %s", utilisateur.id)
    return AccountService(db).exporter(utilisateur)


@router.delete("")
async def supprimer_mon_compte(
    utilisateur: User = Depends(proprietaire_du_compte),
    db: Session = Depends(get_db),
):
    """RGPD art. 17 — efface le compte et ce qui en dépend.

    Ce qui doit être conservé pour la comptabilité est anonymisé, pas gardé
    en clair : voir `docs/vague-b/INVENTAIRE_DONNEES_PERSONNELLES.md`.
    """
    logger.info("RGPD art.17 : effacement demandé par le compte %s", utilisateur.id)
    return AccountService(db).supprimer(utilisateur)
