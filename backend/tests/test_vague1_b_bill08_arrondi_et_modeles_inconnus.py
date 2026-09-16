"""
Vague 1 / file B — BILL-08 (audit Astra du 06/09/2026, L754).

« L'arrondi n'est pas un plafond supérieur et les modèles inconnus sont
tarifés par ressemblance. »

Deux défauts distincts :

1. ``_credits_for_tokens`` arrondit en ``ROUND_HALF_UP`` : 1,2 crédit brut
   devient 1, pas 2. La migration 015 et la FAQ du site annoncent un arrondi
   vers le haut par appel ; le minimum de 1 ne le prouve pas (il ne joue que
   sous 0,5).

2. ``_resolve_pricing`` retombe sur une correspondance de sous-chaîne
   opus/sonnet/haiku : un modèle servi non listé est tarifé au tarif d'une
   AUTRE version, et c'est cette autre version qui est écrite dans
   ``credit_transactions.model_used``. Contexte mesuré des 15-16/09 : des
   lignes ``model_pricing`` ont été ajoutées à la main pour la calibration —
   un modèle servi non listé doit être REFUSÉ, pas tarifé au plus proche
   (règle 6 : jamais de repli silencieux).

3. ``requires_opt_in`` n'est contrôlé nulle part : la colonne existe depuis la
   migration 008 et Opus la porte, aucun code ne la lit.

Les alias explicites (``claude-sonnet-4.6`` → ``claude-sonnet-4-6``) restent
résolus : ce qui est refusé, c'est la ressemblance, pas l'alias déclaré.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.user import User
from app.services.credit_service import (
    CreditService,
    ModelNotAllowedError,
    UnknownModelError,
    _credits_for_tokens,
)


@pytest.fixture
def socle(db_session):
    db_session.add_all(
        [
            TierConfig(tier_name="free", monthly_credits=0, daily_credits_cap=50,
                       price_eur_monthly=0, description="free"),
            TierConfig(tier_name="pro", monthly_credits=15000, daily_credits_cap=None,
                       price_eur_monthly=79, description="pro"),
            TierConfig(tier_name="team", monthly_credits=100000, daily_credits_cap=None,
                       price_eur_monthly=1490, description="team"),
            # Modèle listé, tarif « rond » : 1 crédit / 1k entrée, 5 / 1k sortie.
            ModelPricing(model_name="modele-liste-bill08",
                         credits_per_1k_input=1.0, credits_per_1k_output=5.0,
                         allowed_tiers="free,pro,team",
                         requires_opt_in=False, is_active=True),
            # Modèle réservé, opt-in exigé (comme Opus depuis la migration 008).
            ModelPricing(model_name="modele-opt-in-bill08",
                         credits_per_1k_input=5.0, credits_per_1k_output=25.0,
                         allowed_tiers="team",
                         requires_opt_in=True, is_active=True),
            # Modèle désactivé : ne doit jamais servir de tarif.
            ModelPricing(model_name="modele-retire-bill08",
                         credits_per_1k_input=1.0, credits_per_1k_output=1.0,
                         allowed_tiers="free,pro,team",
                         requires_opt_in=False, is_active=False),
        ]
    )
    db_session.commit()


def _compte(db_session, palier: str, solde: int = 10000) -> User:
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(email=f"bill08-{suffixe}@exemple.test", hashed_password="x",
                       name=f"Compte BILL-08 {suffixe}", subscription_tier=palier)
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)
    db_session.add(CreditBalance(user_id=utilisateur.id, included_credits=solde,
                                 used_credits=0, overage_credits=0))
    db_session.commit()
    return utilisateur


def _tarif(db_session, nom: str) -> ModelPricing:
    return db_session.query(ModelPricing).filter_by(model_name=nom).one()


# ─────────────────────────────────────────────────────────────────────
# 1. Arrondi : plafond supérieur, par appel
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "jetons_in, jetons_out, attendu",
    [
        # 1 200 entrée = 1,2 crédit brut → 2, pas 1 (l'exemple de l'audit).
        (1200, 0, 2),
        # 0,2 crédit brut → 1 (minimum par appel, déjà tenu).
        (200, 0, 1),
        # 1 000 entrée = 1,0 pile → 1 : un compte rond ne monte pas d'un cran.
        (1000, 0, 1),
        # 1 001 entrée = 1,001 → 2 : le moindre dépassement monte.
        (1001, 0, 2),
        # 1 600 entrée = 1,6 → 2 (identique sous HALF_UP : ne discrimine pas).
        (1600, 0, 2),
        # 1 000 entrée + 1 000 sortie = 1 + 5 = 6 pile.
        (1000, 1000, 6),
        # 1 200 entrée + 1 300 sortie = 1,2 + 6,5 = 7,7 → 8.
        (1200, 1300, 8),
        # Appel vide : 0 crédit, pas le minimum de 1.
        (0, 0, 0),
    ],
)
def test_l_arrondi_est_un_plafond_superieur(db_session, socle, jetons_in, jetons_out, attendu):
    tarif = _tarif(db_session, "modele-liste-bill08")
    assert _credits_for_tokens(tarif, jetons_in, jetons_out) == attendu


def test_l_arrondi_ne_descend_jamais_sous_le_cout_brut(db_session, socle):
    """Propriété, pas cas par cas : le crédit facturé est toujours >= au coût
    brut, et jamais plus d'un crédit au-dessus."""
    tarif = _tarif(db_session, "modele-liste-bill08")
    for jetons_in in range(0, 3000, 137):
        for jetons_out in range(0, 2000, 211):
            brut = (Decimal(jetons_in) / 1000 * Decimal("1.0")
                    + Decimal(jetons_out) / 1000 * Decimal("5.0"))
            facture = _credits_for_tokens(tarif, jetons_in, jetons_out)
            assert Decimal(facture) >= brut, (jetons_in, jetons_out, brut, facture)
            if brut > 0:
                assert Decimal(facture) - brut < 1, (jetons_in, jetons_out)


