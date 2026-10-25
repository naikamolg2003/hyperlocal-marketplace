"""
Freemium Subscription Enforcement and Broadcast Access Control.

Enforces the Rs. 1,000 monthly platform fee rule:
1. Sellers have a subscription_status in ('trial', 'active', 'expired').
2. completed_orders_count tracks total fulfilled orders.
3. If completed_orders_count > 2 and subscription_status != 'active', access is restricted
   when attempting to view or respond to customer requirement broadcasts,
   requiring the Rs. 1,000 monthly platform fee payment to continue.
"""

from typing import Optional, Tuple, Union
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import SubscriptionStatus, User, UserRole

SUBSCRIPTION_FEE_AMOUNT = 1000.0

SUBSCRIPTION_RESTRICTION_MESSAGE = (
    "Access restricted: Completed order count exceeds trial limit (completed_orders_count > 2) "
    "and subscription_status != 'active'. "
    "Please pay the Rs. 1,000 monthly platform fee payment to continue."
)

EXPIRED_TRIAL_MESSAGE = (
    "Access restricted: Free trial has expired. "
    "Please pay the Rs. 1,000 monthly platform fee payment to continue."
)


def check_seller_subscription_access(seller: User) -> Tuple[bool, str]:
    """
    Evaluates whether a seller is eligible to view or respond to customer requirement broadcasts.

    Returns:
        (is_allowed: bool, message: str)
    """
    if seller.role != UserRole.SELLER:
        return True, "User is not a seller."

    status_str = str(seller.subscription_status).lower() if seller.subscription_status else "trial"
    completed = seller.completed_orders_count or 0

    # 1. Active or Subscribed merchants
    if status_str in ("active", "subscribed"):
        from datetime import datetime, timezone

        if seller.subscription_expires_at and seller.subscription_expires_at < datetime.now(timezone.utc):
            return (
                False,
                "Your subscription has expired. Please pay the Rs. 1,000 monthly platform fee payment to continue.",
            )
        return True, "Subscription is active."

    # 2. Freemium Rule: If completed_orders_count > 2 and subscription_status != 'active', restrict access
    if completed > 2 and status_str != "active":
        return False, SUBSCRIPTION_RESTRICTION_MESSAGE

    # 3. Explicitly expired or pending payment states
    if status_str in ("expired", "pending_payment", "trial_expired"):
        return False, EXPIRED_TRIAL_MESSAGE

    # 4. Active trial within allowed quota (<= 2 completed orders)
    return True, f"Trial active. {max(0, 2 - completed)} free orders remaining."


def enforce_seller_broadcast_access(
    seller_or_id: Union[User, UUID], db: Session
) -> User:
    """
    Helper function enforcing the Rs. 1,000 freemium subscription rule.
    If completed_orders_count > 2 and subscription_status != 'active',
    raises HTTP 403 Forbidden requiring the platform fee payment to continue.
    """
    if isinstance(seller_or_id, User):
        seller = seller_or_id
    else:
        seller = crud.get_user(db, seller_or_id)
        if not seller:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Seller with ID '{seller_or_id}' not found.",
            )

    if seller.role != UserRole.SELLER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.",
        )

    allowed, message = check_seller_subscription_access(seller)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=message,
        )

    return seller


def require_seller_broadcast_access(
    seller_id: UUID = Query(..., description="UUID of quoting or querying merchant"),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI Dependency enforcing seller broadcast eligibility."""
    return enforce_seller_broadcast_access(seller_id, db)
