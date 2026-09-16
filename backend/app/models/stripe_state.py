"""
État Stripe persisté — BILL-04 (vague 1 / file B, audit Astra L683).

Jusqu'ici rien n'était persisté : chaque webhook lisait ``users.subscription_tier``
et l'écrasait. D'où les quatre défauts de BILL-04 :

- un événement ancien pouvait écraser un état plus récent (Stripe ne garantit
  pas l'ordre de livraison) ;
- un même événement rejoué rechargeait les crédits une seconde fois ;
- la suppression d'un ancien abonnement rétrogradait le compte alors qu'un
  autre était encore payé (chaque Checkout peut créer un abonnement de plus) ;
- ``past_due`` / ``unpaid`` gardaient le palier sans aucune échéance
  applicative, en pariant que Stripe finirait par envoyer ``deleted``.

Deux tables :

``stripe_events``
    Un événement Stripe reçu = une ligne, clé primaire l'identifiant Stripe.
    C'est la contrainte d'unicité qui rend le traitement idempotent : un
    doublon ne peut pas s'insérer, donc il ne peut pas recharger deux fois.
    Les événements non appliqués (price inconnu, client introuvable) restent
    en ``pending_reconciliation`` — la file de réconciliation demandée par
    l'audit — au lieu d'être acquittés en 200 et perdus.

``stripe_subscriptions``
    L'abonnement canonique et sa période. ``last_event_created`` porte
    l'horodatage Stripe du dernier événement appliqué à cette ligne : un
    événement plus ancien est refusé, ce qui règle le désordre. Le palier du
    compte est *dérivé* de l'ensemble de ces lignes, jamais écrit à l'aveugle
    par le dernier événement arrivé.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func

from app.database import Base


# --- statuts de traitement d'un événement ---------------------------------
EVENT_APPLIED = "applied"
EVENT_IGNORED = "ignored"                       # type non géré, sans effet
EVENT_PENDING_RECONCILIATION = "pending_reconciliation"

#: Statuts Stripe d'un abonnement qui donne droit au palier payant.
STATUTS_PAYANTS = ("active", "trialing")
#: Statuts d'impayé : le palier est conservé jusqu'à la fin de la grâce.
STATUTS_IMPAYES = ("past_due", "unpaid")
#: Statuts terminaux : plus aucun droit.
STATUTS_TERMINES = ("canceled", "incomplete_expired", "incomplete", "paused")


class StripeEvent(Base):
    """Un événement Stripe reçu. La clé primaire est l'identifiant Stripe :
    c'est elle qui interdit le double traitement."""

    __tablename__ = "stripe_events"

    event_id = Column(String(255), primary_key=True)
    event_type = Column(String(100), nullable=False)
    # `created` de l'événement Stripe (epoch) — sert à ordonner, pas l'heure
    # de réception : c'est l'ordre d'émission qui fait foi.
    event_created = Column(BigInteger, nullable=True)
    status = Column(String(32), nullable=False, default=EVENT_PENDING_RECONCILIATION)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    subscription_id = Column(String(255), nullable=True)
    note = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_stripe_events_status", "status"),
        Index("idx_stripe_events_user", "user_id"),
    )


class StripeSubscription(Base):
    """L'abonnement canonique : un par identifiant d'abonnement Stripe."""

    __tablename__ = "stripe_subscriptions"

    subscription_id = Column(String(255), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    customer_id = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False)
    price_id = Column(String(255), nullable=True)
    tier = Column(String(20), nullable=False)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, nullable=False, default=False,
                                  server_default="false")
    # Fin de la période de grâce sur impayé. Passée cette date, l'abonnement
    # ne donne plus droit au palier, sans attendre un `deleted` de Stripe.
    grace_until = Column(DateTime(timezone=True), nullable=True)
    # Horodatage Stripe du dernier événement APPLIQUÉ à cette ligne : un
    # événement plus ancien est refusé (désordre de livraison).
    last_event_created = Column(BigInteger, nullable=True)
    # Allocation initiale de crédits : posée une seule fois, à la première
    # activation. Empêche un second `subscription.created` de recharger.
    initial_credits_granted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False,
                        server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_stripe_subscriptions_user", "user_id"),
        Index("idx_stripe_subscriptions_customer", "customer_id"),
    )

    def donne_droit_au_palier(self, maintenant) -> bool:
        """L'abonnement ouvre-t-il le palier payant à cet instant ?

        Actif ou en essai : oui. Impayé : oui tant que la grâce court —
        c'est l'échéance applicative qui manquait. Terminé : non.
        """
        if self.status in STATUTS_PAYANTS:
            return True
        if self.status in STATUTS_IMPAYES:
            return self.grace_until is not None and maintenant < self.grace_until
        return False
