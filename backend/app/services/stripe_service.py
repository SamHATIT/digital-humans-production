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

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.stripe_state import (
    EVENT_APPLIED,
    EVENT_IGNORED,
    EVENT_PENDING_RECONCILIATION,
    STATUTS_IMPAYES,
    STATUTS_PAYANTS,
    StripeEvent,
    StripeSubscription,
)
from app.models.user import User
from app.services.llm_service import invalidate_tier_cache

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

# Ordre des paliers, du moins au plus élevé. Sert à dériver le palier du
# compte quand plusieurs abonnements coexistent (BILL-04) : on retient le plus
# élevé parmi ceux qui donnent droit, jamais « le dernier événement arrivé ».
ORDRE_PALIERS = ("free", "pro", "team", "enterprise")

# BILL-04 — impayé traité explicitement. Stripe relance selon sa configuration
# de recouvrement, que l'application ne peut pas vérifier : on ne parie donc
# plus sur un `customer.subscription.deleted` final. Un impayé ouvre une grâce
# DATÉE, au terme de laquelle l'accès se ferme de lui-même.
GRACE_IMPAYE_JOURS = int(os.environ.get("DH_STRIPE_GRACE_IMPAYE_JOURS", "5") or 5)


# --- DEC-2026-0809-10 : carte bancaire à l'inscription Free ----------------
# Décision de Sam non prise au 16/09 (attendue avant le 22/09). Les deux
# chemins existent et sont testés ; aucun n'est deviné. Le drapeau est la
# seule chose à basculer le jour de la décision.
_VALEURS_VRAIES = {"1", "true", "yes", "oui", "on"}


def _lire_drapeau_carte(valeur: Optional[str]) -> bool:
    """Vrai seulement pour une valeur explicitement vraie. Tout le reste —
    y compris une valeur inattendue — vaut faux : une valeur non reconnue ne
    tombe pas dans la branche permissive (règle 6)."""
    return (valeur or "").strip().lower() in _VALEURS_VRAIES


FREE_SIGNUP_REQUIRES_CARD = _lire_drapeau_carte(
    os.environ.get("DH_FREE_SIGNUP_REQUIRES_CARD")
)


def free_signup_requires_card() -> bool:
    """L'inscription Free exige-t-elle une carte bancaire ?

    Lu au moment de l'appel (et non figé à l'import) pour que le drapeau soit
    basculable sans redéploiement de l'image, et surchargeable dans les tests.
    """
    return FREE_SIGNUP_REQUIRES_CARD


def preparer_inscription_free(user: User, db: Session,
                              success_url: str = "", cancel_url: str = "") -> Dict[str, Any]:
    """Prépare l'inscription d'un compte Free, selon la décision DEC-2026-0809-10.

    - drapeau FAUX (comportement actuel) : on crée seulement le client Stripe,
      pour que la montée en gamme se fasse plus tard en un clic. Aucune carte
      n'est demandée, le compte est utilisable tout de suite.
    - drapeau VRAI : on crée en plus une session Checkout en mode ``setup``,
      qui recueille une carte sans la débiter. L'appelant redirige vers
      ``url`` ; le compte reste Free.

    Rend un dictionnaire portant toujours ``requires_card`` : l'appelant n'a
    pas à relire le drapeau lui-même.
    """
    _ensure_configured()
    customer_id = get_or_create_customer(user, db)
    if not free_signup_requires_card():
        return {"requires_card": False, "customer_id": customer_id, "url": None}

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="setup",
        success_url=success_url or _url_par_defaut("/account?carte=enregistree"),
        cancel_url=cancel_url or _url_par_defaut("/account?carte=annulee"),
        metadata={"user_id": str(user.id), "motif": "inscription_free"},
    )
    logger.info("Inscription Free avec carte : session setup %s pour l'utilisateur %s",
                session.id, user.id)
    return {"requires_card": True, "customer_id": customer_id,
            "session_id": session.id, "url": session.url}


def _url_par_defaut(chemin: str) -> str:
    base = os.environ.get("FRONTEND_BASE_URL", "https://app.digital-humans.fr")
    return f"{base}{chemin}"


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


