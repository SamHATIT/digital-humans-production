"""
Feature Access Control - Section 9.2
Decorators and utilities to control access based on subscription tier.
"""
from functools import wraps
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from app.models.subscription import (
    SubscriptionTier,
    TIER_FEATURES,
    get_tier_features,
    has_feature,
    get_limit,
    get_required_tier
)


class FeatureAccessError(HTTPException):
    """Exception raised when user doesn't have access to a feature."""
    
    def __init__(self, feature_name: str, required_tier: SubscriptionTier):
        super().__init__(
            status_code=403,
            detail={
                "error": "feature_not_available",
                "feature": feature_name,
                "required_tier": required_tier.value,
                "message": f"La fonctionnalité '{feature_name}' nécessite un abonnement {required_tier.value.title()}",
                "upgrade_url": "/pricing"
            }
        )


class LimitExceededError(HTTPException):
    """Exception raised when user exceeds a limit."""
    
    def __init__(self, limit_name: str, current: int, limit: int, tier: SubscriptionTier):
        super().__init__(
            status_code=403,
            detail={
                "error": "limit_exceeded",
                "limit_name": limit_name,
                "current": current,
                "limit": limit,
                "tier": tier.value,
                "message": f"Limite atteinte: {current}/{limit}. Passez à un abonnement supérieur.",
                "upgrade_url": "/pricing"
            }
        )


def require_feature(feature_name: str):
    """
    Decorator to check if user has access to a feature.
    
    Usage:
        @router.post("/build/start")
        @require_feature("build_phase")
        async def start_build(..., current_user: User = Depends(get_current_user)):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get current user from kwargs (injected by Depends)
            current_user = kwargs.get('current_user')
            
            if not current_user:
                raise HTTPException(status_code=401, detail="Non authentifié")
            
            # Get user's tier (default to FREE)
            tier = getattr(current_user, 'subscription_tier', None)
            if tier is None:
                tier = SubscriptionTier.FREE
            elif isinstance(tier, str):
                tier = SubscriptionTier(tier)
            
            # Check feature access
            if not has_feature(tier, feature_name):
                required = get_required_tier(feature_name)
                raise FeatureAccessError(feature_name, required or SubscriptionTier.PREMIUM)
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_feature_access(user, feature_name: str) -> Dict[str, Any]:
    """
    Check if a user has access to a feature.
    Returns a dict with access info.
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    has_access = has_feature(tier, feature_name)
    required_tier = get_required_tier(feature_name)
    
    return {
        "feature": feature_name,
        "has_access": has_access,
        "user_tier": tier.value,
        "required_tier": required_tier.value if required_tier else None,
        "upgrade_needed": not has_access
    }


def check_project_limits(user, db: Session = None) -> Dict[str, Any]:
    """
    Check if user has reached their project limits.
    
    Returns:
        {
            "allowed": True/False,
            "reason": str (if not allowed),
            "current": int,
            "limit": int or None
        }
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    max_projects = get_limit(tier, "max_projects")
    
    # If unlimited (None), always allowed
    if max_projects is None:
        return {"allowed": True, "current": 0, "limit": None}
    
    # Count existing projects
    # Note: This requires the user to have a projects relationship
    current_projects = len(getattr(user, 'projects', [])) if hasattr(user, 'projects') else 0
    
    if current_projects >= max_projects:
        return {
            "allowed": False,
            "reason": f"Limite de projets atteinte ({max_projects}). Passez à un abonnement supérieur.",
            "current": current_projects,
            "limit": max_projects,
            "tier": tier.value
        }
    
    return {
        "allowed": True,
        "current": current_projects,
        "limit": max_projects,
        "remaining": max_projects - current_projects
    }


def check_br_limit(user, project, new_br_count: int = 1) -> Dict[str, Any]:
    """
    Check if adding BRs would exceed limit.
    
    Args:
        user: Current user
        project: Project to check
        new_br_count: Number of BRs to add
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    max_brs = get_limit(tier, "max_brs_per_project")
    
    # If unlimited, always allowed
    if max_brs is None:
        return {"allowed": True, "limit": None}
    
    # Count current BRs
    current_brs = len(getattr(project, 'business_requirements', [])) if hasattr(project, 'business_requirements') else 0
    
    if current_brs + new_br_count > max_brs:
        return {
            "allowed": False,
            "reason": f"Limite de BRs dépassée ({max_brs}). Actuel: {current_brs}, Ajout: {new_br_count}",
            "current": current_brs,
            "adding": new_br_count,
            "limit": max_brs,
            "tier": tier.value
        }
    
    return {
        "allowed": True,
        "current": current_brs,
        "limit": max_brs,
        "remaining": max_brs - current_brs
    }


def check_uc_limit(user, project, new_uc_count: int = 1) -> Dict[str, Any]:
    """
    Check if adding UCs would exceed limit.
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    max_ucs = get_limit(tier, "max_ucs_per_project")
    
    if max_ucs is None:
        return {"allowed": True, "limit": None}
    
    # This would need to query the database for actual UC count
    # For now, return allowed
    return {"allowed": True, "limit": max_ucs}


def get_user_tier_info(user) -> Dict[str, Any]:
    """
    Get complete tier information for a user.
    Useful for frontend to show what features are available.
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    tier_config = TIER_FEATURES.get(tier, TIER_FEATURES[SubscriptionTier.FREE])
    
    return {
        "tier": tier.value,
        "name": tier_config["name"],
        "price_display": tier_config["price_display"],
        "features": tier_config["features"],
        "limitations": tier_config["limitations"],
        "can_upgrade": tier != SubscriptionTier.ENTERPRISE
    }


def get_locked_features(user) -> list:
    """
    Get list of features that are locked for the user.
    Useful for showing upgrade prompts in UI.
    """
    tier = getattr(user, 'subscription_tier', None)
    if tier is None:
        tier = SubscriptionTier.FREE
    elif isinstance(tier, str):
        tier = SubscriptionTier(tier)
    
    user_features = get_tier_features(tier)
    locked = []
    
    # Check against ENTERPRISE (all features)
    enterprise_features = get_tier_features(SubscriptionTier.ENTERPRISE)
    
    for feature, available in enterprise_features.items():
        if available is True and not user_features.get(feature, False):
            required = get_required_tier(feature)
            locked.append({
                "feature": feature,
                "required_tier": required.value if required else "premium"
            })
    
    return locked


# Test
if __name__ == "__main__":
    print("Feature Access Control")
    print("=" * 50)
    
    # Mock user
    class MockUser:
        subscription_tier = SubscriptionTier.FREE
        projects = []
    
    user = MockUser()
    
    # Test feature access
    print("\n📋 Feature access (FREE tier):")
    for feature in ["sds_document", "build_phase", "git_integration", "custom_templates"]:
        result = check_feature_access(user, feature)
        status = "✅" if result["has_access"] else "🔒"
        print(f"  {status} {feature}: {result['has_access']}")
    
    # Test limits
    print("\n📊 Project limits:")
    limits = check_project_limits(user)
    print(f"  Allowed: {limits['allowed']}, Limit: {limits['limit']}")
    
    # Test locked features
    print("\n🔒 Locked features:")
    locked = get_locked_features(user)
    for f in locked[:5]:
        print(f"  - {f['feature']} (requires {f['required_tier']})")
    
    print("\n✅ Feature access control working")
