"""
Subscription Model — 4-tier freemium model (Free / Pro / Team / Enterprise).

Source : MASTER_PLAN_V4 §1 D3-D4 + DH_brief_consolide §6.
Périmètres validés par Sam les 26 + 29 avril 2026.

Tier scopes
-----------
FREE        — Sophie + Olivia chat seul. Pas d'upload, pas de mémoire.
              Modèle Haiku uniquement. Vitrine + qualification prospect.
PRO   49€   — Équipe complète, upload, mémoire persistante.
              Livrable final = SDS (BR + UC + Solution Design + document Word/PDF).
              PAS de BUILD (pas de génération de code), PAS de déploiement.
              Modèles Haiku + Sonnet. Pas d'Opus.
TEAM 1490€  — Pipeline complet jusqu'à sandbox.
              SDS + BUILD (Apex, LWC, Admin) + déploiement SFDX vers sandbox.
              PAS de mise en production (raison de sécurité, validé Sam 29 avril).
              Modèles Haiku + Sonnet + Opus opt-in.
ENTERPRISE  — On-premise, sur devis.
              Tout TEAM + déploiement prod négocié au contrat.
              Choix du LLM (Claude/GPT/Mistral), customisation, SSO, audit logs.

Migration historique
-------------------
L'ancien modèle 3-tier était : free / premium / enterprise (premium 99€ avec BUILD).
Mapping appliqué dans la migration 009 :
  - 'premium'    → 'team'        (BUILD était dans premium → reste dans team)
  - 'enterprise' (old SaaS) → 'team' (sauf si contrat on-premise existant)
"""
import enum
from typing import Dict, Any, List, Optional


class SubscriptionTier(str, enum.Enum):
    """Subscription tiers for Digital Humans platform (4-tier model)."""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


# Feature configuration per tier
# Naming convention : snake_case feature flags. Order matters for `compare_tiers`.
TIER_FEATURES: Dict[SubscriptionTier, Dict[str, Any]] = {
    SubscriptionTier.FREE: {
        "name": "Free",
        "tagline": "Discover the studio",
        "price": 0,
        "price_display": "Gratuit",
        "billing_period": None,
        "features": {
            # Chat scope
            "chat_sophie": True,
            "chat_olivia": True,
            "chat_full_team": False,
            # Inputs
            "upload_documents": False,
            "persistent_memory": False,
            # SDS pipeline
            "br_extraction": False,
            "uc_generation": False,
            "solution_design": False,
            "sds_document": False,
            "export_word": False,
            "export_pdf": False,
            # BUILD pipeline
            "build_phase": False,
            "sfdx_deployment": False,
            "git_integration": False,
            "multi_environment": False,
            "deploy_to_production": False,
            # LLM access
            "llm_haiku": True,
            "llm_sonnet": False,
            "llm_opus": False,
            # Limits
            "max_brs_per_project": 0,
            "max_ucs_per_project": 0,
            "max_projects": 0,
            # Advanced
            "custom_templates": False,
            "priority_support": False,
            "api_access": False,
            "sso_integration": False,
            "audit_logs": False,
            "white_label": False,
            "on_premise": False,
        },
        "limitations": [
            "Chat avec Sophie et Olivia uniquement",
            "Pas d'upload de fichiers",
            "Pas de mémoire persistante (sessions stateless)",
            "Modèle Haiku uniquement",
        ],
    },
    SubscriptionTier.PRO: {
        "name": "Pro",
        "tagline": "Du brief au SDS",
        "price": 49,
        "price_display": "49 €/mois",
        "billing_period": "monthly",
        "features": {
            # Chat scope
            "chat_sophie": True,
            "chat_olivia": True,
            "chat_full_team": True,
            # Inputs
            "upload_documents": True,
            "persistent_memory": True,
            # SDS pipeline — livrable final = SDS
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # BUILD pipeline — non inclus en Pro
            "build_phase": False,
            "sfdx_deployment": False,
            "git_integration": False,
            "multi_environment": False,
            "deploy_to_production": False,
            # LLM access
            "llm_haiku": True,
            "llm_sonnet": True,
            "llm_opus": False,
            # Limits
            "max_brs_per_project": 100,
            "max_ucs_per_project": 500,
            "max_projects": 20,
            # Advanced
            "custom_templates": False,
            "priority_support": True,
            "api_access": False,
            "sso_integration": False,
            "audit_logs": False,
            "white_label": False,
            "on_premise": False,
        },
        "limitations": [
            "Pas de génération de code (BUILD)",
            "Pas de déploiement Salesforce",
            "Modèle Opus indisponible",
            "Maximum 20 projets",
        ],
    },
    SubscriptionTier.TEAM: {
        "name": "Team",
        "tagline": "Pocket team pour évolutions continues",
        "price": 1490,
        "price_display": "1 490 €/mois",
        "billing_period": "monthly",
        "features": {
            # Chat scope
            "chat_sophie": True,
            "chat_olivia": True,
            "chat_full_team": True,
            # Inputs
            "upload_documents": True,
            "persistent_memory": True,
            # SDS pipeline
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # BUILD pipeline — inclus jusqu'à sandbox
            "build_phase": True,
            "sfdx_deployment": True,
            "git_integration": True,
            "multi_environment": True,
            "deploy_to_production": False,    # Sécurité : sandbox uniquement
            # LLM access
            "llm_haiku": True,
            "llm_sonnet": True,
            "llm_opus": True,                 # Opt-in côté UI
            # Limits
            "max_brs_per_project": 500,
            "max_ucs_per_project": 2500,
            "max_projects": 100,
            # Advanced
            "custom_templates": False,
            "priority_support": True,
            "api_access": False,
            "sso_integration": False,
            "audit_logs": True,
            "white_label": False,
            "on_premise": False,
        },
        "limitations": [
            "Déploiement limité aux sandboxes (pas de production)",
            "Opus en opt-in (coût supplémentaire affiché avant envoi)",
            "Pas d'API publique",
        ],
    },
    SubscriptionTier.ENTERPRISE: {
        "name": "Enterprise",
        "tagline": "On-premise, sur mesure",
        "price": None,
        "price_display": "Sur devis",
        "billing_period": "annual",
        "features": {
            # Chat scope
            "chat_sophie": True,
            "chat_olivia": True,
            "chat_full_team": True,
            # Inputs
            "upload_documents": True,
            "persistent_memory": True,
            # SDS pipeline
            "br_extraction": True,
            "uc_generation": True,
            "solution_design": True,
            "sds_document": True,
            "export_word": True,
            "export_pdf": True,
            # BUILD pipeline — peut aller jusqu'en prod (négocié)
            "build_phase": True,
            "sfdx_deployment": True,
            "git_integration": True,
            "multi_environment": True,
            "deploy_to_production": True,     # Négocié au contrat
            # LLM access (choix client)
            "llm_haiku": True,
            "llm_sonnet": True,
            "llm_opus": True,
            # Limits — illimité
            "max_brs_per_project": None,
            "max_ucs_per_project": None,
            "max_projects": None,
            # Advanced — tout disponible
            "custom_templates": True,
            "priority_support": True,
            "dedicated_support": True,
            "custom_agents": True,
            "api_access": True,
            "sso_integration": True,
            "audit_logs": True,
            "white_label": True,
            "on_premise": True,
        },
        "limitations": [],
    },
}


