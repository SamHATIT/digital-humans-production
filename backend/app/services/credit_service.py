"""
Credit Service — Phase 3.1+3.2 of MASTER_PLAN_V4.

Source de vérité pour la consommation de crédits LLM.

Public API
----------
- CreditService.reserve(user_id, model, max_tokens, ...)  — BILL-01 : retient
  l'estimation sous verrou de la ligne de solde, AVANT l'appel réseau.
- CreditService.settle(reservation_id, tokens_in, tokens_out, model) — règle la
  réservation au coût mesuré et rend le reliquat.
- CreditService.release(reservation_id, reason) — appel échoué : rend tout,
  garde une ligne à 0.
- CreditService.charge(user_id, model, tokens_in, tokens_out, ...) — débit
  direct en une seule étape, sous le même verrou.
- CreditService.get_balance(user_id)
- CreditService.reset_monthly(user_id)
- CreditService.preflight(user_id, model, max_tokens) — contrôle sans écriture.
- CreditService.verify_ledger(user_id) — invariant « solde = journal ».

Concurrence (BILL-01, audit Astra L633) : toute écriture sur ``used_credits``
se fait dans une transaction qui tient ``SELECT … FOR UPDATE`` sur la ligne
``credit_balances`` de l'utilisateur ; le plafond journalier (somme du journal)
est calculé sous ce même verrou. Sur SQLite le verrou n'est pas rendu : les
preuves de concurrence tournent sur PostgreSQL
(``tests/test_vague1_b_bill01_reservation_atomique.py``).

Le mapping User.subscription_tier (free/premium/enterprise) → credit tier
(free/pro/team) est centralisé dans :func:`resolve_credit_tier`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.credit import (
    LEDGER_DEBIT_TYPES,
    TRANSACTION_TYPE_CHARGE,
    TRANSACTION_TYPE_REFUSED,
    TRANSACTION_TYPE_RELEASE,
    TRANSACTION_TYPE_RESERVATION,
    TRANSACTION_TYPE_RESET,
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CreditError(Exception):
    """Base class for credit-system errors."""


class InsufficientCreditsError(CreditError):
    """User does not have enough credits for the requested operation."""

    def __init__(self, user_id: int, requested: int, available: int):
        self.user_id = user_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient credits for user {user_id}: requested={requested}, available={available}"
        )


class ModelNotAllowedError(CreditError):
    """The user's tier is not authorized to use this model."""

    def __init__(self, user_id: int, model: str, tier: str,
                 raison: Optional[str] = None):
        self.user_id = user_id
        self.model = model
        self.tier = tier
        self.raison = raison
        message = f"Model '{model}' not allowed for tier '{tier}' (user {user_id})"
        if raison:
            message = f"{message} : {raison}"
        super().__init__(message)


class UnknownModelError(CreditError):
    """No pricing row found for the requested model."""


class ReservationStateError(CreditError):
    """La réservation visée n'existe pas ou n'est plus en cours (déjà réglée
    ou libérée). Régler deux fois la même réservation est refusé."""


# ---------------------------------------------------------------------------
# Tier mapping
# ---------------------------------------------------------------------------

# Map User.subscription_tier values → credit tier names used by tier_config.
# Since 29 avril 2026 the canonical 4-tier model is free / pro / team / enterprise.
# Legacy 'premium' values from the old 3-tier model are mapped to 'team' because
# the old 99€ Premium tier included BUILD, which now lives in the Team tier (not
# in the new 49€ Pro tier). 'enterprise' is mapped to 'team' for the credit
# accounting (no dedicated enterprise row in tier_config — Enterprise contracts
# are billed annually, not metered through credit_balances).
_TIER_ALIAS = {
    "free": "free",
    "pro": "pro",
    "team": "team",
    "enterprise": "team",   # credit accounting only — see comment above
    # --- Legacy aliases (DEPRECATED, will be removed once migration 009 lands) ---
    "premium": "team",      # was 99€ with BUILD → equivalent to current Team tier
}


