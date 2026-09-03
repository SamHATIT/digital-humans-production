"""
Authentication routes for user registration, login, and profile management.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session

import hashlib
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserLogin, User as UserSchema, Token,
    SignupRequest, SignupConfirm,
)
from app.utils.auth import verify_password, get_password_hash, create_access_token
from app.utils.dependencies import get_current_user
from app.utils.email_token import (
    create_signup_token, decode_signup_token, SignupTokenError,
)
from app.services.email_sender import send_signup_verification_email
from app.rate_limiter import limiter, RateLimits, get_client_ip

logger = logging.getLogger(__name__)

# ONBOARDING-002: tiers that can sign up self-serve (mirror of the same set
# in the legacy /register endpoint — kept in sync explicitly).
SELF_SERVE_TIERS = {"free"}

# ─────────────────────────────────────────────────────────────────────
# RGPD — vague B / lot B3 : consentement CGV explicite a l'inscription
# ─────────────────────────────────────────────────────────────────────
#
# Version du texte CGV/politique de confidentialite couverte par ce
# consentement. Doit correspondre exactement a la constante CGV_VERSION du
# frontend (frontend/src/pages/SignupPage.tsx) : la faire correspondre est
# un choix delibere ci-dessous (repli refuse, pas silencieux) plutot que de
# faire confiance au client. A incrementer manuellement si le texte des CGV
# ou de la politique de confidentialite change.
CURRENT_TERMS_VERSION = "2026-08-30"  # date de publication des CGV / legal / privacy (Sam + Legal). Pas un numero arbitraire.

# kim:COH-05 (meme regle que sophie_concierge_service.IP_SALT) — aucun
# defaut public : un sel connu rendrait les hachages d'IP reversibles par
# dictionnaire, ce qui viderait la protection RGPD de son sens.
IP_SALT = os.getenv("CHAT_IP_SALT", "")


def _hash_consent_ip(ip: str) -> str:
    """SHA-256 hex de (ip + sel) — meme methode que
    ``sophie_concierge_service._hash_ip`` (chat_logs.ip_hash), reutilisee
    ici pour ``users.consent_ip_hash``. Jamais l'IP en clair en base.

    Leve ``RuntimeError`` si ``CHAT_IP_SALT`` n'est pas configure : hacher
    avec un sel vide ne protegerait rien (regle 6, jamais de repli
    silencieux).
    """
    if not IP_SALT:
        raise RuntimeError(
            "CHAT_IP_SALT is not configured — refusing to hash the consent "
            "IP with an empty salt. Set CHAT_IP_SALT in the backend "
            "environment."
        )
    return hashlib.sha256(f"{ip}{IP_SALT}".encode("utf-8")).hexdigest()


def _consent_ip_hash_or_503(request: Request, where: str) -> str:
    """Wrap ``_hash_consent_ip`` for a route handler: turn the RuntimeError
    above into a loud, explicit 500 rather than letting an unconfigured
    salt crash unhandled or silently fall back to no hash."""
    try:
        return _hash_consent_ip(get_client_ip(request))
    except RuntimeError as exc:
        logger.error("[%s] cannot hash consent IP: %s", where, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="signup_temporarily_unavailable",
        ) from exc


def _require_consent(consent_cgv: bool, consent_version: Optional[str]) -> None:
    """Reject signup with no explicit, correctly-versioned CGV consent.

    Regle 6 (jamais de repli silencieux) : un consentement manquant/faux, ou
    une version qui ne correspond pas a ce que le backend sert aujourd'hui,
    est refuse avec un message nommant ce qui a ete recu et ce qui est
    attendu — jamais suppose « accepte » ou coerce vers la version courante.
    """
    if not consent_cgv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Vous devez accepter explicitement les CGV et la politique "
                "de confidentialite pour creer un compte (consent_cgv "
                "manquant ou faux)."
            ),
        )
    if consent_version != CURRENT_TERMS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"consent_version invalide : recu {consent_version!r}, "
                f"attendu {CURRENT_TERMS_VERSION!r}."
            ),
        )


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimits.AUTH_REGISTER)
async def register(request: Request, response: Response, user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Args:
        user_data: User registration data (email, name, password)
        db: Database session

    Returns:
        Created user data

    Raises:
        HTTPException: If email already exists
    """
    # Check if user with email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # RGPD (lot B3) — consentement CGV explicite obligatoire avant toute
    # creation de compte, y compris sur ce chemin legacy.
    _require_consent(user_data.consent_cgv, user_data.consent_version)
    consent_ip_hash = _consent_ip_hash_or_503(request, "register")

    # Resolve the requested tier (ONBOARDING-001) — only `free` is self-serve
    # for now. Pro/Team need a Stripe checkout flow which doesn't bypass /register
    # (so we don't trust an arbitrary `requested_tier=pro` from the wire).
    SELF_SERVE_TIERS = {"free"}
    resolved_tier = "free"
    if user_data.requested_tier and user_data.requested_tier in SELF_SERVE_TIERS:
        resolved_tier = user_data.requested_tier

    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        email=user_data.email,
        name=user_data.name,
        hashed_password=hashed_password,
        is_active=True,
        subscription_tier=resolved_tier,
        consent_cgv_at=datetime.now(timezone.utc),
        consent_version=user_data.consent_version,
        consent_ip_hash=consent_ip_hash,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Create a Stripe Customer right at signup so the user can upgrade with
    # one click later. Best-effort : if Stripe is unreachable or misconfigured,
    # don't block the signup — the customer can still be created lazily on
    # the first checkout call (create_customer is idempotent).
    try:
        from app.services.stripe_service import create_customer, is_configured, StripeNotConfiguredError
        if is_configured():
            create_customer(new_user, db)
    except StripeNotConfiguredError:
        pass  # Stripe not set up in this environment, skip
    except Exception as exc:  # noqa: BLE001
        # Log and move on — signup must not fail because of Stripe.
        import logging
        logging.getLogger(__name__).warning(
            "Stripe customer creation failed for user %s: %s", new_user.id, exc
        )

    return new_user


