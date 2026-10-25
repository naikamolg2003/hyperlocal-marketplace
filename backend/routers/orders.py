"""
Order Lifecycle and Delivery Status Tracking Router for Hyperlocal Marketplace.

Endpoints:
- POST /orders/accept-quote: Customer selects a vendor's quote, transitioning order to ACCEPTED.
- PATCH /orders/{order_id}/status: Seller updates delivery status (e.g., OUT_FOR_DELIVERY, COMPLETED).
- GET /orders/{order_id}: Fetches full order details by UUID.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import (
    OrderAcceptQuoteRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
)

router = APIRouter(tags=["Order Lifecycle & Delivery Tracking"])


@router.post(
    "/orders/accept-quote",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer Accepts Seller Quote and Transitions Order to ACCEPTED",
)
@router.post(
    "/api/v1/orders/accept-quote",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def accept_quote(
    payload: OrderAcceptQuoteRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Customer selects a specific seller's quote:
    1. Sets the chosen quotation's status to 'accepted'.
    2. Sets all competing quotes for this requirement to 'rejected'.
    3. Transitions requirement status to 'ACCEPTED'.
    4. Creates or transitions the Order record with status 'ACCEPTED'.
    """
    try:
        order = crud.accept_quotation_and_create_order(
            db=db,
            quotation_id=payload.quotation_id,
            notes=payload.notes,
        )
    except ValueError as e:
        err_msg = str(e)
        if "does not exist" in err_msg or "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    return OrderResponse.model_validate(order)


@router.patch(
    "/orders/{order_id}/status",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Order Delivery Lifecycle Status",
)
@router.patch(
    "/api/v1/orders/{order_id}/status",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def update_order_status(
    order_id: UUID,
    payload: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Allows a seller to update the delivery status of an active order.
    Valid statuses: 'BROADCASTED', 'QUOTED', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED'.
    Transitioning to 'COMPLETED' records completion timestamp and increments the seller's
    completed orders counter, triggering freemium billing subscription checks.
    """
    try:
        updated_order = crud.update_order_delivery_status(
            db=db,
            order_id=order_id,
            new_status=payload.status,
            notes=payload.notes,
        )
    except ValueError as e:
        err_msg = str(e)
        if "does not exist" in err_msg or "not found" in err_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    return OrderResponse.model_validate(updated_order)


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Order Details by ID",
)
@router.get(
    "/api/v1/orders/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_order_by_id(
    order_id: UUID,
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Retrieve full details for an order by UUID."""
    order = crud.get_order(db, order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID '{order_id}' not found.",
        )
    return OrderResponse.model_validate(order)
