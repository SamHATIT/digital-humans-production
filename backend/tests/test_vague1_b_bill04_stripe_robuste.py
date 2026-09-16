"""
Vague 1 / file B — BILL-04 (audit Astra du 06/09/2026, L683).

« L'état Stripe n'est pas robuste aux événements désordonnés, impayés et
abonnements multiples. »

La sandbox Stripe N'EST PAS jointe : le bac à sable et le bootstrap hermétique
refusent tout appel sortant. Les événements sont donc des charges JSON
conformes au format Stripe, signées avec un secret factice et POSTées sur la
vraie route webhook — c'est le code de production qui vérifie la signature
(``stripe.Webhook.construct_event``) et dispatche. Ce qui reste à jouer sur la
sandbox du VPS est listé dans docs/missions/RAPPORT_VAGUE1_B.md.

Critère de sortie (mission) : « le paiement initial crédite ; doublon/désordre
ne recharge pas deux fois ; impayé traité explicitement ».
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.credit import (
    TRANSACTION_TYPE_RESET,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.stripe_state import (
    EVENT_APPLIED,
    EVENT_PENDING_RECONCILIATION,
    StripeEvent,
    StripeSubscription,
)
from app.models.user import User

SECRET_FACTICE = "whsec_secret-factice-des-tests-bill04"
PRIX_PRO = "price_factice_pro_bill04"
PRIX_TEAM = "price_factice_team_bill04"
CLIENT = "cus_factice_bill04"


# ─────────────────────────────────────────────────────────────────────
# Socle
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def socle(db_session, monkeypatch):
    """Paliers, tarifs, et un service Stripe configuré sur des valeurs
    factices — aucune clé réelle, aucun appel sortant."""
    db_session.add_all([
        TierConfig(tier_name="free", monthly_credits=0, daily_credits_cap=50,
                   price_eur_monthly=0, description="free"),
        TierConfig(tier_name="pro", monthly_credits=15000, daily_credits_cap=None,
                   price_eur_monthly=79, description="pro"),
        TierConfig(tier_name="team", monthly_credits=100000, daily_credits_cap=None,
                   price_eur_monthly=1490, description="team"),
        ModelPricing(model_name="modele-fictif-bill04", credits_per_1k_input=1.0,
                     credits_per_1k_output=2.0, allowed_tiers="free,pro,team",
                     requires_opt_in=False, is_active=True),
    ])
    db_session.commit()

    from app.services import stripe_service
    monkeypatch.setattr(stripe_service, "STRIPE_WEBHOOK_SECRET", SECRET_FACTICE)
    monkeypatch.setattr(stripe_service, "PRICE_ID_TO_TIER",
                        {PRIX_PRO: "pro", PRIX_TEAM: "team"})
    monkeypatch.setattr(stripe_service, "TIER_TO_PRICE_ID",
                        {"pro": PRIX_PRO, "team": PRIX_TEAM})
    return stripe_service


@pytest.fixture
def utilisateur(db_session):
    suffixe = uuid.uuid4().hex[:8]
    u = User(email=f"bill04-{suffixe}@exemple.test", hashed_password="x",
             name=f"Compte BILL-04 {suffixe}", subscription_tier="free",
             stripe_customer_id=CLIENT)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


# ─────────────────────────────────────────────────────────────────────
# Fabrication d'événements signés
# ─────────────────────────────────────────────────────────────────────


def _evenement(type_evenement: str, objet: dict, *, event_id: str | None = None,
               created: int | None = None) -> dict:
    return {
        "id": event_id or f"evt_{uuid.uuid4().hex[:16]}",
        "object": "event",
        "type": type_evenement,
        "created": created if created is not None else int(time.time()),
        "data": {"object": objet},
    }


def _abonnement(statut: str = "active", *, price_id: str = PRIX_PRO,
                sub_id: str = "sub_factice_bill04",
                period_end: int | None = None) -> dict:
    return {
        "id": sub_id,
        "object": "subscription",
        "customer": CLIENT,
        "status": statut,
        "cancel_at_period_end": False,
        "current_period_end": period_end or int(time.time()) + 30 * 86400,
        "items": {"data": [{"price": {"id": price_id}}]},
    }


def _facture(billing_reason: str = "subscription_cycle", *,
             sub_id: str = "sub_factice_bill04",
             invoice_id: str | None = None) -> dict:
    return {
        "id": invoice_id or f"in_{uuid.uuid4().hex[:16]}",
        "object": "invoice",
        "customer": CLIENT,
        "subscription": sub_id,
        "billing_reason": billing_reason,
        "amount_due": 7900,
        "attempt_count": 1,
        "next_payment_attempt": int(time.time()) + 3 * 86400,
    }


def _signer(charge: bytes, secret: str = SECRET_FACTICE) -> str:
    """En-tête `Stripe-Signature` au format v1, comme Stripe l'émet."""
    horodatage = int(time.time())
    signature = hmac.new(
        secret.encode(), f"{horodatage}.".encode() + charge, hashlib.sha256
    ).hexdigest()
    return f"t={horodatage},v1={signature}"