@router.post("/signup-request", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(RateLimits.AUTH_SIGNUP_REQUEST)
async def signup_request(
    request: Request,
    response: Response,
    body: SignupRequest,
    db: Session = Depends(get_db),
):
    """First step of the verify-then-create signup flow (ONBOARDING-002).

    We hash the password and pack everything into a short-lived JWT, then
    email a link to the user. No row in `users` until the link is clicked.

    Returns 202 Accepted with a generic message in all cases — including
    when the email is already registered — so we don't leak account
    existence to scrapers.
    """
    # RGPD (lot B3) — consent is given HERE, on this form (SignupPage.tsx
    # renders the checkbox next to this call). Validate and hash the IP
    # before anything else: a rejected consent must not depend on whether
    # the email is already taken (anti-enumeration cuts both ways).
    _require_consent(body.consent_cgv, body.consent_version)
    consent_ip_hash = _consent_ip_hash_or_503(request, "signup-request")

    # Resolve the requested tier with the same fallback rules as /register.
    resolved_tier = "free"
    if body.requested_tier and body.requested_tier in SELF_SERVE_TIERS:
        resolved_tier = body.requested_tier

    # If the email is already in use, silently no-op (and log) — anti-enumeration.
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        logger.info(
            "[signup-request] email already registered (silent no-op): %s",
            body.email,
        )
        return {"status": "ok", "message": "If the address is valid, a confirmation email is on its way."}

    # Hash the password NOW — the hash travels in the signed token.
    hashed_password = get_password_hash(body.password)

    # Consent proof travels through the token too (RGPD, lot B3): the
    # moment of consent is this request, not the later signup-confirm click,
    # so consent_version/consent_ip_hash must be captured now and carried
    # unaltered — see app/utils/email_token.py docstring.
    token = create_signup_token(
        email=body.email,
        name=body.name.strip(),
        hashed_password=hashed_password,
        requested_tier=resolved_tier,
        consent_version=body.consent_version,
        consent_ip_hash=consent_ip_hash,
    )

    base_url = os.getenv("STUDIO_PUBLIC_URL", "https://app.digital-humans.fr").rstrip("/")
    verify_url = f"{base_url}/verify-signup?token={token}"

    try:
        send_signup_verification_email(
            to_email=body.email,
            to_name=body.name.strip(),
            verify_url=verify_url,
            lang=(body.lang or "fr"),
        )
    except Exception as exc:  # noqa: BLE001 — never block signup on mailer failure
        logger.exception("[signup-request] mail send failed for %s: %s", body.email, exc)
        # Still return success — the user will retry, and we don't want to leak
        # the mailer state. The log is enough for ops to investigate.

    return {"status": "ok", "message": "If the address is valid, a confirmation email is on its way."}


@router.post("/signup-confirm", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit(RateLimits.AUTH_SIGNUP_CONFIRM)
async def signup_confirm(
    request: Request,
    response: Response,
    body: SignupConfirm,
    db: Session = Depends(get_db),
):
    """Second step — redeem the verify-token, create the user, log them in.

    Returns the same Token shape as /login so the frontend can store it and
    redirect to the Studio without an extra round-trip.
    """
    try:
        payload = decode_signup_token(body.token)
    except SignupTokenError as exc:
        # Generic 400 — don't tell the client whether the token was expired or
        # malformed (no information value, just attack surface).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        ) from exc

    email = payload["email"]
    name = payload["name"]
    hashed_password = payload["hashed_password"]
    resolved_tier = payload["requested_tier"]

    # RGPD (lot B3) — defensive re-check: the signed token is trusted, but a
    # token minted by pre-B3 code (or a hand-crafted payload, which the
    # signature would already reject) must not silently pass through as
    # "consented". Same generic 400 as any other rejected token — we don't
    # want to give a forger a signal about which field tripped.
    if not payload.get("consent_cgv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        )
    consent_version = payload["consent_version"]
    consent_ip_hash = payload["consent_ip_hash"]
    # The consent moment is when the visitor checked the box and submitted
    # signup-request, i.e. this token's own issuance time — not "now" (this
    # confirm click can happen minutes later, from a different IP/device).
    consent_cgv_at = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

    # Race-condition guard: in the 30 minutes between request and confirm,
    # someone else could have signed up with the same email through a
    # different channel. Re-check.
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        # If THIS user clicks their own link twice (idempotent confirm),
        # we already created the account on the first click — issue a fresh
        # token so they keep going. If a different account squatted the
        # email, we still log them in; the first-finger-on-the-link wins.
        logger.info("[signup-confirm] account already exists for %s — re-issuing token", email)
        access_token = create_access_token(
            data={"sub": str(existing.id), "email": existing.email}
        )
        return {"access_token": access_token, "token_type": "bearer"}

    # Materialise the user.
    new_user = User(
        email=email,
        name=name,
        hashed_password=hashed_password,
        is_active=True,
        subscription_tier=resolved_tier,
        consent_cgv_at=consent_cgv_at,
        consent_version=consent_version,
        consent_ip_hash=consent_ip_hash,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Best-effort Stripe customer (mirrors the legacy /register path).
    try:
        from app.services.stripe_service import (
            create_customer, is_configured, StripeNotConfiguredError,
        )
        if is_configured():
            create_customer(new_user, db)
    except StripeNotConfiguredError:
        pass
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Stripe customer creation failed for user %s: %s", new_user.id, exc
        )

    access_token = create_access_token(
        data={"sub": str(new_user.id), "email": new_user.email}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=Token)
@limiter.limit(RateLimits.AUTH_LOGIN)
async def login(request: Request, response: Response, user_credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return JWT access token.

    Args:
        user_credentials: User login credentials (email, password)
        db: Database session

    Returns:
        JWT access token

    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by email
    user = db.query(User).filter(User.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(user_credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Create access token
    # Convert user.id to string for JWT "sub" claim compatibility
    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserSchema)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user's profile.

    Args:
        current_user: Current authenticated user from JWT token

    Returns:
        Current user profile data
    """
    return current_user
