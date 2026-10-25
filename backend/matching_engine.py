"""
Geospatial Hyperlocal Matching Engine.

Performs:
1. High-speed 3 km PostGIS spatial radius queries (ST_DWithin) on indexed seller coordinates.
2. Geodesic distance computation (ST_Distance) on the WGS84 ellipsoid.
3. Inventory & category matching against AI-parsed customer requirements.
4. Intelligent merchant ranking based on item availability and proximity.
"""

import logging
import re
from typing import Dict, List, Optional, Set
from uuid import UUID

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.ai_parser import ParsedItem, ParsedRequirement
from backend.models import Category, InventoryItem, User, UserRole

logger = logging.getLogger("hyperlocal-matching-engine")


# -----------------------------------------------------------------------------
# Matching Output Schemas
# -----------------------------------------------------------------------------
class MatchedInventoryItem(BaseModel):
    item_id: UUID
    product_name: str
    price: float
    is_available: bool
    categories: List[str]
    matched_requested_item: str
    match_type: str = Field(
        ...,
        description="Type of match: 'exact_name', 'token_match', or 'category_match'",
    )


class MatchedSeller(BaseModel):
    seller_id: UUID
    name: str
    phone: str
    address: Optional[str] = None
    distance_meters: float
    distance_km: float
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    subscription_status: Optional[str] = "active_trial"
    can_receive_broadcasts: bool = True
    match_status: str = Field(
        ...,
        description="'full_match', 'partial_match', 'category_match', or 'nearby_seller'",
    )
    fulfillment_percentage: float = Field(
        ...,
        description="Percentage (0.0 to 100.0) of requested items this seller can fulfill",
    )
    matched_requested_items: List[str]
    matched_categories: List[str]
    matched_items: List[MatchedInventoryItem]
    coverage_summary: str


class GeospatialMatchSummary(BaseModel):
    customer_location: Dict[str, float]
    search_radius_km: float
    total_active_sellers_within_radius: int
    matched_sellers_count: int
    notified_sellers_count: int
    coverage_status: str = Field(
        default="active_sellers_found",
        description="'active_sellers_found' or 'no_sellers_within_radius'",
    )
    status_message: str = Field(
        default="",
        description="Clear human-readable summary of geospatial coverage",
    )
    sellers: List[MatchedSeller]


# -----------------------------------------------------------------------------
# Matching Helper Functions
# -----------------------------------------------------------------------------
def _tokenize(text: str) -> Set[str]:
    """Tokenize text into lowercase alphanumeric words, filtering out short stopwords."""
    stopwords = {"a", "an", "the", "and", "or", "some", "need", "fresh", "organic", "packet", "packets", "kg", "g", "ml", "l"}
    words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower()))
    return words - stopwords


def _matches_item(inv_item: InventoryItem, req_item: ParsedItem) -> Optional[str]:
    """
    Evaluates whether an inventory item matches a customer's requested item.
    Returns match type ('exact_name', 'token_match', 'category_match') or None.
    """
    inv_name_lower = inv_item.product_name.lower()
    req_name_lower = req_item.product_name.lower()

    # 1. Substring or Exact Match
    if req_name_lower in inv_name_lower or inv_name_lower in req_name_lower:
        return "exact_name"

    # 2. Token / Keyword Overlap
    inv_tokens = _tokenize(inv_name_lower)
    req_tokens = _tokenize(req_name_lower)
    if inv_tokens & req_tokens:
        return "token_match"

    # 3. Category Match (if categories match and there is partial relevance)
    if req_item.category:
        req_cat_lower = req_item.category.lower()
        for cat in inv_item.categories:
            if cat.category and req_cat_lower in cat.category.lower():
                return "category_match"
            if cat.sub_category and req_cat_lower in cat.sub_category.lower():
                return "category_match"

    return None


