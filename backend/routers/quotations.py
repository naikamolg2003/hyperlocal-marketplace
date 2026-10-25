"""Vendor Quotations Router for Hyperlocal Marketplace."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import QuotationResponse, QuotationSubmitRequest

router = APIRouter(tags=["Vendor Quotations"])


@router.post(
    "/quotations/submit",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Vendor Price Quote for Requirement",
)
@router.post(
    "/api/v1/quotations/submit",
    response_model=QuotationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def submit_quotation(
    payload: QuotationSubmitRequest,
    db: Session = Depends(get_db),
) -> QuotationResponse:
    """
    Allows a subscribed local seller to submit a price quote for a customer requirement.
    Enforces that:
    1. The requirement exists.
    2. The seller exists and has role 'seller'.
    3. The seller has an active subscription (either active trial with remaining quota or paid subscription).
    """
    try:
        from backend.subscription import enforce_seller_broadcast_access
        enforce_seller_broadcast_access(payload.seller_id, db)
        return crud.create_quotation(db, payload)
    except PermissionError as p_err:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(p_err),
        )
    except ValueError as v_err:
        err_msg = str(v_err)
        if "does not exist" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=err_msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )


@router.get(
    "/requirements/{requirement_id}/quotations",
    response_model=List[QuotationResponse],
    status_code=status.HTTP_200_OK,
    summary="List All Quotes for Requirement",
)
@router.get(
    "/api/v1/requirements/{requirement_id}/quotations",
    response_model=List[QuotationResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_requirement_quotations(
    requirement_id: UUID,
    db: Session = Depends(get_db),
) -> List[QuotationResponse]:
    """
    Allows customers to retrieve and view all quotations submitted by local sellers for their requirement.
    Returns seller details, itemized prices, total amount, estimated delivery time, and status.
    """
    req = crud.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement with ID '{requirement_id}' does not exist.",
        )
    return crud.list_quotations_for_requirement(db, requirement_id)
