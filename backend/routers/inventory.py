import csv
from decimal import Decimal
import io
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import (
    BulkInventoryItemItem,
    BulkInventoryUploadRequest,
    BulkInventoryUploadResponse,
    InventoryItemCreate,
    InventoryItemResponse,
    InventoryItemUpdate,
    NearbyItemResult,
    NearbyItemsResponse,
)

router = APIRouter(prefix="/api/v1/items", tags=["Inventory & Spatial Search"])


@router.post(
    "",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add Inventory Item",
)
def create_item(item_in: InventoryItemCreate, db: Session = Depends(get_db)) -> InventoryItemResponse:
    """
    Publish an individual inventory product for sale.
    Validates that the seller exists and holds a 'seller' role.
    Optionally links the product to multiple category IDs or category names without record duplication.
    """
    seller = crud.get_user(db, item_in.seller_id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller with ID '{item_in.seller_id}' does not exist.",
        )
    if seller.role != UserRole.SELLER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.",
        )

    return crud.create_item(db, item_in)


@router.post(
    "/bulk",
    response_model=BulkInventoryUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk Upload Inventory Items (JSON)",
)
def bulk_upload_items(
    payload: BulkInventoryUploadRequest, db: Session = Depends(get_db)
) -> BulkInventoryUploadResponse:
    """
    Bulk uploads multiple inventory items for a seller in a single transaction.
    Associates products with multiple categories without duplicating product records.
    """
    try:
        items = crud.bulk_create_items(db, seller_id=payload.seller_id, items_in=payload.items)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return BulkInventoryUploadResponse(
        success=True,
        total_uploaded=len(items),
        seller_id=payload.seller_id,
        items=[InventoryItemResponse.model_validate(it) for it in items],
    )


@router.post(
    "/upload-csv",
    response_model=BulkInventoryUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk Upload Inventory Items via CSV File",
)
async def upload_csv_inventory(
    seller_id: UUID = Query(..., description="UUID of the selling merchant"),
    file: UploadFile = File(..., description="CSV file with columns: product_name, price, is_available, categories"),
    db: Session = Depends(get_db),
) -> BulkInventoryUploadResponse:
    """
    Accepts a standard CSV file (product_name, price, is_available, categories)
    and ingests it directly into the merchant's catalog.
    """
    seller = crud.get_user(db, seller_id)
    if not seller:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Seller '{seller_id}' not found.")
    if seller.role != UserRole.SELLER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user is not a merchant.")

    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    items_to_create: List[BulkInventoryItemItem] = []
    for row in reader:
        name = row.get("product_name") or row.get("name") or row.get("Product Name") or row.get("product")
        price_val = row.get("price") or row.get("Price") or row.get("cost")
        if not name or not price_val:
            continue
        try:
            clean_price = Decimal(str(price_val).replace("₹", "").replace("$", "").strip())
        except Exception:
            continue

        avail_val = row.get("is_available") or row.get("available") or row.get("in_stock") or "true"
        is_avail = str(avail_val).strip().lower() in ("true", "1", "yes", "t", "y")

        cat_str = row.get("categories") or row.get("category") or ""
        cat_names = [c.strip() for c in cat_str.split(",") if c.strip()] if cat_str else []

        items_to_create.append(
            BulkInventoryItemItem(
                product_name=name.strip(),
                price=clean_price,
                is_available=is_avail,
                category_names=cat_names,
            )
        )

    if not items_to_create:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid product rows parsed from CSV. Header should contain product_name, price, is_available, categories.",
        )

    items = crud.bulk_create_items(db, seller_id=seller_id, items_in=items_to_create)
    return BulkInventoryUploadResponse(
        success=True,
        total_uploaded=len(items),
        seller_id=seller_id,
        items=[InventoryItemResponse.model_validate(it) for it in items],
    )


@router.get("/nearby", response_model=NearbyItemsResponse, summary="Hyperlocal Nearby Inventory Search")
def search_nearby_items(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Customer latitude (WGS84)"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Customer longitude (WGS84)"),
    radius_km: float = Query(3.0, gt=0.0, le=50.0, description="Search radius in kilometers (default 3 km)"),
    category: Optional[str] = Query(None, description="Filter by category or sub-category name"),
    query: Optional[str] = Query(None, description="Filter by product name keywords"),
    available_only: bool = Query(True, description="Only return currently available items"),
    limit: int = Query(50, ge=1, le=100, description="Maximum items to return"),
    db: Session = Depends(get_db),
) -> NearbyItemsResponse:
    """
    Core Hyperlocal Spatial Search:
    - Utilizes PostGIS `ST_DWithin` on indexed geographic points (EPSG:4326).
    - Calculates exact geodesic distance with `ST_Distance` on WGS84 ellipsoid.
    - Returns sorted by distance ascending (closest sellers first).
    """
    results = crud.get_nearby_items(
        db,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        category_name=category,
        search_query=query,
        is_available_only=available_only,
        limit=limit,
    )

    items_out: List[NearbyItemResult] = []
    for item, dist_meters in results:
        items_out.append(
            NearbyItemResult(
                item=InventoryItemResponse.model_validate(item),
                distance_meters=round(dist_meters, 1),
                distance_km=round(dist_meters / 1000.0, 2),
            )
        )

    return NearbyItemsResponse(
        count=len(items_out),
        query_latitude=lat,
        query_longitude=lon,
        radius_km=radius_km,
        items=items_out,
    )


@router.get("/seller/{seller_id}", response_model=List[InventoryItemResponse], summary="List Seller Catalog")
def list_seller_items(
    seller_id: UUID,
    is_available: Optional[bool] = Query(None, description="Filter by availability status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[InventoryItemResponse]:
    """Retrieve full inventory list published by a specific merchant."""
    seller = crud.get_user(db, seller_id)
    if not seller:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seller '{seller_id}' not found.",
        )
    return crud.list_seller_items(db, seller_id, is_available=is_available, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=InventoryItemResponse, summary="Get Inventory Item Details")
def get_item(item_id: UUID, db: Session = Depends(get_db)) -> InventoryItemResponse:
    """Retrieve individual product record with mapped categories and seller information."""
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item '{item_id}' not found.")
    return item


@router.put("/{item_id}", response_model=InventoryItemResponse, summary="Update Item & Category Mappings")
def update_item(
    item_id: UUID,
    item_update: InventoryItemUpdate,
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    """Update item pricing, product name, availability, and mapped category IDs."""
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item '{item_id}' not found.")
    return crud.update_item(db, item, item_update)


@router.patch(
    "/{item_id}/availability",
    response_model=InventoryItemResponse,
    summary="Toggle Item In-Stock Availability",
)
def toggle_availability(
    item_id: UUID,
    is_available: bool = Body(..., embed=True, description="New availability toggle boolean"),
    db: Session = Depends(get_db),
) -> InventoryItemResponse:
    """Instant merchant toggle for item stock availability."""
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item '{item_id}' not found.")
    return crud.toggle_item_availability(db, item, is_available)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Inventory Item")
def delete_item(item_id: UUID, db: Session = Depends(get_db)):
    """Permanently delete an inventory item."""
    item = crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Item '{item_id}' not found.")
    crud.delete_item(db, item)
    return None