def resolve_credit_tier(user: User) -> str:
    """Map a User to its credit tier (free/pro/team). Defaults to ``free``."""
    raw = (user.subscription_tier or "free").lower()
    return _TIER_ALIAS.get(raw, "free")


# ---------------------------------------------------------------------------
# Model name normalisation
# ---------------------------------------------------------------------------

def _normalize_model_name(model: str) -> str:
    """Strip provider prefix and trim."""
    if not model:
        return ""
    if "/" in model:
        model = model.split("/", 1)[1]
    return model.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _credits_for_tokens(
    pricing: ModelPricing, tokens_in: int, tokens_out: int
) -> int:
    """
    Crédits entiers consommés pour un couple (entrée, sortie).

    Decimal pour éviter la dérive flottante, **arrondi au plafond supérieur
    par appel** (BILL-08), minimum 1 crédit dès que le coût brut est positif.

    L'arrondi était ``ROUND_HALF_UP`` : 1,2 crédit brut devenait 1. L'engagement
    publié (migration 015, FAQ crédits du site) est l'arrondi supérieur par
    appel, et le minimum de 1 ne le tenait que sous 0,5. Un compte rond ne
    monte pas d'un cran (1,0 reste 1) ; le moindre dépassement monte (1,001 → 2).

    Unité publiée : 1 crédit, par appel.
    """
    # Use str() to keep Decimal precision when SQLAlchemy returns NUMERIC as float (SQLite).
    in_credits = (Decimal(int(tokens_in or 0)) / Decimal(1000)) * Decimal(
        str(pricing.credits_per_1k_input or 0)
    )
    out_credits = (Decimal(int(tokens_out or 0)) / Decimal(1000)) * Decimal(
        str(pricing.credits_per_1k_output or 0)
    )
    raw = in_credits + out_credits
    if raw <= 0:
        return 0
    rounded = int(raw.to_integral_value(rounding=ROUND_CEILING))
    return max(rounded, 1)


def _is_daily_cap_quota_tier(tier_cfg: Optional[TierConfig]) -> bool:
    """
    True when the tier's spendable quota is the daily cap itself, with no
    monthly allotment (Free today). For such tiers ``balance.available`` is
    structurally 0 and must be ignored — the daily cap is the quota.
    """
    return (
        tier_cfg is not None
        and tier_cfg.daily_credits_cap is not None
        and (tier_cfg.monthly_credits or 0) == 0
    )


