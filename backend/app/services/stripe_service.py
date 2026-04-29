"""
Stripe Service — Phase 3 S3.3 (29 avril 2026).

Wraps the Stripe Python SDK to handle the customer / subscription lifecycle
for the 4-tier freemium model (free / pro / team / enterprise).

Flows
-----
1. Signup hook   : create_customer(user) — called once when a User registers.
2. Upgrade flow  : create_checkout_session(user, tier) — returns a hosted
   Stripe Checkout URL for the user to enter card details.
3. Self-service  : create_portal_session(user) — returns a hosted Customer
   Portal URL where the user can change plan, update card, cancel.
4. Webhook       : handle_webhook(payload, signature) — verifies the
   Stripe-Signature header and dispatches subscription events to keep
   user.subscription_tier in sync with Stripe's source of truth.

Mapping Price ID → tier is loaded from env at module load (STRIPE_PRICE_ID_PRO
and STRIPE_PRICE_ID_TEAM). Enterprise is on-premise and bypasses Stripe.

Source of truth : Stripe owns the subscription state (active, past_due,
canceled, etc.). Our DB mirrors `subscription_tier` for fast reads in the
LLM router and credit service. The webhook is the only legit way to
mutate `users.subscription_tier` for paying tiers.
"""
from __future__ import annotations

import logging
import os
from typing import Optional, Dict, Any

import stripe
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration — loaded once at module import
# ---------------------------------------------------------------------------

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

# Price ID → tier name mapping. Enterprise is not listed (on-premise, no
# Stripe billing). Add to this dict if you ever ship a yearly variant.
PRICE_ID_TO_TIER: Dict[str, str] = {
    os.environ.get("STRIPE_PRICE_ID_PRO",  ""): "pro",
    os.environ.get("STRIPE_PRICE_ID_TEAM", ""): "team",
}
PRICE_ID_TO_TIER = {pid: tier for pid, tier in PRICE_ID_TO_TIER.items() if pid}

TIER_TO_PRICE_ID = {tier: pid for pid, tier in PRICE_ID_TO_TIER.items()}


def is_configured() -> bool:
    """Return True if the secret key is present (sandbox or live)."""
    return bool(stripe.api_key)


class StripeNotConfiguredError(RuntimeError):
    """Raised when a Stripe call is attempted but STRIPE_SECRET_KEY is missing."""


def _ensure_configured():
    if not is_configured():
        raise StripeNotConfiguredError(
            "Stripe is not configured: set STRIPE_SECRET_KEY in the environment."
        )


# ---------------------------------------------------------------------------
# Customer lifecycle
# ---------------------------------------------------------------------------

def create_customer(user: User, db: Session) -> str:
    """Create a Stripe Customer for a user and persist the ID.

    Idempotent : if user.stripe_customer_id is already set, return it.
    """
    _ensure_configured()

    if user.stripe_customer_id:
        logger.info("Stripe customer already exists for user %s: %s",
                    user.id, user.stripe_customer_id)
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        name=user.name,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.add(user)
    db.commit()
    logger.info("Created Stripe customer %s for user %s (%s)",
                customer.id, user.id, user.email)
    return customer.id


def get_or_create_customer(user: User, db: Session) -> str:
    """Convenience wrapper, alias for create_customer (which is idempotent)."""
    return create_customer(user, db)


# ---------------------------------------------------------------------------
# Checkout — upgrade flow
# ---------------------------------------------------------------------------