def _poster(client, evenement: dict, *, secret: str = SECRET_FACTICE):
    charge = json.dumps(evenement).encode()
    return client.post("/api/billing/webhook", content=charge,
                       headers={"stripe-signature": _signer(charge, secret)})


def _solde(db_session, user_id: int):
    db_session.expire_all()
    return db_session.query(CreditBalance).filter_by(user_id=user_id).first()


def _resets(db_session, user_id: int):
    db_session.expire_all()
    return (db_session.query(CreditTransaction)
            .filter_by(user_id=user_id, transaction_type=TRANSACTION_TYPE_RESET)
            .all())


def _abonnement_persiste(db_session, sub_id: str = "sub_factice_bill04"):
    db_session.expire_all()
    return db_session.query(StripeSubscription).filter_by(subscription_id=sub_id).first()


def _palier(db_session, utilisateur):
    db_session.expire_all()
    return db_session.query(User).get(utilisateur.id).subscription_tier


# ─────────────────────────────────────────────────────────────────────
# 1. Signature — contrôle positif et négatif
# ─────────────────────────────────────────────────────────────────────


def test_une_signature_invalide_est_refusee(client, socle, utilisateur):
    reponse = _poster(client, _evenement("customer.subscription.created", _abonnement()),
                      secret="whsec_mauvais-secret")
    assert reponse.status_code == 400


def test_une_signature_valide_est_acceptee(client, socle, utilisateur, db_session):
    """Contrôle positif : sans lui, un refus systématique passerait le test
    précédent."""
    reponse = _poster(client, _evenement("customer.subscription.created", _abonnement()))
    assert reponse.status_code == 200, reponse.text
    assert _palier(db_session, utilisateur) == "pro"


# ─────────────────────────────────────────────────────────────────────
# 2. Le paiement initial crédite — une fois
# ─────────────────────────────────────────────────────────────────────


def test_le_paiement_initial_provisionne_les_credits(client, socle, utilisateur, db_session):
    """BILL-03/04 : un Free qui a consulté son solde a déjà une ligne à 0.
    `subscription.created` doit la recharger à l'allocation du palier — sinon
    le nouveau Pro reste sans crédits."""
    db_session.add(CreditBalance(user_id=utilisateur.id, included_credits=0,
                                 used_credits=0, overage_credits=0))
    db_session.commit()

    reponse = _poster(client, _evenement("customer.subscription.created", _abonnement()))
    assert reponse.status_code == 200, reponse.text

    solde = _solde(db_session, utilisateur.id)
    assert solde.included_credits == 15000, "le paiement initial n'a pas crédité"
    assert solde.used_credits == 0


