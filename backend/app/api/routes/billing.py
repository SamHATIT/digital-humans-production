"""
Billing routes — Phase 3.1.

Two endpoints :
- GET /api/billing/balance : current credit picture for the authenticated user.
- GET /api/billing/usage   : aggregated consumption (total + breakdown + timeline).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.credit_service import CreditService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/balance")
async def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current credit balance for the authenticated user."""
    return CreditService(db).get_balance(current_user.id)


@router.get("/usage")
async def get_usage(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregated credit usage over the last ``days`` days."""
    return CreditService(db).get_usage(current_user.id, days=days)
