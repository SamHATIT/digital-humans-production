"""Jetons du cache Anthropic : comptes dans le cout et persistes (15/11/2026).

`usage.input_tokens` exclut les jetons lus/ecrits en cache : ils etaient
absents du cout USD et de toute table, le gain du cache etait invisible.
"""
from app.services.llm_router_service import LLMRouterService


def _routeur():
    r = LLMRouterService.__new__(LLMRouterService)
    r._resoudre_tarif = lambda provider: {"input": 3.0, "output": 15.0}
    return r


def test_le_cout_compte_lecture_et_ecriture_du_cache():
    r = _routeur()
    sans = r._calculate_cost("anthropic/claude-sonnet", 1000, 0)
    avec = r._calculate_cost("anthropic/claude-sonnet", 1000, 0, cache_read=100_000, cache_create=10_000)
    # 1000 + 10000*1,25 + 100000*0,10 = 23 500 jetons d'entree equivalents a 3 $/M
    assert round(avec, 6) == round(23_500 / 1_000_000 * 3.0, 6)
    assert avec > sans


def test_controle_negatif_sans_cache_le_cout_est_inchange():
    r = _routeur()
    assert r._calculate_cost("anthropic/claude-sonnet", 2000, 500) == round(2000 / 1e6 * 3 + 500 / 1e6 * 15, 6)


def test_le_reglement_persiste_les_jetons_du_cache(db_session):
    from app.models.credit import CreditBalance, CreditTransaction, ModelPricing, TierConfig
    from app.models.user import User
    from app.services.credit_service import CreditService
    u = User(email="cache@example.com", name="C", hashed_password="x", subscription_tier="pro")
    db_session.add_all([u, TierConfig(tier_name="pro", monthly_credits=15000, daily_credits_cap=None,
                                      price_eur_monthly=79, description="pro"),
                        ModelPricing(model_name="claude-sonnet-5-5", credits_per_1k_input=1.0,
                                     credits_per_1k_output=5.0, allowed_tiers="pro,team",
                                     requires_opt_in=False, is_active=True)])
    db_session.commit()
    service = CreditService(db_session)
    resa = service.reserve(user_id=u.id, model="claude-sonnet-5-5", max_tokens=1000)
    tx = service.settle(reservation_id=resa.id, tokens_in=500, tokens_out=200, model="claude-sonnet-5-5",
                        cache_read_tokens=40_000, cache_creation_tokens=3_000)
    lu = db_session.get(CreditTransaction, tx.id)
    assert lu.cache_read_tokens == 40_000 and lu.cache_creation_tokens == 3_000
