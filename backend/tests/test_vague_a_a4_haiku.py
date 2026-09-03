"""
Lot A4 — clé `llm_haiku` morte.

Décision Sam D5 (docs/vague-a/DECISIONS_SAM.md) : « Haiku : aucun tier,
aucune clé `llm_haiku` ». Aucun modèle Haiku n'est servi par la plateforme ;
la clé de feature `llm_haiku` ne doit donc apparaître nulle part dans
`TIER_FEATURES`, et `has_feature` doit renvoyer False pour elle sur tous les
paliers (puisque la clé n'existe plus).
"""
import pytest

from app.models.subscription import (
    SubscriptionTier,
    TIER_FEATURES,
    has_feature,
)


@pytest.mark.parametrize("tier", list(SubscriptionTier))
def test_has_feature_llm_haiku_is_false_for_every_tier(tier):
    """`llm_haiku` n'est plus une clé de feature valide : False partout."""
    assert has_feature(tier, "llm_haiku") is False


def test_has_feature_llm_haiku_false_on_free_explicitly():
    """Critère de fin explicite du lot A4 (docs/vague-a/MISSION.md)."""
    assert has_feature(SubscriptionTier.FREE, "llm_haiku") is False


@pytest.mark.parametrize(
    "tier,feature",
    [
        (SubscriptionTier.PRO, "llm_sonnet"),
        (SubscriptionTier.TEAM, "llm_sonnet"),
        (SubscriptionTier.TEAM, "llm_opus"),
        (SubscriptionTier.ENTERPRISE, "llm_opus"),
    ],
)
def test_control_positif_autre_cle_llm_reste_vraie(tier, feature):
    """Contrôle négatif/positif : le retrait de llm_haiku ne doit pas
    entraîner le retrait d'autres clés LLM toujours présentes."""
    assert has_feature(tier, feature) is True


def test_aucune_cle_llm_haiku_dans_tier_features():
    """`llm_haiku` ne doit apparaître nulle part dans TIER_FEATURES,
    ni dans `features`, ni ailleurs dans le dict de configuration d'un
    palier."""
    for tier, config in TIER_FEATURES.items():
        assert "llm_haiku" not in config.get("features", {}), (
            f"llm_haiku encore present dans features de {tier}"
        )
        assert "llm_haiku" not in config, (
            f"llm_haiku encore present au niveau racine de la config de {tier}"
        )