def create_checkout_session(
    user: User,
    tier: str,
    db: Session,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a Stripe Checkout Session for upgrading a user to ``tier``.

    Returns a dict {id, url} — the frontend redirects the browser to ``url``.

    Raises ValueError if the tier is unknown or not subscribable via Stripe
    (free, enterprise).
    """
    _ensure_configured()

    if tier not in TIER_TO_PRICE_ID:
        raise ValueError(
            f"Tier '{tier}' is not subscribable via Stripe. "
            f"Available tiers: {list(TIER_TO_PRICE_ID.keys())}"
        )

    customer_id = get_or_create_customer(user, db)
    price_id = TIER_TO_PRICE_ID[tier]

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        # Stripe will add ?session_id={CHECKOUT_SESSION_ID} to success_url
        # if it contains the literal {CHECKOUT_SESSION_ID}.
        allow_promotion_codes=True,
        # Pass user_id and target_tier in metadata so the webhook can
        # correlate the subscription to our user even if the Customer's
        # email changes later.
        subscription_data={
            "metadata": {
                "user_id": str(user.id),
                "target_tier": tier,
            },
        },
        # Also tag the session itself for debugging.
        metadata={
            "user_id": str(user.id),
            "target_tier": tier,
        },
    )
    logger.info("Created Checkout Session %s for user %s → tier %s",
                session.id, user.id, tier)
    return {"id": session.id, "url": session.url}


# ---------------------------------------------------------------------------
# Customer Portal — self-service
# ---------------------------------------------------------------------------

def create_portal_session(user: User, return_url: str) -> str:
    """Create a Stripe Customer Portal session and return its URL.

    The portal lets the user change plan, update card, view invoices, cancel.
    Requires a configured Customer Portal in the Stripe dashboard
    (Settings → Billing → Customer Portal).
    """
    _ensure_configured()
    if not user.stripe_customer_id:
        raise ValueError(
            f"User {user.id} has no Stripe customer — they must complete "
            "a Checkout flow first."
        )
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=return_url,
    )
    logger.info("Created Portal session for user %s", user.id)
    return session.url


# ---------------------------------------------------------------------------
# Webhook — Stripe events → DB sync
# ---------------------------------------------------------------------------

def verify_webhook(payload: bytes, signature: str) -> stripe.Event:
    """Verify a webhook signature and return the parsed Event.

    Raises stripe.error.SignatureVerificationError if invalid.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise StripeNotConfiguredError("STRIPE_WEBHOOK_SECRET not set in env")
    return stripe.Webhook.construct_event(
        payload=payload,
        sig_header=signature,
        secret=STRIPE_WEBHOOK_SECRET,
    )


def handle_webhook_event(event: stripe.Event, db: Session) -> Dict[str, Any]:
    """Dispatch a verified Stripe Event to the right handler.

    Returns a dict with at least {"handled": bool, "type": str, "user_id": ...}
    for logging / debugging.
    """
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type in ("customer.subscription.created",
                      "customer.subscription.updated"):
        return _handle_subscription_change(obj, db, event_type)

    if event_type == "customer.subscription.deleted":
        return _handle_subscription_deleted(obj, db)

    if event_type == "invoice.payment_succeeded":
        # TODO Phase 3.4 : reset monthly credits via CreditService
        return {"handled": False, "type": event_type, "note": "TODO credit reset"}

    if event_type == "invoice.payment_failed":
        # TODO Phase 3.4 : start grace period, notify user
        return {"handled": False, "type": event_type, "note": "TODO grace period"}

    logger.debug("Stripe event ignored: %s", event_type)
    return {"handled": False, "type": event_type, "note": "ignored"}


def _handle_subscription_change(sub: Dict[str, Any], db: Session,
                                event_type: str) -> Dict[str, Any]:
    """Update user.subscription_tier when a subscription is created or updated."""
    customer_id = sub.get("customer")
    status_str  = sub.get("status")  # active, past_due, canceled, ...
    items = (sub.get("items") or {}).get("data") or []
    if not items:
        logger.warning("Subscription %s has no items", sub.get("id"))
        return {"handled": False, "type": event_type, "reason": "no items"}
    price_id = items[0].get("price", {}).get("id")
    new_tier = PRICE_ID_TO_TIER.get(price_id)
    if not new_tier:
        logger.warning("Subscription %s has unknown price_id %s",
                       sub.get("id"), price_id)
        return {"handled": False, "type": event_type, "reason": "unknown price_id"}

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning("No user found for Stripe customer %s", customer_id)
        return {"handled": False, "type": event_type, "reason": "user not found"}

    # Active states keep the paying tier. Inactive states drop to free.
    if status_str in ("active", "trialing"):
        user.subscription_tier = new_tier
    elif status_str in ("past_due", "unpaid"):
        # Keep tier for now — grace period handled via invoice.payment_failed
        user.subscription_tier = new_tier
    else:
        # incomplete, incomplete_expired, canceled → downgrade to free
        user.subscription_tier = "free"

    db.add(user)
    db.commit()
    logger.info("Updated user %s tier → %s (Stripe sub %s status=%s)",
                user.id, user.subscription_tier, sub.get("id"), status_str)
    return {
        "handled": True, "type": event_type,
        "user_id": user.id, "new_tier": user.subscription_tier,
        "stripe_status": status_str,
    }


def _handle_subscription_deleted(sub: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """User downgrades to free when their subscription is canceled (period end)."""
    customer_id = sub.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        logger.warning("No user found for canceled sub, customer %s", customer_id)
        return {"handled": False, "type": "customer.subscription.deleted",
                "reason": "user not found"}
    user.subscription_tier = "free"
    db.add(user)
    db.commit()
    logger.info("User %s downgraded to free (sub %s deleted)",
                user.id, sub.get("id"))
    return {"handled": True, "type": "customer.subscription.deleted",
            "user_id": user.id, "new_tier": "free"}
