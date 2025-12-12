"""
Subscription API Routes - Section 9
Endpoints for subscription management and feature access.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.user import User
from app.models.subscription import (
    SubscriptionTier,
    TIER_FEATURES,
    get_tier_config,
    compare_tiers
)
from app.utils.feature_access import (
    get_user_tier_info,
    get_locked_features,
    check_project_limits,
    check_feature_access
)

router = APIRouter()


@router.get("/tiers")
async def get_all_tiers():
    """
    Get all subscription tiers and their features.
    Public endpoint for pricing page.
    """
    tiers = []
    for tier in SubscriptionTier:
        config = get_tier_config(tier)
        tiers.append({
            "tier": tier.value,
            "name": config["name"],
            "price": config["price"],
            "price_display": config["price_display"],
            "features": config["features"],
            "limitations": config["limitations"]
        })
    
    return {"tiers": tiers}


@router.get("/compare")
async def compare_subscription_tiers():
    """
    Get feature comparison table across all tiers.
    """
    return {"comparison": compare_tiers()}


@router.get("/my-subscription")
async def get_my_subscription(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's subscription information.
    """
    tier_info = get_user_tier_info(current_user)
    limits = check_project_limits(current_user)
    locked = get_locked_features(current_user)
    
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        **tier_info,
        "project_limits": limits,
        "locked_features": locked,
        "subscription_started_at": current_user.subscription_started_at,
        "subscription_expires_at": current_user.subscription_expires_at
    }


@router.get("/check-feature/{feature_name}")
async def check_feature(
    feature_name: str,
    current_user: User = Depends(get_current_user)
):
    """
    Check if user has access to a specific feature.
    """
    return check_feature_access(current_user, feature_name)


@router.get("/can-create-project")
async def can_create_project(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if user can create a new project (within limits).
    """
    limits = check_project_limits(current_user, db)
    return limits


@router.post("/upgrade-to/{tier}")
async def request_upgrade(
    tier: str,
    current_user: User = Depends(get_current_user)
):
    """
    Request upgrade to a higher tier.
    In a real implementation, this would integrate with Stripe.
    """
    try:
        target_tier = SubscriptionTier(tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {tier}")
    
    current_tier = current_user.tier
    
    if target_tier == current_tier:
        return {"message": "Already on this tier", "success": False}
    
    # In a real implementation, this would:
    # 1. Create a Stripe checkout session
    # 2. Return the checkout URL
    # For now, just return info
    
    target_config = get_tier_config(target_tier)
    
    return {
        "message": "Upgrade request received",
        "current_tier": current_tier.value,
        "target_tier": target_tier.value,
        "target_price": target_config["price_display"],
        "checkout_url": "/pricing",  # Would be Stripe URL
        "success": True
    }
