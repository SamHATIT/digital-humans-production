"""
Vague 1 / file B — BILL-01 (audit Astra du 06/09/2026, L633).

« Les crédits ne sont pas réservés atomiquement : dépassements et lignes
perdues. » Deux requêtes passent le préflight sur le même disponible ; les
débits lisent puis réécrivent `used_credits` sans verrou : le journal totalise
N débits et le solde n'en reflète qu'un. Le plafond Free, calculé par somme,
est dépassé par des commits concurrents.

Critère de sortie (mission) : N appels simultanés avec un solde pour N-1 →
exactement N-1 réussissent, la ligne perdante est journalisée, le solde =
somme du journal.

Ces tests tournent sur la base PostgreSQL de session (fixture `db_session`),
avec une session SQLAlchemy PAR FIL : `test_credit_service.py` tourne sur un
SQLite mémoire, qui ne prouve rien sur le verrouillage (`FOR UPDATE` n'y est
pas rendu).

Aucun appel réseau : le transport du routeur est remplacé. Le nom de modèle
est une valeur de fixture, pas un identifiant de service.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.credit import (
    TRANSACTION_TYPE_CHARGE,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.user import User
from app.services import llm_router_service as routeur_mod
from app.services.credit_service import (
    CreditError,
    CreditService,
    InsufficientCreditsError,
)
from app.services.llm_router_service import (
    LLMRequest,
    LLMResponse,
    LLMRouterService,
)

# 2 crédits / 1k jetons en entrée, 3 crédits / 1k en sortie.
MODELE = "modele-fictif-bill01"
FOURNISSEUR = "fictif/modele-fictif-bill01"
# Estimation d'une réservation : max_tokens en entrée ET en sortie
# (2 000 → 4 + 6 = 10 crédits). Un débit direct à (2 000, 2 000) coûte pareil.
MAX_TOKENS = 2000
CREDITS_PAR_APPEL = 10
N = 8
PLAFOND_FREE = 50          # 5 appels de 10 tiennent, le 6e ne tient pas


# ─────────────────────────────────────────────────────────────────────
# Socle
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def socle(db_session):
    db_session.add_all(
        [
            TierConfig(tier_name="free", monthly_credits=0,
                       daily_credits_cap=PLAFOND_FREE, price_eur_monthly=0,
                       description="free"),
            TierConfig(tier_name="pro", monthly_credits=15000,
                       daily_credits_cap=None, price_eur_monthly=79,
                       description="pro"),
            ModelPricing(model_name=MODELE, credits_per_1k_input=2.0,
                         credits_per_1k_output=3.0,
                         allowed_tiers="free,pro,team",
                         requires_opt_in=False, is_active=True),
        ]
    )
    db_session.commit()


def _compte(db_session, palier: str, solde: int | None = None) -> User:
    suffixe = uuid.uuid4().hex[:8]
    utilisateur = User(
        email=f"bill01-{suffixe}@exemple.test",
        hashed_password="x",
        name=f"Compte BILL-01 {suffixe}",
        subscription_tier=palier,
    )
    db_session.add(utilisateur)
    db_session.commit()
    db_session.refresh(utilisateur)
    if solde is not None:
        db_session.add(
            CreditBalance(
                user_id=utilisateur.id,
                included_credits=solde,
                used_credits=0,
                overage_credits=0,
                last_reset_at=datetime.now(timezone.utc),
            )
        )
        db_session.commit()
    return utilisateur


def _fabrique(db_session):
    """Une session SQLAlchemy indépendante par fil, sur la même base."""
    return sessionmaker(bind=db_session.get_bind(), autoflush=False,
                        autocommit=False, expire_on_commit=False)


def _en_parallele(fabrique, n: int, action):
    """Lance `action(service)` dans n fils, tous relâchés en même temps.

    Rend la liste des issues : ("ok", valeur), ("refus", exc) ou
    ("erreur", exc)."""
    barriere = threading.Barrier(n)
    issues = [None] * n

    def travail(i):
        session = fabrique()
        try:
            barriere.wait(timeout=10)
            issues[i] = ("ok", action(CreditService(session)))
        except InsufficientCreditsError as exc:
            issues[i] = ("refus", exc)
        except Exception as exc:  # noqa: BLE001 — l'issue est examinée
            issues[i] = ("erreur", exc)
        finally:
            session.close()

    fils = [threading.Thread(target=travail, args=(i,)) for i in range(n)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join(timeout=60)
    assert all(not fil.is_alive() for fil in fils), "un fil n'a pas rendu la main"
    return issues


def _solde(db_session, user_id: int) -> CreditBalance:
    db_session.expire_all()
    return db_session.query(CreditBalance).filter_by(user_id=user_id).one()


def _journal(db_session, user_id: int):
    db_session.expire_all()
    return (
        db_session.query(CreditTransaction)
        .filter(CreditTransaction.user_id == user_id)
        .order_by(CreditTransaction.id)
        .all()
    )


def _somme_journal(db_session, user_id: int) -> int:
    """Somme de ce qui compte dans le solde : débits réglés + réservations en cours."""
    return sum(
        ligne.credits_consumed or 0
        for ligne in _journal(db_session, user_id)
        if ligne.transaction_type in (TRANSACTION_TYPE_CHARGE, "reservation")
    )


def _issues(issues, genre):
    return [i for i in issues if i and i[0] == genre]


# ─────────────────────────────────────────────────────────────────────
# 1. Concurrence sur le débit direct (`charge`, API existante)
# ─────────────────────────────────────────────────────────────────────


def test_n_debits_simultanes_pour_un_solde_de_n_moins_un(db_session, socle):
    """Pro, solde pour N-1 débits, N débits en même temps : N-1 passent,
    un est refusé, le solde vaut la somme du journal."""
    utilisateur = _compte(db_session, "pro", solde=(N - 1) * CREDITS_PAR_APPEL)

    issues = _en_parallele(
        _fabrique(db_session), N,
        lambda svc: svc.charge(utilisateur.id, MODELE,
                               tokens_in=MAX_TOKENS, tokens_out=MAX_TOKENS),
    )

    assert not _issues(issues, "erreur"), _issues(issues, "erreur")
    assert len(_issues(issues, "ok")) == N - 1, [i[0] for i in issues]
    assert len(_issues(issues, "refus")) == 1

    solde = _solde(db_session, utilisateur.id)
    lignes = [l for l in _journal(db_session, utilisateur.id)
              if l.transaction_type == TRANSACTION_TYPE_CHARGE]
    assert len(lignes) == N - 1
    assert solde.used_credits == (N - 1) * CREDITS_PAR_APPEL
    assert solde.used_credits == _somme_journal(db_session, utilisateur.id)


# ─────────────────────────────────────────────────────────────────────
# 2. Concurrence sur la réservation (`reserve`, API BILL-01)
# ─────────────────────────────────────────────────────────────────────


def test_n_reservations_simultanees_pour_un_solde_de_n_moins_un(db_session, socle):
    """Même scénario, avant réseau : la réservation est atomique et la
    tentative perdante laisse une ligne à zéro dans le journal."""
    utilisateur = _compte(db_session, "pro", solde=(N - 1) * CREDITS_PAR_APPEL)

    issues = _en_parallele(
        _fabrique(db_session), N,
        lambda svc: svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS).id,
    )

    assert not _issues(issues, "erreur"), _issues(issues, "erreur")
    assert len(_issues(issues, "ok")) == N - 1, [i[0] for i in issues]
    assert len(_issues(issues, "refus")) == 1

    journal = _journal(db_session, utilisateur.id)
    reservations = [l for l in journal if l.transaction_type == "reservation"]
    refus = [l for l in journal if l.transaction_type == "refused"]
    assert len(reservations) == N - 1
    assert len(refus) == 1, "la tentative perdante doit être journalisée"
    assert refus[0].credits_consumed == 0
    assert "refus" in (refus[0].note or "").lower()

    solde = _solde(db_session, utilisateur.id)
    assert solde.used_credits == (N - 1) * CREDITS_PAR_APPEL
    assert solde.used_credits == _somme_journal(db_session, utilisateur.id)
    assert solde.available == 0


def test_le_plafond_journalier_free_tient_sous_concurrence(db_session, socle):
    """Free : plafond 50/jour, N réservations de 10 en même temps →
    exactement 5 passent ; la somme des lignes du jour ne dépasse pas 50."""
    utilisateur = _compte(db_session, "free")
    attendus = PLAFOND_FREE // CREDITS_PAR_APPEL

    issues = _en_parallele(
        _fabrique(db_session), N,
        lambda svc: svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS).id,
    )

    assert not _issues(issues, "erreur"), _issues(issues, "erreur")
    assert len(_issues(issues, "ok")) == attendus, [i[0] for i in issues]
    assert len(_issues(issues, "refus")) == N - attendus
    assert _somme_journal(db_session, utilisateur.id) == PLAFOND_FREE
    assert CreditService(db_session)._daily_used_credits(utilisateur.id) == PLAFOND_FREE


def test_la_creation_concurrente_du_solde_ne_perd_ni_ligne_ni_debit(db_session, socle):
    """Compte Pro sans ligne de solde : N premières réservations en même
    temps. Une seule ligne de solde, N réservations, solde = journal."""
    utilisateur = _compte(db_session, "pro")   # pas de CreditBalance

    issues = _en_parallele(
        _fabrique(db_session), N,
        lambda svc: svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS).id,
    )

    assert not _issues(issues, "erreur"), _issues(issues, "erreur")
    assert len(_issues(issues, "ok")) == N
    soldes = db_session.query(CreditBalance).filter_by(user_id=utilisateur.id).all()
    assert len(soldes) == 1
    assert soldes[0].included_credits == 15000
    assert soldes[0].used_credits == N * CREDITS_PAR_APPEL
    assert soldes[0].used_credits == _somme_journal(db_session, utilisateur.id)


# ─────────────────────────────────────────────────────────────────────
# 3. Cycle réservation → règlement / libération
# ─────────────────────────────────────────────────────────────────────


def test_le_reglement_au_cout_mesure_libere_le_reliquat(db_session, socle):
    utilisateur = _compte(db_session, "pro", solde=100)
    svc = CreditService(db_session)

    reservation = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    assert reservation.transaction_type == "reservation"
    assert reservation.credits_consumed == CREDITS_PAR_APPEL
    assert _solde(db_session, utilisateur.id).used_credits == CREDITS_PAR_APPEL

    # Coût mesuré : 500 jetons entrée (1.0) + 200 sortie (0.6) = 1.6 → 2 crédits.
    reglee = svc.settle(reservation.id, tokens_in=500, tokens_out=200, model=MODELE)
    assert reglee.id == reservation.id
    assert reglee.transaction_type == TRANSACTION_TYPE_CHARGE
    assert reglee.credits_consumed == 2
    assert reglee.tokens_input == 500 and reglee.tokens_output == 200

    solde = _solde(db_session, utilisateur.id)
    assert solde.used_credits == 2
    assert solde.used_credits == _somme_journal(db_session, utilisateur.id)
    assert len(_journal(db_session, utilisateur.id)) == 1


def test_un_appel_echoue_libere_la_reservation_et_laisse_une_trace(db_session, socle):
    utilisateur = _compte(db_session, "pro", solde=100)
    svc = CreditService(db_session)

    reservation = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    liberee = svc.release(reservation.id, reason="fournisseur injoignable (test)")

    assert liberee.transaction_type == "release"
    assert liberee.credits_consumed == 0
    assert "fournisseur injoignable" in (liberee.note or "")
    solde = _solde(db_session, utilisateur.id)
    assert solde.used_credits == 0
    assert solde.used_credits == _somme_journal(db_session, utilisateur.id)


def test_une_reservation_ne_se_regle_qu_une_fois(db_session, socle):
    """Contrôle : régler ou libérer deux fois la même réservation est refusé,
    sans toucher le solde."""
    utilisateur = _compte(db_session, "pro", solde=100)
    svc = CreditService(db_session)
    reservation = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    svc.settle(reservation.id, tokens_in=500, tokens_out=200, model=MODELE)

    with pytest.raises(CreditError):
        svc.settle(reservation.id, tokens_in=500, tokens_out=200, model=MODELE)
    with pytest.raises(CreditError):
        svc.release(reservation.id, reason="doublon")
    assert _solde(db_session, utilisateur.id).used_credits == 2


def test_le_solde_egale_le_journal_apres_un_melange_d_operations(db_session, socle):
    """Invariant de sortie d'Astra : solde = journal, vérifié par le service
    lui-même (`verify_ledger`), après réservations, règlements, libérations
    et débits directs mêlés."""
    utilisateur = _compte(db_session, "pro", solde=200)
    svc = CreditService(db_session)

    r1 = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    r2 = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    r3 = svc.reserve(utilisateur.id, MODELE, max_tokens=MAX_TOKENS)
    svc.settle(r1.id, tokens_in=1000, tokens_out=1000, model=MODELE)   # 5
    svc.release(r2.id, reason="échec")                                  # 0
    svc.charge(utilisateur.id, MODELE, tokens_in=1000, tokens_out=0)    # 2
    # r3 reste en cours : 10

    bilan = svc.verify_ledger(utilisateur.id)
    assert bilan["ok"] is True, bilan
    assert bilan["used_credits"] == 5 + 2 + 10
    assert bilan["journal"] == bilan["used_credits"]
    assert bilan["pending_reservations"] == 1


# ─────────────────────────────────────────────────────────────────────
# 4. Le routeur : réserve avant réseau, règle au coût mesuré, libère sur échec
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def routeur_simule(monkeypatch):
    """Transport remplacé ; le reste du routeur (crochets de crédit inclus)
    est le code de production."""
    etat = {"reussite": True, "appels": []}

    async def _faux_appel(self, request, provider_str):
        etat["appels"].append(request)
        if not etat["reussite"]:
            return LLMResponse(content="", provider=provider_str, model_id=MODELE,
                               tokens_in=0, tokens_out=0, cost_usd=0.0,
                               latency_ms=1, success=False,
                               error="panne simulée")
        return LLMResponse(content="ok", provider=provider_str, model_id=MODELE,
                           tokens_in=1000, tokens_out=1000, cost_usd=0.0,
                           latency_ms=1, success=True)

    monkeypatch.setattr(LLMRouterService, "_call_provider", _faux_appel)
    monkeypatch.setattr(LLMRouterService, "_select_provider",
                        lambda self, request: FOURNISSEUR)
    monkeypatch.setattr(LLMRouterService, "_get_model_id",
                        lambda self, provider_str: MODELE)
    monkeypatch.setattr(LLMRouterService, "_fallback_for",
                        lambda self, provider_str: None)
    monkeypatch.setattr(routeur_mod, "_router_instance", None, raising=False)
    return etat


def test_le_routeur_reserve_puis_regle_au_cout_mesure(db_session, socle, routeur_simule):
    utilisateur = _compte(db_session, "pro", solde=100)
    routeur = routeur_mod.get_llm_router()

    reponse = asyncio.run(routeur.complete(
        LLMRequest(prompt="x", agent_type="pm", max_tokens=MAX_TOKENS,
                   user_id=utilisateur.id)))
    assert reponse.success

    journal = _journal(db_session, utilisateur.id)
    assert [l.transaction_type for l in journal] == [TRANSACTION_TYPE_CHARGE]
    assert journal[0].credits_consumed == 5           # 2 + 3, pas l'estimation de 10
    assert journal[0].tokens_input == 1000
    solde = _solde(db_session, utilisateur.id)
    assert solde.used_credits == 5
    assert solde.used_credits == _somme_journal(db_session, utilisateur.id)


def test_le_routeur_libere_la_reservation_quand_l_appel_echoue(db_session, socle, routeur_simule):
    """Contrôle négatif : un appel échoué coûte 0 ET laisse une ligne."""
    utilisateur = _compte(db_session, "pro", solde=100)
    routeur_simule["reussite"] = False
    routeur = routeur_mod.get_llm_router()

    reponse = asyncio.run(routeur.complete(
        LLMRequest(prompt="x", agent_type="pm", max_tokens=MAX_TOKENS,
                   user_id=utilisateur.id)))
    assert not reponse.success

    journal = _journal(db_session, utilisateur.id)
    assert [l.transaction_type for l in journal] == ["release"]
    assert journal[0].credits_consumed == 0
    assert "panne simulée" in (journal[0].note or "")
    assert _solde(db_session, utilisateur.id).used_credits == 0


def test_le_routeur_refuse_avant_reseau_quand_le_solde_ne_couvre_pas_l_estimation(
    db_session, socle, routeur_simule
):
    """Solde 9 < estimation 10 : refusé AVANT l'appel, tentative journalisée."""
    utilisateur = _compte(db_session, "pro", solde=9)
    routeur = routeur_mod.get_llm_router()

    with pytest.raises(InsufficientCreditsError):
        asyncio.run(routeur.complete(
            LLMRequest(prompt="x", agent_type="pm", max_tokens=MAX_TOKENS,
                       user_id=utilisateur.id)))

    assert routeur_simule["appels"] == [], "l'appel réseau est parti malgré le refus"
    journal = _journal(db_session, utilisateur.id)
    assert [l.transaction_type for l in journal] == ["refused"]
    assert _solde(db_session, utilisateur.id).used_credits == 0