def test_un_second_subscription_created_ne_recharge_pas(client, socle, utilisateur, db_session):
    """L'allocation initiale est provisionnée UNE seule fois."""
    _poster(client, _evenement("customer.subscription.created", _abonnement()))
    solde = _solde(db_session, utilisateur.id)
    solde.used_credits = 4000
    db_session.commit()

    # Un second événement `created` pour le MÊME abonnement (identifiant
    # d'événement différent : ce n'est pas un doublon, c'est un rejeu Stripe).
    _poster(client, _evenement("customer.subscription.created", _abonnement()))

    assert _solde(db_session, utilisateur.id).used_credits == 4000, (
        "la consommation a été effacée par une seconde allocation initiale"
    )


# ─────────────────────────────────────────────────────────────────────
# 3. Doublon : un seul crédit
# ─────────────────────────────────────────────────────────────────────


def test_un_evenement_rejoue_deux_fois_ne_recharge_qu_une_fois(
    client, socle, utilisateur, db_session
):
    """Critère de sortie : « webhook rejoué deux fois → un seul crédit »."""
    _poster(client, _evenement("customer.subscription.created", _abonnement()))
    solde = _solde(db_session, utilisateur.id)
    solde.used_credits = 3000
    db_session.commit()

    renouvellement = _evenement("invoice.payment_succeeded",
                                _facture("subscription_cycle"))
    premiere = _poster(client, renouvellement)
    assert premiere.status_code == 200, premiere.text
    assert _solde(db_session, utilisateur.id).used_credits == 0

    # On consomme de nouveau, puis on rejoue LE MÊME événement.
    solde = _solde(db_session, utilisateur.id)
    solde.used_credits = 2500
    db_session.commit()

    seconde = _poster(client, renouvellement)
    assert seconde.status_code == 200, seconde.text
    assert seconde.json().get("duplicate") is True, seconde.json()
    assert _solde(db_session, utilisateur.id).used_credits == 2500, (
        "l'événement rejoué a rechargé les crédits une seconde fois"
    )
    assert len(_resets(db_session, utilisateur.id)) == 1


def test_l_evenement_est_journalise_une_seule_fois(client, socle, utilisateur, db_session):
    evenement = _evenement("customer.subscription.created", _abonnement())
    _poster(client, evenement)
    _poster(client, evenement)
    db_session.expire_all()
    lignes = db_session.query(StripeEvent).filter_by(event_id=evenement["id"]).all()
    assert len(lignes) == 1
    assert lignes[0].status == EVENT_APPLIED


# ─────────────────────────────────────────────────────────────────────
# 4. Désordre : un événement ancien n'écrase pas un état plus récent
# ─────────────────────────────────────────────────────────────────────


def test_un_evenement_ancien_n_ecrase_pas_un_etat_plus_recent(
    client, socle, utilisateur, db_session
):
    """Stripe ne garantit pas l'ordre de livraison. L'annulation (ancienne)
    arrive APRÈS la réactivation (récente) : l'état final doit être le plus
    récent, donc actif."""
    maintenant = int(time.time())

    ancien = _evenement("customer.subscription.updated",
                        _abonnement("canceled"), created=maintenant - 3600)
    recent = _evenement("customer.subscription.updated",
                        _abonnement("active"), created=maintenant)

    assert _poster(client, recent).status_code == 200
    assert _palier(db_session, utilisateur) == "pro"

    reponse = _poster(client, ancien)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json().get("stale") is True, reponse.json()
    assert _palier(db_session, utilisateur) == "pro", (
        "un événement plus ancien a écrasé un état plus récent"
    )
    assert _abonnement_persiste(db_session).status == "active"


def test_controle_positif_un_evenement_plus_recent_est_bien_applique(
    client, socle, utilisateur, db_session
):
    """Sans ce contrôle, un code qui refuserait TOUS les updates passerait le
    test précédent."""
    maintenant = int(time.time())
    _poster(client, _evenement("customer.subscription.updated",
                               _abonnement("active"), created=maintenant - 3600))
    assert _palier(db_session, utilisateur) == "pro"

    _poster(client, _evenement("customer.subscription.updated",
                               _abonnement("canceled"), created=maintenant))
    assert _palier(db_session, utilisateur) == "free"