# Tier ordering (low → high) — used by `get_required_tier` and comparison views
TIER_ORDER: List[SubscriptionTier] = [
    SubscriptionTier.FREE,
    SubscriptionTier.PRO,
    SubscriptionTier.TEAM,
    SubscriptionTier.ENTERPRISE,
]


def get_tier_config(tier: SubscriptionTier) -> Dict[str, Any]:
    """Get full configuration for a tier."""
    return TIER_FEATURES.get(tier, TIER_FEATURES[SubscriptionTier.FREE])


def get_tier_features(tier: SubscriptionTier) -> Dict[str, Any]:
    """Get features dict for a tier."""
    return get_tier_config(tier).get("features", {})


def has_feature(tier: SubscriptionTier, feature_name: str) -> bool:
    """Check if a tier has access to a specific feature.

    A feature is granted when its value is truthy *and* not a numeric limit
    of 0 (which means 'no quota' rather than 'feature available').
    """
    features = get_tier_features(tier)
    if feature_name not in features:
        return False
    value = features[feature_name]
    # Numeric limits of 0 mean 'no allowance', not 'feature granted'
    if isinstance(value, int) and not isinstance(value, bool):
        return value != 0
    return bool(value)


def get_limit(tier: SubscriptionTier, limit_name: str) -> Optional[int]:
    """Get a numeric limit for a tier. Returns None if unlimited."""
    features = get_tier_features(tier)
    return features.get(limit_name)


def get_required_tier(feature_name: str) -> Optional[SubscriptionTier]:
    """Get the minimum tier required for a feature (low → high lookup)."""
    for tier in TIER_ORDER:
        if has_feature(tier, feature_name):
            return tier
    return None


def get_all_features() -> List[str]:
    """Get list of all feature names."""
    all_features: set = set()
    for tier_config in TIER_FEATURES.values():
        all_features.update(tier_config.get("features", {}).keys())
    return sorted(list(all_features))


def compare_tiers() -> Dict[str, Dict[str, Any]]:
    """Generate a comparison table of all tiers (feature → tier → value)."""
    all_features = get_all_features()
    return {
        feature: {
            tier.value: get_tier_features(tier).get(feature, False)
            for tier in TIER_ORDER
        }
        for feature in all_features
    }


# Smoke test
if __name__ == "__main__":
    print("Subscription Tiers Configuration (4-tier model)")
    print("=" * 60)

    for tier in TIER_ORDER:
        config = get_tier_config(tier)
        print(f"\n{config['name']:12} {config['price_display']:15} — {config['tagline']}")
        print(f"  Full team chat   : {has_feature(tier, 'chat_full_team')}")
        print(f"  Upload + memory  : {has_feature(tier, 'upload_documents')} / {has_feature(tier, 'persistent_memory')}")
        print(f"  SDS deliverable  : {has_feature(tier, 'sds_document')}")
        print(f"  BUILD phase      : {has_feature(tier, 'build_phase')}")
        print(f"  Deploy to prod   : {has_feature(tier, 'deploy_to_production')}")
        print(f"  LLM access       : haiku={has_feature(tier, 'llm_haiku')} sonnet={has_feature(tier, 'llm_sonnet')} opus={has_feature(tier, 'llm_opus')}")
        max_proj = get_limit(tier, "max_projects")
        print(f"  Max projects     : {'∞' if max_proj is None else max_proj}")

    print("\n✅ Subscription model loaded — 4 tiers")
