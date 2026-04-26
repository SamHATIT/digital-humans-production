"""
Unit tests for CreditService — Phase 3.1.

Uses the SQLite test fixtures from conftest.py. Pricing & tier_config rows
are seeded here (the seed lives in the Alembic migration, but tests run on a
freshly-created schema without migrations).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.credit import (
    CreditBalance,
    CreditTransaction,
    ModelPricing,
    TierConfig,
)
from app.models.user import User
from app.services.credit_service import (
    CreditService,
    InsufficientCreditsError,
    ModelNotAllowedError,
    UnknownModelError,
    resolve_credit_tier,
)


# ---------------------------------------------------------------------------
# Helpers — seeded fixtures
# ---------------------------------------------------------------------------


def _seed_tiers(db) -> None:
    db.add_all(
        [
            TierConfig(
                tier_name="free",
                monthly_credits=0,
                daily_credits_cap=300,
                price_eur_monthly=0,
                description="free",
            ),
            TierConfig(
                tier_name="pro",
                monthly_credits=2000,
                daily_credits_cap=None,
                price_eur_monthly=49,
                description="pro",
            ),
            TierConfig(
                tier_name="team",
                monthly_credits=100000,
                daily_credits_cap=None,
                price_eur_monthly=1490,
                description="team",
            ),
        ]
    )
    db.commit()


def _seed_pricing(db) -> None:
    db.add_all(
        [
            ModelPricing(
                model_name="claude-haiku-4-5",
                credits_per_1k_input=0.300,
                credits_per_1k_output=1.500,
                allowed_tiers="free,pro,team",
                requires_opt_in=False,
                is_active=True,
            ),
            ModelPricing(
                model_name="claude-sonnet-4-6",
                credits_per_1k_input=1.000,
                credits_per_1k_output=5.000,
                allowed_tiers="pro,team",
                requires_opt_in=False,
                is_active=True,
            ),
            ModelPricing(
                model_name="claude-opus-4-7",
                credits_per_1k_input=5.000,
                credits_per_1k_output=25.000,
                allowed_tiers="team",
                requires_opt_in=True,
                is_active=True,
            ),
        ]
    )
    db.commit()


def _create_user(db, email: str, tier: str = "free") -> User:
    user = User(
        email=email,
        name=email.split("@")[0],
        hashed_password="x",
        is_active=True,
        subscription_tier=tier,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def seeded_db(db_session):
    _seed_tiers(db_session)
    _seed_pricing(db_session)
    return db_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resolve_credit_tier_maps_legacy_premium_to_pro(seeded_db):
    user = _create_user(seeded_db, "premium@example.com", tier="premium")
    assert resolve_credit_tier(user) == "pro"


def test_resolve_credit_tier_maps_enterprise_to_team(seeded_db):
    user = _create_user(seeded_db, "ent@example.com", tier="enterprise")
    assert resolve_credit_tier(user) == "team"


def test_charge_sonnet_pro_user_ok(seeded_db):
    user = _create_user(seeded_db, "pro@example.com", tier="premium")
    service = CreditService(seeded_db)
    tx = service.charge(user.id, "claude-sonnet-4-6", tokens_in=2000, tokens_out=1000)
    # 2 * 1.0 + 1 * 5.0 = 7 credits
    assert tx.credits_consumed == 7
    balance = service.get_balance(user.id)
    assert balance["used_credits"] == 7
    assert balance["available"] == 2000 - 7


def test_charge_opus_free_user_raises_model_not_allowed(seeded_db):
    user = _create_user(seeded_db, "free@example.com", tier="free")
    service = CreditService(seeded_db)
    with pytest.raises(ModelNotAllowedError):
        service.charge(user.id, "claude-opus-4-7", tokens_in=1000, tokens_out=1000)


def test_charge_sonnet_free_user_raises_model_not_allowed(seeded_db):
    user = _create_user(seeded_db, "free@example.com", tier="free")
    service = CreditService(seeded_db)
    with pytest.raises(ModelNotAllowedError):
        service.charge(user.id, "claude-sonnet-4-6", tokens_in=500, tokens_out=500)


def test_charge_insufficient_credits_raises(seeded_db):
    user = _create_user(seeded_db, "lowbal@example.com", tier="premium")
    service = CreditService(seeded_db)
    # Drain the balance to almost 0
    balance = service._ensure_balance(user.id)
    balance.included_credits = 5
    seeded_db.commit()
    with pytest.raises(InsufficientCreditsError):
        service.charge(user.id, "claude-sonnet-4-6", tokens_in=10000, tokens_out=1000)


def test_charge_increments_used_credits(seeded_db):
    user = _create_user(seeded_db, "incr@example.com", tier="premium")
    service = CreditService(seeded_db)
    service.charge(user.id, "claude-sonnet-4-6", tokens_in=1000, tokens_out=1000)
    service.charge(user.id, "claude-sonnet-4-6", tokens_in=1000, tokens_out=1000)
    balance = seeded_db.query(CreditBalance).filter_by(user_id=user.id).one()
    # 1*1 + 1*5 = 6 credits each → 12 total
    assert balance.used_credits == 12


def test_charge_logs_transaction(seeded_db):
    user = _create_user(seeded_db, "log@example.com", tier="premium")
    service = CreditService(seeded_db)
    tx = service.charge(
        user.id,
        "claude-sonnet-4-6",
        tokens_in=500,
        tokens_out=500,
        execution_id=None,
        project_id=None,
        note="unit test",
    )
    rows = seeded_db.query(CreditTransaction).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].id == tx.id
    assert rows[0].transaction_type == "charge"
    assert rows[0].model_used == "claude-sonnet-4-6"
    assert rows[0].tokens_input == 500
    assert rows[0].tokens_output == 500
    assert rows[0].note == "unit test"


def test_get_balance_lazy_create(seeded_db):
    user = _create_user(seeded_db, "lazy@example.com", tier="premium")
    service = CreditService(seeded_db)
    assert seeded_db.query(CreditBalance).filter_by(user_id=user.id).first() is None
    snapshot = service.get_balance(user.id)
    assert snapshot["included_credits"] == 2000  # pro monthly
    assert snapshot["used_credits"] == 0
    assert snapshot["available"] == 2000
    # Balance row was created
    assert seeded_db.query(CreditBalance).filter_by(user_id=user.id).first() is not None


def test_reset_monthly_resets_used_to_zero_and_refills_included(seeded_db):
    user = _create_user(seeded_db, "reset@example.com", tier="premium")
    service = CreditService(seeded_db)
    service.charge(user.id, "claude-sonnet-4-6", tokens_in=10000, tokens_out=2000)
    before = seeded_db.query(CreditBalance).filter_by(user_id=user.id).one()
    assert before.used_credits > 0

    service.reset_monthly(user.id)

    after = seeded_db.query(CreditBalance).filter_by(user_id=user.id).one()
    assert after.used_credits == 0
    assert after.included_credits == 2000  # pro tier monthly allotment


def test_pricing_calculation_haiku(seeded_db):
    user = _create_user(seeded_db, "haiku@example.com", tier="free")
    service = CreditService(seeded_db)
    # 1000 in, 1000 out → 0.3 + 1.5 = 1.8 → rounded 2 credits
    tx = service.charge(user.id, "claude-haiku-4-5", tokens_in=1000, tokens_out=1000)
    assert tx.credits_consumed == 2


def test_pricing_calculation_sonnet(seeded_db):
    user = _create_user(seeded_db, "sonnet@example.com", tier="premium")
    service = CreditService(seeded_db)
    # 5000 in, 1000 out → 5 + 5 = 10 credits
    tx = service.charge(user.id, "claude-sonnet-4-6", tokens_in=5000, tokens_out=1000)
    assert tx.credits_consumed == 10


def test_pricing_calculation_opus(seeded_db):
    user = _create_user(seeded_db, "opus@example.com", tier="enterprise")
    service = CreditService(seeded_db)
    # 1000 in, 1000 out → 5 + 25 = 30 credits
    tx = service.charge(user.id, "claude-opus-4-7", tokens_in=1000, tokens_out=1000)
    assert tx.credits_consumed == 30


def test_substring_fallback_resolves_provider_alias(seeded_db):
    """A model passed as 'anthropic/claude-sonnet' must still resolve."""
    user = _create_user(seeded_db, "sub@example.com", tier="premium")
    service = CreditService(seeded_db)
    tx = service.charge(user.id, "anthropic/claude-sonnet", tokens_in=1000, tokens_out=1000)
    assert tx.credits_consumed > 0
    assert tx.model_used == "claude-sonnet-4-6"


def test_unknown_model_raises(seeded_db):
    user = _create_user(seeded_db, "unk@example.com", tier="premium")
    service = CreditService(seeded_db)
    with pytest.raises(UnknownModelError):
        service.charge(user.id, "totally-fake-model", tokens_in=10, tokens_out=10)


def test_free_tier_daily_cap_enforced(seeded_db):
    user = _create_user(seeded_db, "freecap@example.com", tier="free")
    service = CreditService(seeded_db)
    # Give them enough balance to make sure the daily cap (not the balance) is what blocks.
    balance = service._ensure_balance(user.id)
    balance.overage_credits = 5000
    seeded_db.commit()

    # One huge call : 1M in / 1M out on Haiku → 300 + 1500 = 1800 credits > 300 daily cap.
    with pytest.raises(InsufficientCreditsError):
        service.charge(
            user.id, "claude-haiku-4-5", tokens_in=1_000_000, tokens_out=1_000_000
        )


def test_preflight_skips_cost_when_balance_ok(seeded_db):
    user = _create_user(seeded_db, "pre@example.com", tier="premium")
    service = CreditService(seeded_db)
    # Should not raise — pro user has 2000 credits and we're checking sonnet 4096 max_tokens.
    service.preflight(user.id, "claude-sonnet-4-6", max_tokens=2048)


def test_preflight_blocks_unauthorized_model(seeded_db):
    user = _create_user(seeded_db, "preno@example.com", tier="free")
    service = CreditService(seeded_db)
    with pytest.raises(ModelNotAllowedError):
        service.preflight(user.id, "claude-opus-4-7", max_tokens=1024)


def test_get_usage_returns_breakdown(seeded_db):
    user = _create_user(seeded_db, "usage@example.com", tier="premium")
    service = CreditService(seeded_db)
    service.charge(user.id, "claude-sonnet-4-6", tokens_in=1000, tokens_out=1000)
    service.charge(user.id, "claude-sonnet-4-6", tokens_in=2000, tokens_out=500)

    usage = service.get_usage(user.id, days=7)
    assert usage["total_credits"] >= 7
    assert "claude-sonnet-4-6" in usage["by_model"]
    assert usage["by_model"]["claude-sonnet-4-6"]["calls"] == 2
    assert len(usage["timeline"]) >= 1
