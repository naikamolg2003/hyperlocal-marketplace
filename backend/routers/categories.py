"""Category Taxonomy Router."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.schemas import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/api/v1/categories", tags=["Categories"])


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Category / Sub-Category",
)
def create_category(category_in: CategoryCreate, db: Session = Depends(get_db)) -> CategoryResponse:
    """
    Register a standardized product category and optional sub-category.
    Idempotent: returns existing category if already defined.
    """
    return crud.create_category(db, category_in)


@router.get("", response_model=List[CategoryResponse], summary="List Categories")
def list_categories(
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(100, ge=1, le=200, description="Page limit"),
    db: Session = Depends(get_db),
) -> List[CategoryResponse]:
    """Retrieve full catalog of categories and sub-categories."""
    return crud.list_categories(db, skip=skip, limit=limit)


@router.get("/{category_id}", response_model=CategoryResponse, summary="Get Category Details")
def get_category(category_id: UUID, db: Session = Depends(get_db)) -> CategoryResponse:
    """Retrieve category details by UUID."""
    cat = crud.get_category(db, category_id)
    if not cat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{category_id}' not found.",
        )
    return cat
