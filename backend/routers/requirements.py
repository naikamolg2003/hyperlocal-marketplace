"""Customer Requirements & Demand Broadcasting Router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.ai_parser import parse_requirement_text
from backend.matching_engine import find_matching_sellers
from backend.models import Requirement, RequirementStatus, User, UserRole
from backend.schemas import (
    NearbyRequirementResult,
    NearbyRequirementsResponse,
    RequirementCreate,
    RequirementResponse,
    RequirementSubmitRequest,
    RequirementSubmitResponse,
    RequirementUpdate,
)

router = APIRouter(prefix="/api/v1/requirements", tags=["Customer Requirements"])


@router.post(
    "/submit",
    response_model=RequirementSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Requirement with AI Parsing & 3 km Geospatial Matching",
)
async def submit_requirement(
    payload: RequirementSubmitRequest,
    db: Session = Depends(get_db),
) -> RequirementSubmitResponse:
    """
    Core AI & Geospatial Pipeline:
    1. Resolves or provisions customer with GPS coordinates.
    2. Runs AI Parser to extract structured shopping list, quantities, categories & urgency.
    3. Persists requirement into PostgreSQL with JSONB structured output.
    4. Runs 3 km PostGIS spatial radius query (ST_DWithin) to find local sellers.
    5. Matches seller inventory & categories against shopping list items.
    6. Returns structured summary and count of notified local merchants.
    """
    # 1. Resolve or provision customer
    customer: Optional[User] = None
    if payload.customer_id:
        customer = crud.get_user(db, payload.customer_id)
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Customer with ID '{payload.customer_id}' does not exist.",
            )
        # Re-synchronize coordinates if passed
        customer.set_coordinates(payload.latitude, payload.longitude)
        db.commit()
    elif payload.customer_phone:
        customer = crud.get_user_by_phone(db, payload.customer_phone)
        if customer:
            customer.set_coordinates(payload.latitude, payload.longitude)
            db.commit()

    if not customer:
        # Create a new customer profile for this GPS location
        import uuid
        phone_suffix = uuid.uuid4().hex[:8]
        generated_phone = payload.customer_phone or f"+919{phone_suffix}"
        customer = User(
            name=payload.customer_name or "Local Customer",
            phone=generated_phone,
            role=UserRole.CUSTOMER,
            address="Current GPS Location",
        )
        customer.set_coordinates(payload.latitude, payload.longitude)
        db.add(customer)
        db.commit()
        db.refresh(customer)

    # 2. Trigger AI Parser
    parsed_req = await parse_requirement_text(payload.raw_text)

    # 3. Save requirement in database
    requirement = Requirement(
        customer_id=customer.id,
        raw_text=payload.raw_text,
        structured_json=parsed_req.model_dump(),
        status=RequirementStatus.BROADCASTING,
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)

    # 4. Run 3 km Geospatial Matching Engine
    match_summary = find_matching_sellers(
        db=db,
        customer_lat=payload.latitude,
        customer_lon=payload.longitude,
        parsed_requirement=parsed_req,
        radius_km=payload.radius_km,
        include_all_nearby=True,
    )

    return RequirementSubmitResponse(
        requirement_id=requirement.id,
        customer_id=customer.id,
        raw_text=requirement.raw_text,
        status=requirement.status,
        parsed_requirement=parsed_req.model_dump(),
        matching_summary=match_summary.model_dump(),
        notified_sellers_count=match_summary.notified_sellers_count,
        created_at=requirement.created_at,
    )


@router.post(
    "",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Pre-Structured Customer Requirement",
)
def create_requirement(req_in: RequirementCreate, db: Session = Depends(get_db)) -> RequirementResponse:
    """
    Submit a customer demand request.
    Stores raw natural language text alongside structured JSON parsing.
    Validates that the customer exists and holds the 'customer' role.
    """
    customer = crud.get_user(db, req_in.customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer with ID '{req_in.customer_id}' does not exist.",
        )
    if customer.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{customer.name}' has role '{customer.role.value}', not 'customer'.",
        )

    return crud.create_requirement(db, req_in)


@router.get("/nearby", response_model=NearbyRequirementsResponse, summary="Nearby Demands for Merchants")
def search_nearby_requirements(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Merchant latitude"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Merchant longitude"),
    radius_km: float = Query(5.0, gt=0.0, le=50.0, description="Radius in kilometers"),
    status: Optional[RequirementStatus] = Query(None, description="Optional status filter"),
    seller_id: Optional[UUID] = Query(None, description="Optional seller UUID to verify broadcast subscription access"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> NearbyRequirementsResponse:
    """
    Enables local merchants to discover active customer requirements within their delivery radius.
    If seller_id is provided, enforces the freemium subscription rule:
    If completed_orders_count > 2 and subscription_status != 'active',
    restricts access (HTTP 403 Forbidden) and returns a message requiring the Rs. 1,000 monthly platform fee.
    """
    if seller_id:
        from backend.subscription import enforce_seller_broadcast_access
        enforce_seller_broadcast_access(seller_id, db)

    results = crud.get_nearby_requirements(
        db,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        status=status,
        limit=limit,
    )

    reqs_out: List[NearbyRequirementResult] = []
    for req, dist_meters in results:
        reqs_out.append(
            NearbyRequirementResult(
                requirement=RequirementResponse.model_validate(req),
                distance_meters=round(dist_meters, 1),
                distance_km=round(dist_meters / 1000.0, 2),
            )
        )

    return NearbyRequirementsResponse(
        count=len(reqs_out),
        query_latitude=lat,
        query_longitude=lon,
        radius_km=radius_km,
        requirements=reqs_out,
    )


@router.get(
    "/broadcasts/seller/{seller_id}",
    response_model=NearbyRequirementsResponse,
    summary="Get Active Requirement Broadcasts for Seller (Freemium Gated)",
)
@router.get(
    "/api/v1/requirements/broadcasts/seller/{seller_id}",
    response_model=NearbyRequirementsResponse,
    include_in_schema=False,
)
def get_seller_broadcasts(
    seller_id: UUID,
    radius_km: float = Query(3.0, gt=0.0, le=50.0, description="Discovery perimeter radius in kilometers"),
    db: Session = Depends(get_db),
) -> NearbyRequirementsResponse:
    """
    Merchant views customer requirement broadcasts within their delivery radius.
    Enforces the freemium subscription rule:
    If completed_orders_count > 2 and subscription_status != 'active',
    restricts access (HTTP 403 Forbidden) returning a message requiring the Rs. 1,000 monthly fee payment to continue.
    """
    from backend.subscription import enforce_seller_broadcast_access

    seller = enforce_seller_broadcast_access(seller_id, db)
    seller_lat = seller.latitude if seller.latitude is not None else 18.5987
    seller_lon = seller.longitude if seller.longitude is not None else 73.7660

    results = crud.get_nearby_requirements(
        db,
        lat=seller_lat,
        lon=seller_lon,
        radius_km=radius_km,
        status=None,
        limit=50,
    )

    reqs_out: List[NearbyRequirementResult] = []
    for req, dist_meters in results:
        reqs_out.append(
            NearbyRequirementResult(
                requirement=RequirementResponse.model_validate(req),
                distance_meters=round(dist_meters, 1),
                distance_km=round(dist_meters / 1000.0, 2),
            )
        )

    return NearbyRequirementsResponse(
        count=len(reqs_out),
        query_latitude=seller_lat,
        query_longitude=seller_lon,
        radius_km=radius_km,
        requirements=reqs_out,
    )


@router.get("/customer/{customer_id}", response_model=List[RequirementResponse], summary="Customer Demands History")
def list_customer_requirements(
    customer_id: UUID,
    status: Optional[RequirementStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[RequirementResponse]:
    """Retrieve all demands submitted by a specific customer."""
    customer = crud.get_user(db, customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Customer '{customer_id}' not found.",
        )
    return crud.list_customer_requirements(db, customer_id, status=status, skip=skip, limit=limit)


@router.get("/{requirement_id}", response_model=RequirementResponse, summary="Get Requirement Details")
def get_requirement(requirement_id: UUID, db: Session = Depends(get_db)) -> RequirementResponse:
    """Retrieve individual requirement record."""
    req = crud.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{requirement_id}' not found.",
        )
    return req


@router.patch(
    "/{requirement_id}/status",
    response_model=RequirementResponse,
    summary="Update Requirement Lifecycle Status",
)
def update_status(
    requirement_id: UUID,
    status: RequirementStatus = Body(..., embed=True, description="New lifecycle status"),
    db: Session = Depends(get_db),
) -> RequirementResponse:
    """Transition requirement status (e.g. submitted -> broadcasting -> fulfilled)."""
    req = crud.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{requirement_id}' not found.",
        )
    return crud.update_requirement_status(db, req, status)


@router.put("/{requirement_id}", response_model=RequirementResponse, summary="Update Requirement Content")
def update_requirement(
    requirement_id: UUID,
    req_update: RequirementUpdate,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    """Update requirement raw text or parsed structured JSON."""
    req = crud.get_requirement(db, requirement_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{requirement_id}' not found.",
        )
    return crud.update_requirement(db, req, req_update)