def test_le_debit_reel_applique_le_plafond_superieur(db_session, socle):
    """Le plafond supérieur n'est pas qu'une fonction : il atteint le journal."""
    utilisateur = _compte(db_session, "pro")
    tx = CreditService(db_session).charge(utilisateur.id, "modele-liste-bill08",
                                          tokens_in=1200, tokens_out=0)
    assert tx.credits_consumed == 2


# ─────────────────────────────────────────────────────────────────────
# 2. Modèle inconnu : refus, pas ressemblance
# ─────────────────────────────────────────────────────────────────────


def test_un_modele_inconnu_ressemblant_est_refuse(db_session, socle):
    """Le cœur de BILL-08 : un modèle servi non listé ne doit PAS être tarifé
    au tarif d'un homonyme. Ici un nom qui contient « sonnet » alors qu'aucune
    ligne ne le porte."""
    db_session.add(ModelPricing(model_name="claude-sonnet-ancien-bill08",
                                credits_per_1k_input=1.0, credits_per_1k_output=5.0,
                                allowed_tiers="pro,team", requires_opt_in=False,
                                is_active=True))
    db_session.commit()
    svc = CreditService(db_session)

    with pytest.raises(UnknownModelError) as capture:
        svc._resolve_pricing("claude-sonnet-9-nouveau-non-liste")

    message = str(capture.value)
    assert "claude-sonnet-9-nouveau-non-liste" in message
    assert "model_pricing" in message, (
        "le refus doit dire quoi faire, pas seulement qu'il refuse"
    )