def _en_dict(objet: Any) -> Dict[str, Any]:
    """Rend un dictionnaire simple à partir d'un objet du SDK Stripe.

    BILL-04 : avec ``stripe==15.1.0``, ``construct_event`` rend des objets qui
    ne sont plus des dictionnaires et n'ont plus de ``.get()`` — mesuré le
    16/09 : ``hasattr(obj, 'get')`` vaut False, et ``obj.get('customer')`` lève
    ``AttributeError``. Les quatre gestionnaires appelaient ``.get()`` : le
    webhook rendait 500 sur tout événement réel et Stripe rejouait sans fin.

    On normalise donc une fois, en entrée, au lieu de disséminer des
    ``getattr`` dans les gestionnaires.
    """
    if isinstance(objet, dict):
        return dict(objet)
    for methode in ("to_dict_recursive", "to_dict"):
        fonction = getattr(objet, methode, None)
        if callable(fonction):
            try:
                return dict(fonction())
            except Exception:  # noqa: BLE001 — on tente la suite
                pass
    try:
        return json.loads(str(objet))
    except Exception:  # noqa: BLE001
        return {}


def _horodatage(valeur: Optional[int]) -> Optional[datetime]:
    if not valeur:
        return None
    try:
        return datetime.fromtimestamp(int(valeur), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _rang_palier(tier: Optional[str]) -> int:
    try:
        return ORDRE_PALIERS.index((tier or "free").lower())
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Palier dérivé de l'état persisté (BILL-04)
# ---------------------------------------------------------------------------

def reconcilier_palier(user_id: int, db: Session,
                       maintenant: Optional[datetime] = None) -> str:
    """Recalcule ``users.subscription_tier`` À PARTIR des abonnements persistés.

    C'est le cœur du correctif BILL-04. Le palier n'est plus écrit par le
    dernier événement arrivé : il est DÉRIVÉ de l'ensemble des abonnements du
    compte. Trois conséquences :

    - supprimer un ancien abonnement ne rétrograde pas un compte qui en a un
      autre de payé (chaque Checkout peut créer un abonnement de plus) ;
    - un impayé conserve le palier tant que sa grâce court, et le perd ensuite
      sans qu'on ait besoin d'attendre un ``deleted`` de Stripe ;
    - un événement appliqué dans le désordre ne peut pas inverser l'état, car
      l'état vient des lignes, pas du message.

    Rend le palier retenu.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    abonnements = (
        db.query(StripeSubscription).filter(StripeSubscription.user_id == user_id).all()
    )
    palier = "free"
    for abonnement in abonnements:
        if abonnement.donne_droit_au_palier(maintenant):
            if _rang_palier(abonnement.tier) > _rang_palier(palier):
                palier = abonnement.tier

    user = db.get(User, user_id)
    if user is None:
        return palier
    # Un contrat Enterprise n'est pas géré par Stripe : on ne le rétrograde pas.
    if (user.subscription_tier or "").lower() == "enterprise":
        return "enterprise"
    if user.subscription_tier != palier:
        logger.info("Palier du compte %s : %s -> %s (dérivé de %d abonnement(s))",
                    user_id, user.subscription_tier, palier, len(abonnements))
        user.subscription_tier = palier
        db.add(user)
        db.commit()
        invalidate_tier_cache()
    return palier


def evenements_a_reconcilier(db: Session) -> List[StripeEvent]:
    """Les événements reçus mais non appliqués (price inconnu, client
    introuvable…). L'audit demandait de ne pas les acquitter en 200 puis les
    perdre : ils sont conservés avec leur charge, rejouables."""
    return (
        db.query(StripeEvent)
        .filter(StripeEvent.status == EVENT_PENDING_RECONCILIATION)
        .order_by(StripeEvent.received_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Webhook — point d'entrée
# ---------------------------------------------------------------------------

def handle_webhook_event(event: Any, db: Session) -> Dict[str, Any]:
    """Traite un événement Stripe vérifié, une seule fois.

    L'idempotence n'est pas un test applicatif mais la clé primaire de
    ``stripe_events`` : on insère l'identifiant de l'événement AVANT de le
    traiter ; si l'insertion échoue en doublon, c'est qu'il a déjà été traité,
    et on s'arrête là. Un rejeu ne peut donc pas recharger les crédits une
    seconde fois, quel que soit le délai entre les deux livraisons.
    """
    donnees = _en_dict(event)
    event_type = donnees.get("type") or ""
    event_id = donnees.get("id") or ""
    event_created = donnees.get("created")
    objet = _en_dict((donnees.get("data") or {}).get("object") or {})

    # 1. Verrou d'idempotence.
    ligne = StripeEvent(
        event_id=event_id,
        event_type=event_type,
        event_created=event_created,
        status=EVENT_PENDING_RECONCILIATION,
        subscription_id=objet.get("id") if event_type.startswith("customer.subscription")
        else objet.get("subscription"),
        payload=json.dumps(donnees, default=str)[:1_000_000],
    )
    db.add(ligne)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("Événement Stripe %s déjà traité, ignoré (doublon)", event_id)
        return {"handled": False, "type": event_type, "duplicate": True,
                "event_id": event_id, "reason": "événement déjà traité"}

    # 2. Traitement.
    try:
        resultat = _dispatcher(event_type, objet, event_created, db)
    except Exception:
        db.rollback()
        ligne = db.get(StripeEvent, event_id)
        if ligne is not None:
            ligne.status = EVENT_PENDING_RECONCILIATION
            ligne.note = "le gestionnaire a levé — à rejouer"
            db.commit()
        raise

    # 3. Journalisation du sort de l'événement.
    ligne = db.get(StripeEvent, event_id)
    if ligne is not None:
        if resultat.get("handled"):
            ligne.status = EVENT_APPLIED
        elif resultat.get("stale") or resultat.get("ignored"):
            ligne.status = EVENT_IGNORED
        else:
            ligne.status = EVENT_PENDING_RECONCILIATION
        ligne.user_id = resultat.get("user_id")
        ligne.note = resultat.get("reason")
        ligne.processed_at = datetime.now(timezone.utc)
        db.commit()

    resultat.setdefault("event_id", event_id)
    return resultat


def _dispatcher(event_type: str, objet: Dict[str, Any],
                event_created: Optional[int], db: Session) -> Dict[str, Any]:
    if event_type in ("customer.subscription.created",
                      "customer.subscription.updated",
                      "customer.subscription.deleted"):
        return _appliquer_abonnement(objet, db, event_type, event_created)

    if event_type == "invoice.payment_succeeded":
        return _handle_invoice_paid(objet, db)

    if event_type == "invoice.payment_failed":
        return _handle_invoice_failed(objet, db)

    logger.debug("Événement Stripe sans gestionnaire : %s", event_type)
    return {"handled": False, "ignored": True, "type": event_type,
            "reason": "type non géré"}


# ---------------------------------------------------------------------------
# Abonnements
# ---------------------------------------------------------------------------

def _appliquer_abonnement(sub: Dict[str, Any], db: Session, event_type: str,
                          event_created: Optional[int]) -> Dict[str, Any]:
    """Met à jour l'abonnement canonique, puis dérive le palier du compte."""
    subscription_id = sub.get("id")
    customer_id = sub.get("customer")
    statut = "canceled" if event_type.endswith(".deleted") else sub.get("status")

    items = (sub.get("items") or {}).get("data") or []
    price_id = None
    if items:
        price_id = (_en_dict(items[0]).get("price") or {}).get("id")

    existant = db.get(StripeSubscription, subscription_id) if subscription_id else None

    # Palier : le price sur l'événement, sinon celui déjà connu de la ligne.
    tier = PRICE_ID_TO_TIER.get(price_id) if price_id else None
    if tier is None and existant is not None:
        tier = existant.tier
    if tier is None:
        logger.warning("Abonnement %s : price_id %s inconnu — mis en réconciliation",
                       subscription_id, price_id)
        return {"handled": False, "type": event_type,
                "reason": f"price_id inconnu : {price_id}"}

    user = None
    if customer_id:
        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user is None and existant is not None:
        user = db.get(User, existant.user_id)
    if user is None:
        logger.warning("Aucun compte pour le client Stripe %s — mis en réconciliation",
                       customer_id)
        return {"handled": False, "type": event_type,
                "reason": f"client Stripe introuvable : {customer_id}"}

    # Désordre : un événement plus ancien que le dernier appliqué est refusé.
    if (existant is not None and existant.last_event_created is not None
            and event_created is not None
            and int(event_created) < int(existant.last_event_created)):
        logger.info("Événement %s (%s) plus ancien que l'état de l'abonnement %s : ignoré",
                    event_type, event_created, subscription_id)
        return {"handled": False, "stale": True, "type": event_type,
                "user_id": user.id, "reason": "événement antérieur à l'état courant"}

    maintenant = datetime.now(timezone.utc)
    if existant is None:
        existant = StripeSubscription(
            subscription_id=subscription_id,
            user_id=user.id,
            customer_id=customer_id,
            status=statut or "incomplete",
            price_id=price_id,
            tier=tier,
        )
        db.add(existant)
    else:
        existant.user_id = user.id
        existant.customer_id = customer_id or existant.customer_id
        existant.status = statut or existant.status
        existant.price_id = price_id or existant.price_id
        existant.tier = tier

    existant.current_period_end = _horodatage(sub.get("current_period_end"))
    existant.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    existant.last_event_created = event_created

    # Impayé : grâce datée, ouverte une seule fois (une relance ne la prolonge pas).
    if existant.status in STATUTS_IMPAYES:
        if existant.grace_until is None:
            existant.grace_until = maintenant + timedelta(days=GRACE_IMPAYE_JOURS)
    else:
        existant.grace_until = None

    db.commit()

    # Le palier est dérivé AVANT de provisionner : `reset_monthly` lit le
    # palier du compte pour connaître l'allocation. Dans l'autre ordre, le
    # compte était encore Free au moment de la recharge et recevait 0 crédit —
    # exactement le symptôme que BILL-03/04 décrit (« le nouveau Pro peut
    # rester sans crédits »).
    palier = reconcilier_palier(user.id, db, maintenant)

    # Allocation initiale : provisionnée UNE fois, à la première activation.
    credits_provisionnes = False
    if (existant.status in STATUTS_PAYANTS
            and existant.initial_credits_granted_at is None):
        existant.initial_credits_granted_at = maintenant
        db.commit()
        credits_provisionnes = _provisionner_allocation_initiale(user, tier, db)
    logger.info("Abonnement %s : statut=%s palier=%s (compte %s -> %s)",
                subscription_id, existant.status, tier, user.id, palier)
    return {
        "handled": True, "type": event_type, "user_id": user.id,
        "subscription_id": subscription_id, "new_tier": palier,
        "stripe_status": existant.status,
        "grace_until": existant.grace_until.isoformat() if existant.grace_until else None,
        "initial_credits_granted": credits_provisionnes,
    }


def _provisionner_allocation_initiale(user: User, tier: str, db: Session) -> bool:
    """Pose l'allocation du palier sur le solde du compte.

    BILL-03/04 : un Free qui a consulté son solde a déjà une ligne à zéro.
    `subscription.created` changeait son palier sans recharger cette ligne, et
    l'événement du premier paiement était ignoré « parce que la recharge est
    déjà faite » — le nouveau Pro pouvait rester sans crédits. Le garde-fou
    contre le double provisionnement est `initial_credits_granted_at`, posé par
    l'appelant AVANT cet appel.
    """
    from app.services.credit_service import CreditError, CreditService

    try:
        solde = CreditService(db).reset_monthly(user.id)
        logger.info("Allocation initiale posée pour le compte %s (palier %s) : %s crédits",
                    user.id, tier, solde.included_credits)
        return True
    except CreditError as exc:
        logger.error("Allocation initiale impossible pour le compte %s : %s", user.id, exc)
        return False


def _handle_invoice_paid(invoice: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Recharge mensuelle sur renouvellement.

    La déduplication ne se joue plus ici : elle est portée par la clé primaire
    de ``stripe_events``, donc un rejeu de la même facture n'atteint jamais ce
    code. Restent les motifs de facturation : seuls ceux qui correspondent
    vraiment à un renouvellement rechargent. Le commentaire d'origine disait
    « seulement subscription_cycle » mais le code acceptait tout sauf
    ``subscription_create`` — une facture d'ajustement rechargeait le quota.
    """
    from app.services.credit_service import CreditError, CreditService

    customer_id = invoice.get("customer")
    billing_reason = invoice.get("billing_reason")
    invoice_id = invoice.get("id")
    subscription = invoice.get("subscription")

    if not subscription:
        return {"handled": False, "ignored": True,
                "type": "invoice.payment_succeeded",
                "reason": "facture hors abonnement",
                "billing_reason": billing_reason}

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return {"handled": False, "type": "invoice.payment_succeeded",
                "reason": f"client Stripe introuvable : {customer_id}"}

    if billing_reason == "subscription_create":
        # L'allocation initiale est posée par l'événement d'abonnement, une
        # seule fois. On ne recharge pas ici, mais on le dit explicitement au
        # lieu de laisser croire que l'événement a été appliqué.
        return {"handled": True, "type": "invoice.payment_succeeded",
                "user_id": user.id, "billing_reason": billing_reason,
                "reason": "premier paiement : allocation posée par subscription.created",
                "credits_refilled": None}

    if billing_reason != "subscription_cycle":
        return {"handled": False, "ignored": True,
                "type": "invoice.payment_succeeded", "user_id": user.id,
                "billing_reason": billing_reason,
                "reason": f"motif de facturation sans recharge : {billing_reason}"}

    try:
        solde = CreditService(db).reset_monthly(user.id)
    except CreditError as exc:
        logger.error("Recharge de renouvellement impossible (compte %s) : %s", user.id, exc)
        return {"handled": False, "type": "invoice.payment_succeeded",
                "user_id": user.id, "reason": f"recharge impossible : {exc}"}

    logger.info("Crédits rechargés au renouvellement (compte %s, facture %s) : %s",
                user.id, invoice_id, solde.included_credits)
    return {"handled": True, "type": "invoice.payment_succeeded",
            "user_id": user.id, "invoice_id": invoice_id,
            "billing_reason": billing_reason,
            "credits_refilled": solde.included_credits}


def _handle_invoice_failed(invoice: Dict[str, Any], db: Session) -> Dict[str, Any]:
    """Paiement échoué : on ouvre la grâce datée sur l'abonnement concerné.

    L'ancien gestionnaire se contentait de journaliser, en pariant sur un
    ``customer.subscription.deleted`` final dont la venue dépend de la
    configuration de recouvrement Stripe — non vérifiable côté application.
    L'échéance est désormais portée par la base.
    """
    customer_id = invoice.get("customer")
    invoice_id = invoice.get("id")
    subscription_id = invoice.get("subscription")

    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return {"handled": False, "type": "invoice.payment_failed",
                "reason": f"client Stripe introuvable : {customer_id}"}

    maintenant = datetime.now(timezone.utc)
    abonnement = db.get(StripeSubscription, subscription_id) if subscription_id else None
    grace = None
    if abonnement is not None:
        if abonnement.grace_until is None:
            abonnement.grace_until = maintenant + timedelta(days=GRACE_IMPAYE_JOURS)
        if abonnement.status in STATUTS_PAYANTS:
            abonnement.status = "past_due"
        db.commit()
        grace = abonnement.grace_until
        reconcilier_palier(user.id, db, maintenant)

    logger.warning(
        "Paiement echoue (compte %s, facture %s, abonnement %s) : tentative %s, "
        "prochaine relance %s, grace jusqu'au %s",
        user.id, invoice_id, subscription_id, invoice.get("attempt_count"),
        invoice.get("next_payment_attempt"), grace,
    )
    return {
        "handled": True, "type": "invoice.payment_failed",
        "user_id": user.id, "invoice_id": invoice_id,
        "attempt_count": invoice.get("attempt_count"),
        "next_payment_attempt": invoice.get("next_payment_attempt"),
        "grace_until": grace.isoformat() if grace else None,
        "reason": "impaye : grace ouverte",
    }