def _start_of_day_utc(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_month_start(reference: datetime) -> datetime:
    """First day of the calendar month following ``reference`` (UTC, midnight)."""
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    if reference.month == 12:
        return reference.replace(
            year=reference.year + 1,
            month=1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
    return reference.replace(
        month=reference.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


# ---------------------------------------------------------------------------
# CreditService
# ---------------------------------------------------------------------------


class CreditService:
    """Business logic for credit consumption, balance and reset."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_balance(self, user_id: int) -> dict:
        """
        Return the user's current credit picture. Lazy-creates the balance
        row (and its initial allotment) if missing.
        """
        balance = self._ensure_balance(user_id)
        user = self.db.get(User, user_id)
        tier_name = resolve_credit_tier(user) if user else "free"
        tier = self._get_tier_config(tier_name)

        daily_used = self._daily_used_credits(user_id)
        next_reset = _next_month_start(balance.last_reset_at)

        # For daily-cap quota tiers (Free), the spendable balance is what's
        # left of today's cap, not the (always 0) included balance.
        if _is_daily_cap_quota_tier(tier):
            available = max(0, tier.daily_credits_cap - daily_used)
        else:
            available = balance.available

        return {
            "user_id": user_id,
            "tier": tier_name,
            "included_credits": balance.included_credits,
            "used_credits": balance.used_credits,
            "overage_credits": balance.overage_credits,
            "available": available,
            "daily_cap": tier.daily_credits_cap if tier else None,
            "daily_used": daily_used,
            "last_reset_at": balance.last_reset_at,
            "next_reset_at": next_reset,
        }

    def charge(
        self,
        user_id: int,
        model: str,
        tokens_in: int,
        tokens_out: int,
        execution_id: Optional[int] = None,
        project_id: Optional[int] = None,
        note: Optional[str] = None,
        opt_in: bool = False,
    ) -> CreditTransaction:
        """
        Débit direct en une étape (coût déjà connu) : contrôle du quota et
        écriture sous verrou de la ligne de solde.

        Raises:
            UnknownModelError       — no pricing row matches ``model``.
            ModelNotAllowedError    — user's tier cannot use this model.
            InsufficientCreditsError — balance (or daily cap for free tier)
                                       cannot cover the cost. La tentative
                                       refusée laisse une ligne ``refused`` à 0.
        """
        tier_name, pricing = self._tier_and_pricing(user_id, model, opt_in=opt_in)
        credits = _credits_for_tokens(pricing, tokens_in, tokens_out)
        tier_cfg = self._get_tier_config(tier_name)
        self._ensure_balance(user_id)

        try:
            balance = self._lock_balance(user_id)
            self._check_quota(user_id, tier_cfg, balance, credits)
            balance.used_credits = (balance.used_credits or 0) + credits
            tx = CreditTransaction(
                user_id=user_id,
                transaction_type=TRANSACTION_TYPE_CHARGE,
                model_used=pricing.model_name,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                credits_consumed=credits,
                execution_id=execution_id,
                project_id=project_id,
                note=note,
            )
            self.db.add(tx)
            self.db.commit()
        except InsufficientCreditsError as exc:
            self.db.rollback()
            self._journal_refus(user_id, pricing, credits, exc, execution_id, project_id)
            raise
        except SQLAlchemyError:
            self.db.rollback()
            raise

        self.db.refresh(tx)
        logger.info(
            "[CreditService] charged user=%s model=%s credits=%s tokens=(%s,%s)",
            user_id, pricing.model_name, credits, tokens_in, tokens_out,
        )
        return tx

    # ------------------------------------------------------------------
    # BILL-01 — réservation avant réseau, règlement au coût mesuré
    # ------------------------------------------------------------------

    def reserve(
        self,
        user_id: int,
        model: str,
        max_tokens: int,
        execution_id: Optional[int] = None,
        project_id: Optional[int] = None,
        note: Optional[str] = None,
        opt_in: bool = False,
    ) -> CreditTransaction:
        """
        Retient, sous verrou, l'estimation d'un appel (``max_tokens`` en
        entrée et en sortie, comme :meth:`preflight`) et l'écrit dans le
        journal en ``reservation``. ``used_credits`` monte de l'estimation :
        deux réservations concurrentes ne peuvent pas passer sur le même
        disponible.

        Rend la ligne de réservation ; son ``id`` sert à :meth:`settle` ou
        :meth:`release`. Une tentative refusée laisse une ligne ``refused`` à 0.
        """
        tier_name, pricing = self._tier_and_pricing(user_id, model, opt_in=opt_in)
        estimate = _credits_for_tokens(pricing, max_tokens, max_tokens)
        tier_cfg = self._get_tier_config(tier_name)
        self._ensure_balance(user_id)

        try:
            balance = self._lock_balance(user_id)
            self._check_quota(user_id, tier_cfg, balance, estimate)
            balance.used_credits = (balance.used_credits or 0) + estimate
            tx = CreditTransaction(
                user_id=user_id,
                transaction_type=TRANSACTION_TYPE_RESERVATION,
                model_used=pricing.model_name,
                tokens_input=None,
                tokens_output=None,
                credits_consumed=estimate,
                execution_id=execution_id,
                project_id=project_id,
                note=note or f"réservation : max_tokens={int(max_tokens)}",
            )
            self.db.add(tx)
            self.db.commit()
        except InsufficientCreditsError as exc:
            self.db.rollback()
            self._journal_refus(user_id, pricing, estimate, exc, execution_id, project_id)
            raise
        except SQLAlchemyError:
            self.db.rollback()
            raise

        self.db.refresh(tx)
        logger.info(
            "[CreditService] reserved user=%s model=%s credits=%s reservation=%s",
            user_id, pricing.model_name, estimate, tx.id,
        )
        return tx

    def settle(
        self,
        reservation_id: int,
        tokens_in: int,
        tokens_out: int,
        model: Optional[str] = None,
    ) -> CreditTransaction:
        """
        Règle une réservation au coût mesuré : la ligne devient ``charge``
        avec les jetons réels et le modèle réellement servi ; ``used_credits``
        est corrigé de la différence (reliquat rendu, ou complément débité si
        la sortie a dépassé l'estimation — le jeton est consommé, on ne
        refuse pas après coup).

        Raises ReservationStateError si la réservation n'est pas en cours.
        """
        try:
            tx = self._lock_reservation(reservation_id)
            pricing = self._resolve_pricing(model or tx.model_used)
            actual = _credits_for_tokens(pricing, tokens_in, tokens_out)
            balance = self._lock_balance(tx.user_id)
            delta = actual - (tx.credits_consumed or 0)
            balance.used_credits = (balance.used_credits or 0) + delta
            tx.transaction_type = TRANSACTION_TYPE_CHARGE
            tx.credits_consumed = actual
            tx.tokens_input = tokens_in
            tx.tokens_output = tokens_out
            tx.model_used = pricing.model_name
            tx.note = f"{tx.note or ''} ; réglée : {actual} crédits mesurés".strip(" ;")
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except CreditError:
            self.db.rollback()
            raise
        self.db.refresh(tx)
        logger.info(
            "[CreditService] settled reservation=%s user=%s credits=%s tokens=(%s,%s)",
            tx.id, tx.user_id, actual, tokens_in, tokens_out,
        )
        return tx

    def release(self, reservation_id: int, reason: str) -> CreditTransaction:
        """
        Appel échoué : rend toute la réservation. La ligne reste dans le
        journal en ``release`` à 0 crédit, avec le motif — « une tentative
        aboutit à un état traçable, y compris débit nul/échec ».
        """
        try:
            tx = self._lock_reservation(reservation_id)
            balance = self._lock_balance(tx.user_id)
            balance.used_credits = (balance.used_credits or 0) - (tx.credits_consumed or 0)
            tx.transaction_type = TRANSACTION_TYPE_RELEASE
            tx.credits_consumed = 0
            tx.tokens_input = 0
            tx.tokens_output = 0
            tx.note = f"{tx.note or ''} ; libérée : {reason}".strip(" ;")
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        except CreditError:
            self.db.rollback()
            raise
        self.db.refresh(tx)
        logger.info("[CreditService] released reservation=%s user=%s (%s)",
                    tx.id, tx.user_id, reason)
        return tx

    def verify_ledger(self, user_id: int) -> dict:
        """
        Invariant de sortie (Astra) : ``used_credits`` == somme des lignes
        ``charge`` + ``reservation`` créées depuis ``last_reset_at``.
        Rend un bilan ; ``ok`` est False si le solde et le journal divergent.
        """
        balance = self._ensure_balance(user_id)
        self.db.refresh(balance)
        journal = int(
            self.db.query(func.coalesce(func.sum(CreditTransaction.credits_consumed), 0))
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type.in_(LEDGER_DEBIT_TYPES),
                CreditTransaction.created_at >= balance.last_reset_at,
            )
            .scalar()
            or 0
        )
        pending = (
            self.db.query(func.count(CreditTransaction.id))
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type == TRANSACTION_TYPE_RESERVATION,
            )
            .scalar()
            or 0
        )
        used = int(balance.used_credits or 0)
        return {
            "user_id": user_id,
            "used_credits": used,
            "journal": journal,
            "pending_reservations": int(pending),
            "since": balance.last_reset_at,
            "ok": used == journal,
        }

    def list_pending_reservations(self, older_than: Optional[datetime] = None) -> list:
        """Réservations jamais réglées ni libérées (règlement échoué après un
        appel réussi, processus tué…) : à réconcilier à la main ou par un
        cron. Le crédit retenu reste compté tant que la ligne est en cours."""
        q = self.db.query(CreditTransaction).filter(
            CreditTransaction.transaction_type == TRANSACTION_TYPE_RESERVATION
        )
        if older_than is not None:
            q = q.filter(CreditTransaction.created_at < older_than)
        return q.order_by(CreditTransaction.created_at.asc()).all()

    def reset_monthly(self, user_id: int) -> CreditBalance:
        """
        Reset ``used_credits`` to 0 and refill ``included_credits`` based on
        the user's tier. Logs a reset transaction for traceability.
        """
        user = self.db.get(User, user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        tier_cfg = self._get_tier_config(tier_name)
        monthly = tier_cfg.monthly_credits if tier_cfg else 0

        self._ensure_balance(user_id)
        balance = self._lock_balance(user_id)
        previous_used = balance.used_credits or 0
        balance.used_credits = 0
        balance.included_credits = monthly
        balance.last_reset_at = datetime.now(timezone.utc)

        tx = CreditTransaction(
            user_id=user_id,
            transaction_type=TRANSACTION_TYPE_RESET,
            credits_consumed=0,
            note=f"Monthly reset (tier={tier_name}, refilled {monthly}, previously used {previous_used})",
        )
        self.db.add(tx)
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(balance)
        return balance

    # ------------------------------------------------------------------
    # Pre-flight (used by LLM router)
    # ------------------------------------------------------------------

    def preflight(
        self,
        user_id: int,
        model: str,
        max_tokens: int,
        opt_in: bool = False,
    ) -> None:
        """
        Contrôle sans écriture, même estimation que :meth:`reserve`. Lève
        les mêmes erreurs mais ne retient rien : deux préflights concurrents
        peuvent passer sur le même disponible. Le routeur utilise
        :meth:`reserve` (BILL-01) ; ceci reste pour un contrôle d'affichage.
        """
        tier_name, pricing = self._tier_and_pricing(user_id, model, opt_in=opt_in)
        estimate = _credits_for_tokens(pricing, max_tokens, max_tokens)
        balance = self._ensure_balance(user_id)
        tier_cfg = self._get_tier_config(tier_name)
        self._check_quota(user_id, tier_cfg, balance, estimate)

    # ------------------------------------------------------------------
    # Usage helpers (for /api/billing/usage)
    # ------------------------------------------------------------------

    def get_usage(self, user_id: int, days: int = 30) -> dict:
        """
        Aggregated usage report : total credits, breakdown by model, daily
        time series. ``days`` clamped between 1 and 365.
        """
        days = max(1, min(int(days or 30), 365))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            self.db.query(CreditTransaction)
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.created_at >= since,
                CreditTransaction.transaction_type == TRANSACTION_TYPE_CHARGE,
            )
            .all()
        )

        total_credits = 0
        total_tokens_in = 0
        total_tokens_out = 0
        by_model: dict[str, dict] = {}
        by_day: dict[str, int] = {}

        for r in rows:
            credits = r.credits_consumed or 0
            total_credits += credits
            total_tokens_in += r.tokens_input or 0
            total_tokens_out += r.tokens_output or 0

            model_key = r.model_used or "unknown"
            bucket = by_model.setdefault(
                model_key,
                {"credits": 0, "calls": 0, "tokens_input": 0, "tokens_output": 0},
            )
            bucket["credits"] += credits
            bucket["calls"] += 1
            bucket["tokens_input"] += r.tokens_input or 0
            bucket["tokens_output"] += r.tokens_output or 0

            day = r.created_at.date().isoformat() if r.created_at else "unknown"
            by_day[day] = by_day.get(day, 0) + credits

        timeline = [
            {"day": day, "credits": value}
            for day, value in sorted(by_day.items())
        ]

        return {
            "user_id": user_id,
            "period_days": days,
            "since": since,
            "total_credits": total_credits,
            "total_tokens_input": total_tokens_in,
            "total_tokens_output": total_tokens_out,
            "by_model": by_model,
            "timeline": timeline,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tier_and_pricing(self, user_id: int, model: str, opt_in: bool = False):
        """Palier de l'utilisateur et tarif du modèle ; lève avant tout verrou.

        BILL-08 : ``requires_opt_in`` est enfin lu. La colonne existe depuis la
        migration 008 et Opus la porte ; aucun code ne la contrôlait, donc un
        modèle « sur demande explicite » était servi sans demande. L'opt-in
        s'ajoute au palier, il ne le remplace pas : un Free consentant n'a
        toujours pas droit à un modèle réservé au Team.
        """
        user = self.db.get(User, user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        pricing = self._resolve_pricing(model)
        if not pricing.tier_allowed(tier_name):
            raise ModelNotAllowedError(user_id, pricing.model_name, tier_name)
        if pricing.requires_opt_in and not opt_in:
            raise ModelNotAllowedError(
                user_id, pricing.model_name, tier_name,
                raison=(
                    f"le modèle '{pricing.model_name}' exige un opt-in explicite "
                    f"(model_pricing.requires_opt_in) ; il n'a pas été donné "
                    f"pour cet appel"
                ),
            )
        return tier_name, pricing

    def _check_quota(
        self,
        user_id: int,
        tier_cfg: Optional[TierConfig],
        balance: CreditBalance,
        credits: int,
    ) -> None:
        """Plafond journalier puis disponible mensuel. Appelé sous verrou par
        ``charge``/``reserve`` (la somme journalière est alors sérialisée par
        utilisateur), sans verrou par ``preflight``."""
        daily_cap = tier_cfg.daily_credits_cap if tier_cfg else None
        if daily_cap is not None and credits > 0:
            daily_used = self._daily_used_credits(user_id)
            if daily_used + credits > daily_cap:
                raise InsufficientCreditsError(
                    user_id=user_id,
                    requested=credits,
                    available=max(0, daily_cap - daily_used),
                )
        # Disponible mensuel — ignoré pour les paliers à quota journalier
        # (Free) où included=0 et le plafond du jour EST le quota.
        if not _is_daily_cap_quota_tier(tier_cfg) and credits > balance.available:
            raise InsufficientCreditsError(
                user_id=user_id, requested=credits, available=balance.available
            )

    def _lock_balance(self, user_id: int) -> CreditBalance:
        """``SELECT … FOR UPDATE`` sur la ligne de solde : sérialise toute
        écriture de ``used_credits`` pour cet utilisateur. La ligne doit
        exister (voir :meth:`_ensure_balance`).

        ``populate_existing()`` est indispensable, pas décoratif : sans lui,
        une session qui a déjà chargé cette ligne (c'est le cas après
        ``_ensure_balance``) reçoit l'objet de sa carte d'identité SANS relire
        les colonnes. Le verrou serait pris, puis l'incrément calculé sur une
        valeur périmée — mesuré : 8 réservations concurrentes, une seule
        comptée dans ``used_credits``.
        """
        balance = (
            self.db.query(CreditBalance)
            .filter_by(user_id=user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if balance is None:
            raise CreditError(f"No credit balance row for user {user_id}")
        return balance

    def _lock_reservation(self, reservation_id: int) -> CreditTransaction:
        tx = (
            self.db.query(CreditTransaction)
            .filter_by(id=reservation_id)
            .populate_existing()
            .with_for_update()
            .first()
        )
        if tx is None:
            raise ReservationStateError(f"Reservation {reservation_id} not found")
        if tx.transaction_type != TRANSACTION_TYPE_RESERVATION:
            raise ReservationStateError(
                f"Reservation {reservation_id} is not pending "
                f"(state={tx.transaction_type}) — already settled or released"
            )
        return tx

    def _journal_refus(
        self,
        user_id: int,
        pricing: ModelPricing,
        requested: int,
        exc: InsufficientCreditsError,
        execution_id: Optional[int],
        project_id: Optional[int],
    ) -> None:
        """Ligne ``refused`` à 0 crédit pour la tentative perdante. Écrite
        dans sa propre transaction, après le rollback ; un échec ici est
        journalisé mais ne masque pas le refus lui-même."""
        try:
            self.db.add(
                CreditTransaction(
                    user_id=user_id,
                    transaction_type=TRANSACTION_TYPE_REFUSED,
                    model_used=pricing.model_name,
                    tokens_input=0,
                    tokens_output=0,
                    credits_consumed=0,
                    execution_id=execution_id,
                    project_id=project_id,
                    note=(
                        f"refus : {requested} crédits demandés, "
                        f"{exc.available} disponibles"
                    ),
                )
            )
            self.db.commit()
        except SQLAlchemyError as err:  # pragma: no cover — chemin de secours
            self.db.rollback()
            logger.error("[CreditService] refus non journalisé (user=%s) : %s", user_id, err)

    def _ensure_balance(self, user_id: int) -> CreditBalance:
        balance = self.db.query(CreditBalance).filter_by(user_id=user_id).first()
        if balance is not None:
            return balance

        user = self.db.get(User, user_id)
        if user is None:
            raise CreditError(f"User {user_id} not found")
        tier_name = resolve_credit_tier(user)
        tier_cfg = self._get_tier_config(tier_name)
        included = tier_cfg.monthly_credits if tier_cfg else 0

        balance = CreditBalance(
            user_id=user_id,
            included_credits=included,
            used_credits=0,
            overage_credits=0,
            last_reset_at=datetime.now(timezone.utc),
        )
        self.db.add(balance)
        try:
            self.db.commit()
        except IntegrityError:
            # Course à la création (deux premiers appels simultanés) : l'autre
            # session a gagné, on relit sa ligne.
            self.db.rollback()
            balance = self.db.query(CreditBalance).filter_by(user_id=user_id).first()
            if balance is None:
                raise
            return balance
        except SQLAlchemyError:
            self.db.rollback()
            raise
        self.db.refresh(balance)
        return balance

    def _resolve_pricing(self, model: str) -> ModelPricing:
        """
        Tarif du modèle, par correspondance EXACTE sur ``model_pricing``
        (préfixe fournisseur retiré au passage : ``fictif/x`` → ``x``).

        BILL-08 : le repli par sous-chaîne opus/sonnet/haiku est supprimé. Il
        tarifait un modèle servi non listé au tarif d'une autre version, et
        écrivait cette autre version dans ``credit_transactions.model_used`` —
        le grand livre ne disait donc pas ce qui avait réellement été servi.

        Un modèle inconnu est REFUSÉ (règle 6 : jamais de repli silencieux). Le
        message dit quoi faire : ajouter la ligne dans ``model_pricing``. Pour
        une nouvelle version, on ajoute un alias explicite vers un tarif
        versionné — ce que fait déjà la migration 008 (``claude-sonnet-4.6``
        à côté de ``claude-sonnet-4-6``) — on ne devine pas.

        Une ligne ``is_active=False`` vaut retirée : elle ne tarife rien.
        """
        normalized = _normalize_model_name(model)
        if normalized:
            row = self.db.query(ModelPricing).filter_by(model_name=normalized).first()
            if row is not None and row.is_active:
                return row

        raise UnknownModelError(
            f"Modèle '{model}' absent de model_pricing (ou désactivé) : "
            "aucun tarif connu, l'appel est refusé plutôt que facturé au "
            "tarif d'un modèle au nom voisin. Ajoutez la ligne dans "
            "model_pricing (migration Alembic), ou un alias explicite vers "
            "un tarif versionné."
        )

    def _get_tier_config(self, tier_name: str) -> Optional[TierConfig]:
        return self.db.query(TierConfig).filter_by(tier_name=tier_name).first()

    def _daily_used_credits(self, user_id: int) -> int:
        """Crédits du jour (UTC) : débits réglés + réservations en cours."""
        start = _start_of_day_utc()
        result = (
            self.db.query(func.coalesce(func.sum(CreditTransaction.credits_consumed), 0))
            .filter(
                CreditTransaction.user_id == user_id,
                CreditTransaction.transaction_type.in_(LEDGER_DEBIT_TYPES),
                CreditTransaction.created_at >= start,
            )
            .scalar()
        )
        return int(result or 0)