def test_un_modele_inconnu_ressemblant_n_est_pas_debite(db_session, socle):
    """Contrôle de bout en bout : aucune ligne de crédit, aucun débit."""
    utilisateur = _compte(db_session, "pro")
    svc = CreditService(db_session)

    with pytest.raises(UnknownModelError):
        svc.charge(utilisateur.id, "modele-inconnu-qui-ressemble-a-rien",
                   tokens_in=1000, tokens_out=1000)

    assert db_session.query(CreditTransaction).filter_by(user_id=utilisateur.id).count() == 0
    solde = db_session.query(CreditBalance).filter_by(user_id=utilisateur.id).one()
    assert solde.used_credits == 0


def test_un_modele_inconnu_ne_peut_pas_etre_reserve(db_session, socle):
    """La réservation (BILL-01) refuse aussi : on ne retient pas des crédits
    pour un appel qu'on ne saura pas facturer."""
    utilisateur = _compte(db_session, "pro")
    with pytest.raises(UnknownModelError):
        CreditService(db_session).reserve(utilisateur.id, "modele-opus-inexistant-bill08",
                                          max_tokens=2000)


def test_controle_positif_un_modele_liste_est_bien_resolu(db_session, socle):
    """Contrôle positif : le refus ne vient pas d'un refus global."""
    tarif = CreditService(db_session)._resolve_pricing("modele-liste-bill08")
    assert tarif.model_name == "modele-liste-bill08"


def test_le_prefixe_fournisseur_est_toujours_accepte(db_session, socle):
    """« fournisseur/modele » reste résolu : c'est une normalisation
    déclarée, pas une ressemblance."""
    tarif = CreditService(db_session)._resolve_pricing("fictif/modele-liste-bill08")
    assert tarif.model_name == "modele-liste-bill08"


def test_un_modele_desactive_est_refuse_et_ne_sert_pas_de_repli(db_session, socle):
    """`is_active=False` veut dire retiré : ni tarif direct, ni repli."""
    svc = CreditService(db_session)
    with pytest.raises(UnknownModelError):
        svc._resolve_pricing("modele-retire-bill08")


def test_le_modele_reellement_servi_est_celui_qui_est_journalise(db_session, socle):
    """« conserver le modèle réellement servi » : la ligne porte le nom
    demandé, pas celui d'une autre version."""
    utilisateur = _compte(db_session, "pro")
    tx = CreditService(db_session).charge(utilisateur.id, "fictif/modele-liste-bill08",
                                          tokens_in=1000, tokens_out=1000)
    assert tx.model_used == "modele-liste-bill08"
    assert tx.transaction_type == TRANSACTION_TYPE_CHARGE


# ─────────────────────────────────────────────────────────────────────
# 3. requires_opt_in : la colonne est enfin lue
# ─────────────────────────────────────────────────────────────────────


def test_un_modele_a_opt_in_est_refuse_sans_consentement(db_session, socle):
    """Palier autorisé (team) MAIS opt-in non donné → refus explicite."""
    utilisateur = _compte(db_session, "team")
    with pytest.raises(ModelNotAllowedError) as capture:
        CreditService(db_session).charge(utilisateur.id, "modele-opt-in-bill08",
                                         tokens_in=1000, tokens_out=0)
    assert "opt-in" in str(capture.value).lower()


def test_un_modele_a_opt_in_passe_quand_le_consentement_est_donne(db_session, socle):
    """Contrôle positif : avec `opt_in=True`, le même appel passe. Sans ce
    contrôle, un refus systématique passerait le test précédent."""
    utilisateur = _compte(db_session, "team")
    tx = CreditService(db_session).charge(utilisateur.id, "modele-opt-in-bill08",
                                          tokens_in=1000, tokens_out=0, opt_in=True)
    assert tx.credits_consumed == 5


def test_l_opt_in_ne_rattrape_pas_un_palier_non_autorise(db_session, socle):
    """Contrôle négatif : l'opt-in n'est pas un passe-droit de palier."""
    utilisateur = _compte(db_session, "free")
    with pytest.raises(ModelNotAllowedError):
        CreditService(db_session).charge(utilisateur.id, "modele-opt-in-bill08",
                                         tokens_in=1000, tokens_out=0, opt_in=True)
