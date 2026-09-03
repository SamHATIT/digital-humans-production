"""
Email-verification tokens (ONBOARDING-002).

We follow a "verify-then-create" flow: the user fills the signup form,
we send them a JWT-encoded link that contains everything needed to
materialise the account on click. No DB row is created until the user
proves they own the email.

Token payload (signed with settings.SECRET_KEY):
- purpose: "signup_verify"  # scoped — never accepted by the access-token verifier
- email, name, hashed_password, requested_tier
- consent_version, consent_ip_hash (vague B / lot B3 — RGPD, see below)
- exp (30 min), iat
- jti (random nonce — for one-shot replay protection if we add a blocklist later)

RGPD (vague B / lot B3): explicit CGV consent is given by the visitor at
signup-request time (the checkbox lives on that form, SignupPage.tsx), not
at signup-confirm time (a bare link click, days later, possibly a different
IP/device). The consent must therefore be captured NOW and carried through
the signed token so `signup_confirm` can materialise it unaltered on the
user row: ``consent_version`` (the CGV text version accepted) and
``consent_ip_hash`` (SHA-256 hex of the visitor's IP, same method as
``sophie_concierge_service._hash_ip`` — never the raw IP). The moment of
consent itself is the token's own ``iat`` — no separate field needed.
``consent_cgv`` is stored as ``True`` defensively: the caller already
validated it before minting the token, but ``decode_signup_token`` requires
the key to exist so a token minted by older code cannot be replayed against
a consent-aware `signup_confirm`.

Why JWT and not a DB table?
- No background cleanup needed (expiration is native).
- No additional schema. Stateless and easy to scale.
- The hashed_password is in the token, never the plaintext, so a leak
  in transit is no worse than a database leak — and the token is
  short-lived (30 min).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt

from app.config import settings


SIGNUP_TOKEN_PURPOSE = "signup_verify"
SIGNUP_TOKEN_TTL_MINUTES = 30


class SignupTokenError(Exception):
    """Raised when a signup-verification token cannot be decoded or is rejected."""


def create_signup_token(
    *,
    email: str,
    name: str,
    hashed_password: str,
    requested_tier: str,
    consent_version: str,
    consent_ip_hash: str,
    ttl_minutes: int = SIGNUP_TOKEN_TTL_MINUTES,
) -> str:
    """Mint a short-lived token that materialises a user when redeemed.

    ``consent_version``/``consent_ip_hash`` are required keyword args (no
    default) so a caller cannot mint a signup token without having already
    validated explicit CGV consent — see module docstring (RGPD, lot B3).
    """
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "purpose": SIGNUP_TOKEN_PURPOSE,
        "email": email,
        "name": name,
        "hashed_password": hashed_password,
        "requested_tier": requested_tier,
        "consent_cgv": True,
        "consent_version": consent_version,
        "consent_ip_hash": consent_ip_hash,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "jti": secrets.token_urlsafe(12),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_signup_token(token: str) -> Dict[str, Any]:
    """Validate and return the signup payload.

    Raises ``SignupTokenError`` for any reason a token should be rejected
    (expired, wrong purpose, malformed). Callers should map this to a
    generic 400 response so we don't leak which condition failed.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise SignupTokenError("token_expired") from exc
    except jwt.InvalidTokenError as exc:
        raise SignupTokenError("token_invalid") from exc

    # Purpose-scoping: prevents an access token (or any other token signed with
    # the same secret) from being smuggled into /signup-confirm.
    if payload.get("purpose") != SIGNUP_TOKEN_PURPOSE:
        raise SignupTokenError("token_wrong_purpose")

    required = {
        "email", "name", "hashed_password", "requested_tier",
        "consent_cgv", "consent_version", "consent_ip_hash",
    }
    missing = required - set(payload.keys())
    if missing:
        raise SignupTokenError(f"token_missing_fields:{','.join(sorted(missing))}")

    return payload
