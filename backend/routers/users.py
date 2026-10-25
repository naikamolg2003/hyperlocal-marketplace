"""User Management and Onboarding Router."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend import crud
from backend.database import get_db
from backend.models import UserRole
from backend.schemas import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Customer, Seller, or Admin",
)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """
    Register a new user with automatic PostGIS spatial geometry mapping.
    Ensures phone numbers are strictly unique.
    """
    existing = crud.get_user_by_phone(db, user_in.phone)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User with phone number '{user_in.phone}' already exists (User ID: {existing.id}).",
        )
    return crud.create_user(db, user_in)


@router.get("", response_model=List[UserResponse], summary="List Users")
def list_users(
    role: Optional[UserRole] = Query(None, description="Filter by user role ('customer', 'seller', 'admin')"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0, description="Offset pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    db: Session = Depends(get_db),
) -> List[UserResponse]:
    """Retrieve users with optional role and status filters."""
    return crud.list_users(db, role=role, is_active=is_active, skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse, summary="Get User Profile")
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    """Retrieve full user profile by UUID."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found.")
    return user


@router.put("/{user_id}", response_model=UserResponse, summary="Update User Profile & Coordinates")
def update_user(user_id: UUID, user_update: UserUpdate, db: Session = Depends(get_db)) -> UserResponse:
    """
    Update user profile attributes. If latitude or longitude are provided,
    the PostGIS geometry point and GiST spatial index are re-calculated.
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found.")

    if user_update.phone and user_update.phone != user.phone:
        conflict = crud.get_user_by_phone(db, user_update.phone)
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phone number '{user_update.phone}' is already in use by another user.",
            )

    return crud.update_user(db, user, user_update)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate / Delete User")
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    """Permanently delete user profile and cascading inventory/requirements."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User '{user_id}' not found.")
    db.delete(user)
    db.commit()
    return None