# ─────────────────────────────────────────────────────────────────────
# 5. Abonnements multiples
# ─────────────────────────────────────────────────────────────────────


def test_la_suppression_d_un_ancien_abonnement_ne_retrograde_pas_un_compte_encore_paye(
    client, socle, utilisateur, db_session
):
    """Chaque Checkout peut créer un abonnement de plus. Supprimer le premier
    ne doit pas fermer l'accès tant qu'un autre est actif."""
    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", sub_id="sub_ancien_bill04")))
    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", price_id=PRIX_TEAM,
                                           sub_id="sub_recent_bill04")))
    assert _palier(db_session, utilisateur) == "team"

    reponse = _poster(client, _evenement("customer.subscription.deleted",
                                         _abonnement("canceled", sub_id="sub_ancien_bill04")))
    assert reponse.status_code == 200, reponse.text
    assert _palier(db_session, utilisateur) == "team", (
        "la suppression d'un ancien abonnement a rétrogradé un compte encore payé"
    )


def test_la_suppression_du_dernier_abonnement_retrograde_bien(
    client, socle, utilisateur, db_session
):
    """Contrôle négatif du précédent : quand il ne reste rien de payé, le
    compte retombe en free."""
    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", sub_id="sub_unique_bill04")))
    assert _palier(db_session, utilisateur) == "pro"
    _poster(client, _evenement("customer.subscription.deleted",
                               _abonnement("canceled", sub_id="sub_unique_bill04")))
    assert _palier(db_session, utilisateur) == "free"


def test_le_palier_retenu_est_le_plus_eleve_des_abonnements_actifs(
    client, socle, utilisateur, db_session
):
    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", price_id=PRIX_PRO,
                                           sub_id="sub_a_bill04")))
    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", price_id=PRIX_TEAM,
                                           sub_id="sub_b_bill04")))
    assert _palier(db_session, utilisateur) == "team"


# ─────────────────────────────────────────────────────────────────────
# 6. Impayé : traité explicitement, avec une échéance applicative
# ─────────────────────────────────────────────────────────────────────


def test_un_impaye_ouvre_une_grace_datee_et_garde_l_acces(
    client, socle, utilisateur, db_session
):
    """`past_due` conservait le palier SANS échéance applicative, en pariant
    que Stripe enverrait `deleted`. Il doit désormais porter une date de fin
    de grâce."""
    _poster(client, _evenement("customer.subscription.created", _abonnement("active")))
    reponse = _poster(client, _evenement("customer.subscription.updated",
                                         _abonnement("past_due")))
    assert reponse.status_code == 200, reponse.text

    abonnement = _abonnement_persiste(db_session)
    assert abonnement.status == "past_due"
    assert abonnement.grace_until is not None, "impayé sans échéance applicative"
    assert _palier(db_session, utilisateur) == "pro", "l'accès est fermé trop tôt"
    assert reponse.json().get("grace_until") is not None


def test_une_grace_expiree_ferme_l_acces_sans_attendre_stripe(
    client, socle, utilisateur, db_session
):
    """Contrôle négatif : la grâce n'est pas un blanc-seing. Une fois la date
    passée, le palier tombe — sans dépendre d'un `deleted` de Stripe, dont la
    configuration de recouvrement n'est pas vérifiable côté application."""
    from app.services import stripe_service

    _poster(client, _evenement("customer.subscription.created", _abonnement("active")))
    _poster(client, _evenement("customer.subscription.updated", _abonnement("past_due")))

    abonnement = _abonnement_persiste(db_session)
    abonnement.grace_until = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    palier = stripe_service.reconcilier_palier(utilisateur.id, db_session)
    assert palier == "free"
    assert _palier(db_session, utilisateur) == "free"


