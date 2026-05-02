"""
Billing routes — Phase 3.

Existing (3.1, credits):
- GET  /api/billing/balance  : current credit picture for the authenticated user.
- GET  /api/billing/usage    : aggregated consumption (total + breakdown + timeline).

New (3.3, Stripe — 29 avril 2026):
- POST /api/billing/checkout : returns a hosted Stripe Checkout URL for upgrade.
- POST /api/billing/portal   : returns a hosted Customer Portal URL for self-service.
- POST /api/billing/cancel   : cancels the active subscription at period end.
- POST /api/billing/webhook  : Stripe webhook receiver (no auth, signature-verified).

The webhook is the only legitimate way to mutate user.subscription_tier for
paying tiers — Stripe is the source of truth for subscription state.
"""
import logging
import os

from fastapi import APIRouter, Depends, Query, Request, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.credit_service import CreditService
from app.utils.dependencies import get_current_user
from app.services import stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# ---------------------------------------------------------------------------
# Existing 3.1 endpoints — credits
# ---------------------------------------------------------------------------

@router.get("/balance")
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current credit balance for the authenticated user."""
    return CreditService(db).get_balance(current_user.id)


@router.get("/usage")
async def get_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated credit usage over the last ``days`` days."""
    return CreditService(db).get_usage(current_user.id, days=days)


# ---------------------------------------------------------------------------
# Stripe — Checkout / Portal / Cancel
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    tier: str  # "pro" or "team"
    # Optional overrides — frontend can set custom return paths
    success_url: str | None = None
    cancel_url:  str | None = None


def _default_success_url() -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "https://app.digital-humans.fr")
    return f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"


def _default_cancel_url() -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "https://app.digital-humans.fr")
    return f"{base}/billing/cancel"


def _default_portal_return_url() -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "https://app.digital-humans.fr")
    return f"{base}/account"


@router.post("/checkout")
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session and return the redirect URL.

    Frontend should redirect window.location to the returned ``url``.
    """
    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server",
        )
    try:
        result = stripe_service.create_checkout_session(
            user=current_user,
            tier=payload.tier,
            db=db,
            success_url=payload.success_url or _default_success_url(),
            cancel_url=payload.cancel_url or _default_cancel_url(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return result


@router.post("/portal")
async def create_portal(
    current_user: User = Depends(get_current_user),
):
    """Create a Customer Portal session and return its URL."""
    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server",
        )
    try:
        url = stripe_service.create_portal_session(
            user=current_user,
            return_url=_default_portal_return_url(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"url": url}


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
):
    """Cancel the active subscription at the end of the current period.

    The user keeps access until current_period_end. The webhook
    customer.subscription.deleted will downgrade them to free at that point.
    """
    if not stripe_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing is not configured on this server",
        )
    if not current_user.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription to cancel",
        )
    import stripe
    subs = stripe.Subscription.list(
        customer=current_user.stripe_customer_id, status="active", limit=1
    )
    if not subs.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found",
        )
    sub = stripe.Subscription.modify(
        subs.data[0].id, cancel_at_period_end=True
    )
    return {
        "subscription_id": sub.id,
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end,
    }


# ---------------------------------------------------------------------------
# Stripe — Webhook receiver
# ---------------------------------------------------------------------------

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive and dispatch Stripe webhook events.

    No auth — signature verification via STRIPE_WEBHOOK_SECRET is the
    sole gate. If the secret is not configured, returns 503.
    """
    if not stripe_service.STRIPE_WEBHOOK_SECRET:
        # Hard failure : we don't want unsigned events polluting our DB.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.verify_webhook(payload, signature)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        result = stripe_service.handle_webhook_event(event, db)
    except Exception:  # noqa: BLE001
        logger.exception("Webhook handler crashed for event %s", event.get("type"))
        # Return 500 so Stripe retries. If the bug is deterministic, you'll
        # see it surface in the Stripe dashboard event log.
        raise HTTPException(status_code=500, detail="Handler failed")

    logger.info("Webhook processed: %s", result)
    return {"received": True, **result}
