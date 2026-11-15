"""Jetons de reinitialisation du mot de passe (15/11/2026).

Sans etat, comme les jetons d'inscription (email_token.py) : JWT signe par
SECRET_KEY, valable 30 minutes, avec un `purpose` qui le rend inutilisable
comme jeton d'acces.

**Usage unique sans table** : le jeton porte une empreinte du hash du mot de
passe ACTUEL. Des que le mot de passe change (par ce lien ou autrement),
l'empreinte ne correspond plus et tout lien emis avant est refuse.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt

from app.config import settings

PASSWORD_RESET_PURPOSE = "password_reset"
PASSWORD_RESET_TTL_MINUTES = 30


class PasswordResetTokenError(Exception):
    """Jeton de reinitialisation illisible, expire, detourne ou deja utilise."""


def empreinte_mot_de_passe(hashed_password: str) -> str:
    """Empreinte courte du hash courant : change des que le mot de passe change."""
    return hashlib.sha256((hashed_password or "").encode()).hexdigest()[:24]


def create_password_reset_token(*, user_id: int, email: str, hashed_password: str,
                                ttl_minutes: int = PASSWORD_RESET_TTL_MINUTES) -> str:
    maintenant = datetime.now(timezone.utc)
    payload = {
        "purpose": PASSWORD_RESET_PURPOSE,
        "uid": int(user_id),          # pas `sub` : ce jeton n'est jamais un jeton d'acces
        "email": email,
        "pwf": empreinte_mot_de_passe(hashed_password),
        "iat": int(maintenant.timestamp()),
        "exp": int((maintenant + timedelta(minutes=ttl_minutes)).timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise PasswordResetTokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise PasswordResetTokenError("token_invalid") from exc
    if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise PasswordResetTokenError("token_wrong_purpose")
    for cle in ("uid", "email", "pwf"):
        if not payload.get(cle):
            raise PasswordResetTokenError("token_incomplete")
    return payload