# -----------------------------------------------------------------------------
# Core Geospatial Matching Service
# -----------------------------------------------------------------------------
def find_matching_sellers(
    db: Session,
    customer_lat: float,
    customer_lon: float,
    parsed_requirement: ParsedRequirement,
    radius_km: float = 3.0,
    include_all_nearby: bool = True,
) -> GeospatialMatchSummary:
    """
    Executes a 3 km PostGIS radius query from the customer's coordinates (WGS84 EPSG:4326),
    identifies active sellers, and correlates their inventory against parsed requirement items.
    """
    radius_meters = radius_km * 1000.0
    target_point = func.ST_SetSRID(func.ST_MakePoint(customer_lon, customer_lat), 4326)

    # PostGIS distance expression
    dist_expr = func.ST_Distance(
        func.geography(User.location),
        func.geography(target_point),
    ).label("distance_meters")

    # Query active sellers within strictly radius_km
    nearby_seller_rows = (
        db.query(User, dist_expr)
        .options(
            selectinload(User.inventory_items).selectinload(InventoryItem.categories)
        )
        .filter(
            User.role == UserRole.SELLER,
            User.is_active.is_(True),
            User.location.is_not(None),
            func.ST_DWithin(
                func.geography(User.location),
                func.geography(target_point),
                radius_meters,
            ),
        )
        .order_by(dist_expr.asc())
        .all()
    )

    total_sellers_in_radius = len(nearby_seller_rows)
    requested_items = parsed_requirement.items
    total_requested = max(len(requested_items), 1)

    matched_sellers: List[MatchedSeller] = []

    for seller, dist_meters in nearby_seller_rows:
        dist_meters_float = round(float(dist_meters), 1)
        dist_km_float = round(dist_meters_float / 1000.0, 2)

        matched_items_list: List[MatchedInventoryItem] = []
        fulfilled_req_items: Set[str] = set()
        matched_category_names: Set[str] = set()

        # Only evaluate available products in stock
        active_inventory = [it for it in seller.inventory_items if it.is_available]

        for req_item in requested_items:
            for inv_item in active_inventory:
                match_type = _matches_item(inv_item, req_item)
                if match_type:
                    fulfilled_req_items.add(req_item.product_name)
                    item_cats = [c.category for c in inv_item.categories if c.category]
                    matched_category_names.update(item_cats)

                    matched_items_list.append(
                        MatchedInventoryItem(
                            item_id=inv_item.id,
                            product_name=inv_item.product_name,
                            price=float(inv_item.price),
                            is_available=inv_item.is_available,
                            categories=item_cats,
                            matched_requested_item=req_item.product_name,
                            match_type=match_type,
                        )
                    )

        # Calculate fulfillment percentage
        fulfillment_pct = round((len(fulfilled_req_items) / total_requested) * 100.0, 1)

        # Classify match status
        if fulfillment_pct >= 100.0:
            match_status = "full_match"
            coverage_summary = f"Fulfills 100% of demand ({len(fulfilled_req_items)}/{total_requested} items in stock)"
        elif fulfillment_pct > 0.0:
            match_status = "partial_match"
            coverage_summary = f"Fulfills {fulfillment_pct}% ({len(fulfilled_req_items)}/{total_requested} items in stock)"
        elif matched_category_names:
            match_status = "category_match"
            coverage_summary = f"Carries related categories: {', '.join(sorted(matched_category_names))}"
        else:
            match_status = "nearby_seller"
            coverage_summary = f"Located {dist_meters_float}m away within delivery perimeter"

        if include_all_nearby or fulfillment_pct > 0.0:
            can_broadcast = getattr(seller, "can_receive_broadcasts", True)
            sub_status = (
                seller.subscription_status.value
                if hasattr(seller.subscription_status, "value")
                else str(seller.subscription_status or "active_trial")
            )
            matched_sellers.append(
                MatchedSeller(
                    seller_id=seller.id,
                    name=seller.name,
                    phone=seller.phone,
                    address=seller.address,
                    distance_meters=dist_meters_float,
                    distance_km=dist_km_float,
                    latitude=seller.latitude,
                    longitude=seller.longitude,
                    subscription_status=sub_status,
                    can_receive_broadcasts=can_broadcast,
                    match_status=match_status,
                    fulfillment_percentage=fulfillment_pct,
                    matched_requested_items=sorted(fulfilled_req_items),
                    matched_categories=sorted(matched_category_names),
                    matched_items=matched_items_list,
                    coverage_summary=coverage_summary,
                )
            )

    # Rank sellers: highest fulfillment first, then closest distance
    matched_sellers.sort(
        key=lambda s: (-s.fulfillment_percentage, s.distance_meters)
    )

    # Count sellers with inventory/category relevance
    relevant_sellers = [s for s in matched_sellers if s.match_status != "nearby_seller"]
    relevant_sellers_count = len(relevant_sellers)

    # In hyperlocal broadcasting, notify only sellers who are eligible to receive broadcasts (freemium gate)
    if relevant_sellers_count > 0:
        notified_count = sum(1 for s in relevant_sellers if s.can_receive_broadcasts)
    else:
        notified_count = sum(1 for s in matched_sellers if s.can_receive_broadcasts)

    # Determine coverage message
    if total_sellers_in_radius == 0:
        coverage_status = "no_sellers_within_radius"
        status_message = f"No active merchants found within {radius_km} km radius. Demand broadcast remains active."
    else:
        coverage_status = "active_sellers_found"
        status_message = f"Found {total_sellers_in_radius} merchant(s) within {radius_km} km; notified {notified_count} eligible store(s)."

    return GeospatialMatchSummary(
        customer_location={"latitude": customer_lat, "longitude": customer_lon},
        search_radius_km=radius_km,
        total_active_sellers_within_radius=total_sellers_in_radius,
        matched_sellers_count=relevant_sellers_count,
        notified_sellers_count=notified_count,
        coverage_status=coverage_status,
        status_message=status_message,
        sellers=matched_sellers,
    )
