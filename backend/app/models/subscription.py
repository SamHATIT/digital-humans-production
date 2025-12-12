"""
Subscription Model - Section 9 Modèle Freemium
Defines subscription tiers and their features for B2B clients.
"""
import enum
from typing import Dict, Any, List, Optional


class SubscriptionTier(str, enum.Enum):
    """Subscription tiers for Digital Humans platform."""
    FREE = "free"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


# Feature configuration per tier
TIER_FEATURES: Dict[SubscriptionTier, Dict[str, Any]] = {
    SubscriptionTier.FREE: {
        "name": "Free - SDS Generator",
        "price": 0,
        "price_display": "Gratuit",
        "features": {
            # SDS Phase - Available
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # Limits
            "max_brs_per_project": 30,
            "max_ucs_per_project": 150,
            "max_projects": 3,
            # BUILD Phase - Not available
            "build_phase": False,
            "sfdx_deployment": False,
            "git_integration": False,
            "multi_environment": False,
            # Advanced features - Not available
            "custom_templates": False,
            "priority_support": False,
            "api_access": False,
        },
        "limitations": [
            "SDS document generation only",
            "No code generation",
            "No deployment",
            "Max 3 projects",
            "Max 30 BRs per project"
        ]
    },
    SubscriptionTier.PREMIUM: {
        "name": "Premium - Full Automation",
        "price": 99,
        "price_display": "99€/mois",
        "features": {
            # SDS Phase
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # Limits
            "max_brs_per_project": 100,
            "max_ucs_per_project": 500,
            "max_projects": 20,
            # BUILD Phase - Available
            "build_phase": True,
            "sfdx_deployment": True,
            "git_integration": True,
            "multi_environment": True,
            # Advanced features
            "custom_templates": False,
            "priority_support": True,
            "api_access": False,
        },
        "limitations": [
            "Standard templates only",
            "Max 20 projects",
            "Max 100 BRs per project"
        ]
    },
    SubscriptionTier.ENTERPRISE: {
        "name": "Enterprise - Custom Solution",
        "price": None,
        "price_display": "Sur devis",
        "features": {
            # SDS Phase
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # Limits - Unlimited
            "max_brs_per_project": None,  # None = unlimited
            "max_ucs_per_project": None,
            "max_projects": None,
            # BUILD Phase
            "build_phase": True,
            "sfdx_deployment": True,
            "git_integration": True,
            "multi_environment": True,
            # Advanced features - All available
            "custom_templates": True,
            "priority_support": True,
            "dedicated_support": True,
            "custom_agents": True,
            "api_access": True,
            "sso_integration": True,
            "audit_logs": True,
            "white_label": True,
        },
        "limitations": []
    }
}


def get_tier_config(tier: SubscriptionTier) -> Dict[str, Any]:
    """Get full configuration for a tier."""
    return TIER_FEATURES.get(tier, TIER_FEATURES[SubscriptionTier.FREE])


def get_tier_features(tier: SubscriptionTier) -> Dict[str, Any]:
    """Get features dict for a tier."""
    return get_tier_config(tier).get("features", {})


def has_feature(tier: SubscriptionTier, feature_name: str) -> bool:
    """Check if a tier has access to a specific feature."""
    features = get_tier_features(tier)
    return features.get(feature_name, False) is True


def get_limit(tier: SubscriptionTier, limit_name: str) -> Optional[int]:
    """Get a numeric limit for a tier. Returns None if unlimited."""
    features = get_tier_features(tier)
    return features.get(limit_name)


def get_required_tier(feature_name: str) -> Optional[SubscriptionTier]:
    """Get the minimum tier required for a feature."""
    for tier in [SubscriptionTier.FREE, SubscriptionTier.PREMIUM, SubscriptionTier.ENTERPRISE]:
        if has_feature(tier, feature_name):
            return tier
    return None


def get_all_features() -> List[str]:
    """Get list of all feature names."""
    all_features = set()
    for tier_config in TIER_FEATURES.values():
        all_features.update(tier_config.get("features", {}).keys())
    return sorted(list(all_features))


def compare_tiers() -> Dict[str, Dict[str, Any]]:
    """Generate a comparison table of all tiers."""
    all_features = get_all_features()
    comparison = {}
    
    for feature in all_features:
        comparison[feature] = {
            tier.value: get_tier_features(tier).get(feature, False)
            for tier in SubscriptionTier
        }
    
    return comparison


# Test
if __name__ == "__main__":
    print("Subscription Tiers Configuration")
    print("=" * 50)
    
    for tier in SubscriptionTier:
        config = get_tier_config(tier)
        print(f"\n{config['name']} ({config['price_display']})")
        print(f"  Max projects: {get_limit(tier, 'max_projects')}")
        print(f"  Max BRs: {get_limit(tier, 'max_brs_per_project')}")
        print(f"  BUILD phase: {has_feature(tier, 'build_phase')}")
        print(f"  Git integration: {has_feature(tier, 'git_integration')}")
    
    print("\n✅ Subscription model loaded")
