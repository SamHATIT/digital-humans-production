"""B2 (03/09/2026) — le Free sur Nemotron local, tarifé (D2, D6, D12).

Depuis B1 le préflight de crédits ne saute plus. Sans ligne `model_pricing`
pour le modèle local, tout appel Free levait `UnknownModelError` : le tier
Free ne répondait plus. Ces tests couvrent :
- le routage : sous le profil cloud, `tier_overrides.free` force Nemotron pour
  l orchestrateur ET les ouvriers (worker_default, nouveau) ;
- la facturation : la ligne que pose la migration 014 permet de facturer un
  Free à 0,2 / 1,0 crédit pour 1 000 jetons ;
- le contrôle négatif : sans cette ligne, `UnknownModelError`, comme avant.
"""
import pytest
import yaml
from pathlib import Path

from tests.test_credit_service import seeded_db, _create_user  # noqa: F401
from app.models.credit import ModelPricing
from app.services.credit_service import CreditService, UnknownModelError
from app.services.llm_router_service import LLMRouterService, LLMRequest


def _routeur_cloud():
    r = LLMRouterService.__new__(LLMRouterService)
    r.config = yaml.safe_load(Path("config/llm_routing.yaml").read_text(encoding="utf-8"))
    r.profile = "cloud"
    return r


def test_free_orchestrateur_route_sur_nemotron():
    r = _routeur_cloud()
    req = LLMRequest(prompt="x", subscription_tier="free", agent_type="sophie", user_id=1)
    assert r._select_provider(req) == "gpu_nemotron/nemotron"


def test_free_ouvrier_route_sur_nemotron():
    """worker_default : sans lui, les ouvriers Free partaient en Sonnet (refusé au Free)."""
    r = _routeur_cloud()
    req = LLMRequest(prompt="x", subscription_tier="free", agent_type="diego", user_id=1)
    assert r._select_provider(req) == "gpu_nemotron/nemotron"


def test_pro_marcus_garde_son_mapping_standard():
    """Contrôle négatif : le Pro n est pas touché, Marcus reste hors override."""
    r = _routeur_cloud()
    req = LLMRequest(prompt="x", subscription_tier="pro", agent_type="marcus", user_id=1)
    assert r._select_provider(req) != "gpu_nemotron/nemotron"


def _poser_ligne_014(db):
    """Même ligne que la migration 014."""
    db.add(ModelPricing(model_name="nemotron-lightning", credits_per_1k_input=0.2,
                        credits_per_1k_output=1.0, allowed_tiers="free,pro,team",
                        requires_opt_in=False, is_active=True))
    db.commit()


def test_free_sur_nemotron_est_facture(seeded_db):
    _poser_ligne_014(seeded_db)
    user = _create_user(seeded_db, "free@example.com", tier="free")
    service = CreditService(seeded_db)
    service.preflight(user.id, "nemotron-lightning", 2000)
    tx = service.charge(user.id, "nemotron-lightning", tokens_in=5000, tokens_out=1000)
    # 5 * 0.2 + 1 * 1.0 = 2 crédits
    assert tx.credits_consumed == 2
    assert service.get_balance(user.id)["used_credits"] == 2


def test_sans_ligne_014_le_free_est_refuse(seeded_db):
    """Contrôle négatif : c est l état d avant la migration — le défaut mesuré par B1."""
    user = _create_user(seeded_db, "free2@example.com", tier="free")
    with pytest.raises(UnknownModelError):
        CreditService(seeded_db).preflight(user.id, "nemotron-lightning", 2000)


def test_yaml_free_ne_pointe_plus_sonnet():
    cfg = yaml.safe_load(Path("config/llm_routing.yaml").read_text(encoding="utf-8"))
    free = cfg["profiles"]["cloud"]["tier_overrides"]["free"]
    assert free["orchestrator_default"] == "gpu_nemotron/nemotron"
    assert free["worker_default"] == "gpu_nemotron/nemotron"