def test_un_impaye_est_journalise_avec_son_motif(client, socle, utilisateur, db_session):
    _poster(client, _evenement("customer.subscription.created", _abonnement("active")))
    evenement = _evenement("invoice.payment_failed", _facture("subscription_cycle"))
    reponse = _poster(client, evenement)
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps.get("handled") is True
    assert corps.get("attempt_count") == 1

    db_session.expire_all()
    ligne = db_session.query(StripeEvent).filter_by(event_id=evenement["id"]).one()
    assert ligne.status == EVENT_APPLIED


def test_un_impaye_ne_recharge_jamais_les_credits(client, socle, utilisateur, db_session):
    """Contrôle : seul un paiement réussi recharge."""
    _poster(client, _evenement("customer.subscription.created", _abonnement("active")))
    solde = _solde(db_session, utilisateur.id)
    solde.used_credits = 7000
    db_session.commit()
    _poster(client, _evenement("invoice.payment_failed", _facture("subscription_cycle")))
    assert _solde(db_session, utilisateur.id).used_credits == 7000


# ─────────────────────────────────────────────────────────────────────
# 7. File de réconciliation : rien n'est acquitté puis perdu
# ─────────────────────────────────────────────────────────────────────


def test_un_price_inconnu_part_en_reconciliation(client, socle, utilisateur, db_session):
    evenement = _evenement("customer.subscription.created",
                           _abonnement("active", price_id="price_jamais_vu"))
    reponse = _poster(client, evenement)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json().get("handled") is False

    db_session.expire_all()
    ligne = db_session.query(StripeEvent).filter_by(event_id=evenement["id"]).one()
    assert ligne.status == EVENT_PENDING_RECONCILIATION
    assert "price" in (ligne.note or "").lower()
    assert ligne.payload, "la charge doit être conservée pour pouvoir rejouer"


def test_un_client_introuvable_part_en_reconciliation(client, socle, db_session):
    """Aucun utilisateur ne porte ce client Stripe."""
    objet = _abonnement("active")
    objet["customer"] = "cus_inconnu_bill04"
    evenement = _evenement("customer.subscription.created", objet)
    reponse = _poster(client, evenement)
    assert reponse.status_code == 200, reponse.text

    db_session.expire_all()
    ligne = db_session.query(StripeEvent).filter_by(event_id=evenement["id"]).one()
    assert ligne.status == EVENT_PENDING_RECONCILIATION


def test_la_file_de_reconciliation_est_lisible(client, socle, utilisateur, db_session):
    from app.services import stripe_service

    _poster(client, _evenement("customer.subscription.created",
                               _abonnement("active", price_id="price_jamais_vu")))
    en_attente = stripe_service.evenements_a_reconcilier(db_session)
    assert len(en_attente) == 1
    assert en_attente[0].event_type == "customer.subscription.created"


# ─────────────────────────────────────────────────────────────────────
# 8. Le drapeau « carte bancaire à l'inscription Free » (DEC-2026-0809-10)
# ─────────────────────────────────────────────────────────────────────


def test_sans_le_drapeau_l_inscription_free_ne_demande_pas_de_carte(socle, monkeypatch):
    from app.services import stripe_service
    monkeypatch.setattr(stripe_service, "FREE_SIGNUP_REQUIRES_CARD", False)
    assert stripe_service.free_signup_requires_card() is False


def test_avec_le_drapeau_l_inscription_free_demande_une_carte(socle, monkeypatch):
    from app.services import stripe_service
    monkeypatch.setattr(stripe_service, "FREE_SIGNUP_REQUIRES_CARD", True)
    assert stripe_service.free_signup_requires_card() is True


def test_le_drapeau_est_lu_dans_l_environnement(monkeypatch):
    """Les deux chemins sont pilotés par une seule variable, sans valeur
    devinée : tout ce qui n'est pas une valeur vraie reconnue vaut faux."""
    from app.services import stripe_service
    for valeur, attendu in (("true", True), ("1", True), ("yes", True),
                            ("false", False), ("", False), ("peut-etre", False)):
        assert stripe_service._lire_drapeau_carte(valeur) is attendu, valeur
