"""
Seller Freemium Billing & Order Completion Router.

Handles:
1. Seller Freemium Subscription Status (2 free orders, Rs. 1,000/month fee).
2. Automated 2-order completion trigger transitioning status to 'pending_payment'.
3. Platform fee payment processing restoring broadcast eligibility.
4. Order lifecycle fulfillment and history tracking.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import (
    OrderCompleteRequest,
    OrderCompleteResultResponse,
    OrderPaymentRequest,
    OrderPaymentSettlementResponse,
    OrderResponse,
    SellerBillingStatusResponse,
    SellerPaymentRequest,
    SellerPaymentResponse,
    SellerQuoteSubmitRequest,
)

router = APIRouter(tags=["Billing & Subscriptions"])


@router.get(
    "/api/v1/billing/seller/{seller_id}/status",
    response_model=SellerBillingStatusResponse,
    summary="Get Seller Billing & Subscription Status",
)
def get_seller_billing_status(
    seller_id: UUID, db: Session = Depends(get_db)
) -> SellerBillingStatusResponse:
    """
    Check seller freemium subscription status, free orders remaining,
    broadcast eligibility, and renewal dates.
    """
    seller = crud.get_user(db, seller_id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller with ID '{seller_id}' not found.",
        )
    if seller.role != UserRole.SELLER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{seller.name}' is not a seller.",
        )

    info = crud.get_seller_billing_info(seller)
    return SellerBillingStatusResponse(**info)


@router.post(
    "/api/v1/billing/seller/{seller_id}/pay",
    response_model=SellerPaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Seller Platform Fee (Rs. 1,000 / month)",
)
def pay_seller_subscription(
    seller_id: UUID,
    payload: SellerPaymentRequest,
    db: Session = Depends(get_db),
) -> SellerPaymentResponse:
    """
    Process or simulate payment of the Rs. 1,000 platform monthly fee.
    Transitions status to 'subscribed', unlocks 30-day broadcast eligibility.
    """
    try:
        updated_seller = crud.process_seller_payment(
            db=db,
            seller_id=seller_id,
            amount=payload.amount,
            payment_method=payload.payment_method,
            transaction_ref=payload.transaction_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return SellerPaymentResponse(
        success=True,
        message=f"Payment of Rs. {payload.amount:.2f} received. Monthly platform subscription active for 30 days.",
        seller_id=updated_seller.id,
        subscription_status=updated_seller.subscription_status,
        subscription_expires_at=updated_seller.subscription_expires_at,
        can_receive_broadcasts=updated_seller.can_receive_broadcasts,
    )


@router.post(
    "/api/v1/orders/complete",
    response_model=OrderCompleteResultResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Complete an Order & Trigger Freemium Quota Check",
)
@router.post(
    "/api/v1/billing/orders/complete",
    response_model=OrderCompleteResultResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def complete_order(
    payload: OrderCompleteRequest, db: Session = Depends(get_db)
) -> OrderCompleteResultResponse:
    """
    Records an order fulfillment for a seller:
    1. Increments seller completed order count.
    2. Decrements free orders remaining.
    3. Automated check: If seller reaches 2 completed orders in active_trial,
       status transitions to 'pending_payment', locking broadcasts.
    """
    try:
        order, seller, alert = crud.complete_seller_order(
            db=db,
            seller_id=payload.seller_id,
            quote_amount=payload.quote_amount,
            requirement_id=payload.requirement_id,
            customer_id=payload.customer_id,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    billing_info = crud.get_seller_billing_info(seller)
    return OrderCompleteResultResponse(
        order=OrderResponse.model_validate(order),
        seller_billing=SellerBillingStatusResponse(**billing_info),
        trial_expired_alert=alert,
    )


@router.get(
    "/orders/seller/{seller_id}",
    response_model=List[OrderResponse],
    summary="List Completed Orders for Seller (Root Route)",
)
@router.get(
    "/api/v1/orders/seller/{seller_id}",
    response_model=List[OrderResponse],
    summary="List Completed Orders for Seller",
)
def get_seller_orders(
    seller_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[OrderResponse]:
    """Retrieve history of completed orders for a seller."""
    orders = crud.list_orders_for_seller(db, seller_id=seller_id, skip=skip, limit=limit)
    return [OrderResponse.model_validate(o) for o in orders]


@router.post(
    "/api/v1/orders/quote",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Seller Accepts Requirement & Submits Itemized Quote",
)
def submit_order_quote(
    payload: SellerQuoteSubmitRequest, db: Session = Depends(get_db)
) -> OrderResponse:
    """
    Seller accepts an incoming customer demand broadcast and submits an itemized quote.
    Creates an Order in PENDING status awaiting customer escrow approval and payment.
    """
    try:
        from backend.subscription import enforce_seller_broadcast_access
        enforce_seller_broadcast_access(payload.seller_id, db)
        order = crud.create_order_quote(db, quote_in=payload)
    except PermissionError as p_err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(p_err))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return OrderResponse.model_validate(order)


@router.get(
    "/api/v1/orders/requirement/{requirement_id}",
    response_model=List[OrderResponse],
    summary="List Quotes Received for Customer Requirement",
)
def get_requirement_quotes(
    requirement_id: UUID, db: Session = Depends(get_db)
) -> List[OrderResponse]:
    """Retrieve all seller price quotes received for a specific customer requirement."""
    orders = crud.list_quotes_for_requirement(db, requirement_id=requirement_id)
    return [OrderResponse.model_validate(o) for o in orders]


@router.post(
    "/api/v1/orders/{order_id}/pay",
    response_model=OrderPaymentSettlementResponse,
    summary="Customer Approves Quote & Settles Order via Mock Escrow Gateway",
)
def pay_and_settle_order(
    order_id: UUID,
    payload: OrderPaymentRequest = Body(...),
    db: Session = Depends(get_db),
) -> OrderPaymentSettlementResponse:
    """
    Mock Escrow Settlement Gateway:
    Customer approves the seller's quote and completes payment.
    1. Simulates payment verification (UPI/Card/Escrow).
    2. Moves order status to COMPLETED and fulfills requirement.
    3. Increments seller completed order count and triggers freemium 2-order milestone check.
    """
    import uuid
    try:
        order, seller, alert = crud.settle_order_escrow_payment(
            db=db,
            order_id=order_id,
            payment_method=payload.payment_method,
            transaction_ref=payload.transaction_ref,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    txn_id = payload.transaction_ref or f"ESCROW-TXN-{uuid.uuid4().hex[:12].upper()}"
    billing_info = crud.get_seller_billing_info(seller)

    return OrderPaymentSettlementResponse(
        success=True,
        order=OrderResponse.model_validate(order),
        escrow_settled=True,
        payment_amount=order.quote_amount,
        transaction_ref=txn_id,
        seller_billing=SellerBillingStatusResponse(**billing_info),
        trial_expired_alert=alert,
        message=f"Payment of Rs. {order.quote_amount:.2f} held and settled via Escrow Gateway. Order fulfilled.",
    )
