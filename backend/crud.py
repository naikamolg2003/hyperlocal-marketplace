"""
Database CRUD and Business Logic Operations for Hyperlocal Marketplace.

Features:
- PostGIS spherical radius filtering with ST_DWithin and geodesic ST_Distance.
- Multi-category inventory mapping across M:N associations.
- User coordinate synchronization with PostGIS Geometry(Point, 4326).
- Natural language requirement persistence and lifecycle management.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Set, Tuple
from uuid import UUID

from geoalchemy2.functions import ST_Distance, ST_DWithin, ST_MakePoint, ST_SetSRID
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from backend.models import (
    Category,
    InventoryItem,
    Order,
    OrderStatus,
    Quotation,
    QuotationStatus,
    Requirement,
    RequirementStatus,
    SubscriptionStatus,
    User,
    UserRole,
    item_categories,
)
from backend.schemas import (
    BulkInventoryItemItem,
    CategoryCreate,
    InventoryItemCreate,
    InventoryItemUpdate,
    QuotationSubmitRequest,
    RequirementCreate,
    RequirementUpdate,
    SellerQuoteSubmitRequest,
    UserCreate,
    UserUpdate,
)


# =============================================================================
# Category Operations
# =============================================================================
def get_category(db: Session, category_id: UUID) -> Optional[Category]:
    return db.query(Category).filter(Category.id == category_id).first()


def get_category_by_name(
    db: Session, category: str, sub_category: Optional[str] = None
) -> Optional[Category]:
    query = db.query(Category).filter(Category.category == category)
    if sub_category is not None:
        query = query.filter(Category.sub_category == sub_category)
    else:
        query = query.filter(Category.sub_category.is_(None))
    return query.first()


def list_categories(db: Session, skip: int = 0, limit: int = 100) -> List[Category]:
    return db.query(Category).order_by(Category.category, Category.sub_category).offset(skip).limit(limit).all()


def create_category(db: Session, category_in: CategoryCreate) -> Category:
    existing = get_category_by_name(db, category_in.category, category_in.sub_category)
    if existing:
        return existing

    category = Category(
        category=category_in.category,
        sub_category=category_in.sub_category,
        description=category_in.description,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def get_or_create_category(
    db: Session, category_name: str, sub_category_name: Optional[str] = None
) -> Category:
    clean_cat = category_name.strip()
    clean_sub = sub_category_name.strip() if sub_category_name else None
    existing = get_category_by_name(db, clean_cat, clean_sub)
    if existing:
        return existing
    new_cat = Category(category=clean_cat, sub_category=clean_sub)
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


# =============================================================================
# User Operations
# =============================================================================
def get_user(db: Session, user_id: UUID) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return db.query(User).filter(User.phone == phone).first()


def list_users(
    db: Session,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[User]:
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()


def create_user(db: Session, user_in: UserCreate) -> User:
    user = User(
        name=user_in.name,
        phone=user_in.phone,
        role=user_in.role,
        address=user_in.address,
    )
    if user_in.latitude is not None and user_in.longitude is not None:
        user.set_coordinates(user_in.latitude, user_in.longitude)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, user_update: UserUpdate) -> User:
    update_data = user_update.model_dump(exclude_unset=True)

    lat = update_data.pop("latitude", None)
    lon = update_data.pop("longitude", None)

    for field, value in update_data.items():
        setattr(user, field, value)

    # Re-sync geospatial point if coordinates are provided
    if lat is not None and lon is not None:
        user.set_coordinates(lat, lon)
    elif lat is not None and user.longitude is not None:
        user.set_coordinates(lat, user.longitude)
    elif lon is not None and user.latitude is not None:
        user.set_coordinates(user.latitude, lon)

    db.commit()
    db.refresh(user)
    return user


# =============================================================================
# Inventory Item Operations
# =============================================================================
def get_item(db: Session, item_id: UUID) -> Optional[InventoryItem]:
    return (
        db.query(InventoryItem)
        .options(selectinload(InventoryItem.categories), selectinload(InventoryItem.seller))
        .filter(InventoryItem.id == item_id)
        .first()
    )


def list_seller_items(
    db: Session,
    seller_id: UUID,
    is_available: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[InventoryItem]:
    query = (
        db.query(InventoryItem)
        .options(selectinload(InventoryItem.categories), selectinload(InventoryItem.seller))
        .filter(InventoryItem.seller_id == seller_id)
    )
    if is_available is not None:
        query = query.filter(InventoryItem.is_available == is_available)
    return query.order_by(InventoryItem.created_at.desc()).offset(skip).limit(limit).all()


def create_item(db: Session, item_in: InventoryItemCreate) -> InventoryItem:
    item = InventoryItem(
        seller_id=item_in.seller_id,
        product_name=item_in.product_name,
        price=item_in.price,
        is_available=item_in.is_available,
    )
    db.add(item)
    db.flush()  # Allocate item.id

    # Collect unique category IDs without duplication
    target_category_ids: Set[UUID] = set(item_in.category_ids or [])
    if item_in.category_names:
        for cname in item_in.category_names:
            if cname and cname.strip():
                cat = get_or_create_category(db, cname.strip())
                target_category_ids.add(cat.id)

    if target_category_ids:
        for i, cid in enumerate(target_category_ids):
            is_primary = (i == 0)
            db.execute(
                item_categories.insert().values(
                    item_id=item.id,
                    category_id=cid,
                    is_primary=is_primary,
                )
            )

    db.commit()
    return get_item(db, item.id)


def bulk_create_items(
    db: Session, seller_id: UUID, items_in: List[BulkInventoryItemItem]
) -> List[InventoryItem]:
    seller = get_user(db, seller_id)
    if not seller:
        raise ValueError(f"Seller with ID '{seller_id}' does not exist.")
    if seller.role != UserRole.SELLER:
        raise ValueError(f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.")

    created_ids: List[UUID] = []
    for it_in in items_in:
        item = InventoryItem(
            seller_id=seller_id,
            product_name=it_in.product_name,
            price=it_in.price,
            is_available=it_in.is_available,
        )
        db.add(item)
        db.flush()

        target_cat_ids: Set[UUID] = set(it_in.category_ids or [])
        if it_in.category_names:
            for cname in it_in.category_names:
                if cname and cname.strip():
                    cat = get_or_create_category(db, cname.strip())
                    target_cat_ids.add(cat.id)

        for i, cid in enumerate(target_cat_ids):
            db.execute(
                item_categories.insert().values(
                    item_id=item.id,
                    category_id=cid,
                    is_primary=(i == 0),
                )
            )
        created_ids.append(item.id)

    db.commit()
    return [get_item(db, iid) for iid in created_ids]


def update_item(db: Session, item: InventoryItem, item_update: InventoryItemUpdate) -> InventoryItem:
    update_data = item_update.model_dump(exclude_unset=True)
    category_ids = update_data.pop("category_ids", None)
    category_names = update_data.pop("category_names", None)

    for field, value in update_data.items():
        setattr(item, field, value)

    if category_ids is not None or category_names is not None:
        target_cat_ids: Set[UUID] = set(category_ids or [])
        if category_names:
            for cname in category_names:
                if cname and cname.strip():
                    cat = get_or_create_category(db, cname.strip())
                    target_cat_ids.add(cat.id)

        # Clear existing associations
        db.execute(item_categories.delete().where(item_categories.c.item_id == item.id))
        for i, cid in enumerate(target_cat_ids):
            is_primary = (i == 0)
            db.execute(
                item_categories.insert().values(
                    item_id=item.id,
                    category_id=cid,
                    is_primary=is_primary,
                )
            )

    db.commit()
    return get_item(db, item.id)


def toggle_item_availability(db: Session, item: InventoryItem, is_available: bool) -> InventoryItem:
    item.is_available = is_available
    db.commit()
    db.refresh(item)
    return item


def delete_item(db: Session, item: InventoryItem) -> None:
    db.delete(item)
    db.commit()


def get_nearby_items(
    db: Session,
    lat: float,
    lon: float,
    radius_km: float = 3.0,
    category_name: Optional[str] = None,
    search_query: Optional[str] = None,
    is_available_only: bool = True,
    limit: int = 50,
) -> List[Tuple[InventoryItem, float]]:
    """
    Hyperlocal search using PostGIS spherical geometry.
    Finds items sold by merchants located within radius_km of (lat, lon).
    Returns list of (InventoryItem, distance_in_meters) tuples ordered closest first.
    """
    radius_meters = radius_km * 1000.0
    target_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    # PostGIS distance expression
    dist_expr = func.ST_Distance(
        func.geography(User.location),
        func.geography(target_point),
    ).label("distance_meters")

    query = (
        db.query(InventoryItem, dist_expr)
        .join(User, InventoryItem.seller_id == User.id)
        .options(selectinload(InventoryItem.categories), selectinload(InventoryItem.seller))
        .filter(
            User.location.is_not(None),
            User.is_active.is_(True),
            func.ST_DWithin(
                func.geography(User.location),
                func.geography(target_point),
                radius_meters,
            ),
        )
    )

    if is_available_only:
        query = query.filter(InventoryItem.is_available.is_(True))

    if search_query:
        query = query.filter(InventoryItem.product_name.ilike(f"%{search_query}%"))

    if category_name:
        query = query.join(InventoryItem.categories).filter(
            or_(
                Category.category.ilike(f"%{category_name}%"),
                Category.sub_category.ilike(f"%{category_name}%"),
            )
        )

    results = query.order_by(dist_expr.asc()).limit(limit).all()
    return results


# =============================================================================
# Requirement Operations (Customer Demand)
# =============================================================================
def get_requirement(db: Session, requirement_id: UUID) -> Optional[Requirement]:
    return (
        db.query(Requirement)
        .options(selectinload(Requirement.customer))
        .filter(Requirement.id == requirement_id)
        .first()
    )


def list_customer_requirements(
    db: Session,
    customer_id: UUID,
    status: Optional[RequirementStatus] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[Requirement]:
    query = (
        db.query(Requirement)
        .options(selectinload(Requirement.customer))
        .filter(Requirement.customer_id == customer_id)
    )
    if status:
        query = query.filter(Requirement.status == status)
    return query.order_by(Requirement.created_at.desc()).offset(skip).limit(limit).all()


def create_requirement(db: Session, req_in: RequirementCreate) -> Requirement:
    requirement = Requirement(
        customer_id=req_in.customer_id,
        raw_text=req_in.raw_text,
        structured_json=req_in.structured_json,
        status=req_in.status,
    )
    db.add(requirement)
    db.commit()
    return get_requirement(db, requirement.id)


def update_requirement(
    db: Session, requirement: Requirement, req_update: RequirementUpdate
) -> Requirement:
    update_data = req_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement_status(
    db: Session, requirement: Requirement, status: RequirementStatus
) -> Requirement:
    requirement.status = status
    db.commit()
    db.refresh(requirement)
    return requirement


def get_nearby_requirements(
    db: Session,
    lat: float,
    lon: float,
    radius_km: float = 3.0,
    status: Optional[RequirementStatus] = None,
    limit: int = 50,
) -> List[Tuple[Requirement, float]]:
    """
    Find customer requirements submitted within radius_km of a merchant's coordinates.
    """
    radius_meters = radius_km * 1000.0
    target_point = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)

    dist_expr = func.ST_Distance(
        func.geography(User.location),
        func.geography(target_point),
    ).label("distance_meters")

    query = (
        db.query(Requirement, dist_expr)
        .join(User, Requirement.customer_id == User.id)
        .options(selectinload(Requirement.customer))
        .filter(
            User.location.is_not(None),
            func.ST_DWithin(
                func.geography(User.location),
                func.geography(target_point),
                radius_meters,
            ),
        )
    )

    if status:
        query = query.filter(Requirement.status == status)
    else:
        # Default to active demands only
        query = query.filter(Requirement.status.in_([RequirementStatus.SUBMITTED, RequirementStatus.BROADCASTING]))

    results = query.order_by(dist_expr.asc()).limit(limit).all()
    return results


# =============================================================================
# Order & Freemium Billing Operations
# =============================================================================
def complete_seller_order(
    db: Session,
    seller_id: UUID,
    quote_amount: Decimal,
    requirement_id: Optional[UUID] = None,
    customer_id: Optional[UUID] = None,
    notes: Optional[str] = None,
) -> Tuple[Order, User, bool]:
    """
    Fulfills an order for a seller and executes the automated freemium check:
    - Increments seller's completed_orders_count.
    - Updates free_orders_remaining = max(0, 2 - completed_orders_count).
    - If seller completed their 2nd successful order, automatically transitions
      subscription_status to 'pending_payment', locking broadcast reception
      until the Rs. 1,000 monthly platform fee is paid.
    - Returns (order, seller, trial_expired_alert).
    """
    seller = get_user(db, seller_id)
    if not seller:
        raise ValueError(f"Seller with ID '{seller_id}' does not exist.")
    if seller.role != UserRole.SELLER:
        raise ValueError(f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.")

    # Resolve customer ID if not directly provided
    resolved_customer_id = customer_id
    if requirement_id:
        req = get_requirement(db, requirement_id)
        if req:
            req.status = RequirementStatus.FULFILLED
            if not resolved_customer_id:
                resolved_customer_id = req.customer_id

    if not resolved_customer_id:
        # Fallback to customer or create a default transaction party
        resolved_customer_id = seller_id  # self-contained transaction reference

    # Create completed order record
    order = Order(
        seller_id=seller.id,
        customer_id=resolved_customer_id,
        requirement_id=requirement_id,
        quote_amount=quote_amount,
        status=OrderStatus.COMPLETED,
        notes=notes,
        completed_at=func.now(),
    )
    db.add(order)

    # Increment completed orders and update freemium quota
    seller.completed_orders_count = (seller.completed_orders_count or 0) + 1
    seller.free_orders_remaining = max(0, 2 - seller.completed_orders_count)

    # Automated check: Trigger subscription status update upon 2nd completed order
    trial_expired_alert = False
    if seller.subscription_status in (SubscriptionStatus.ACTIVE_TRIAL, SubscriptionStatus.TRIAL, "trial", "active_trial"):
        if seller.completed_orders_count >= 2:
            seller.subscription_status = SubscriptionStatus.PENDING_PAYMENT
            trial_expired_alert = True

    db.commit()
    db.refresh(order)
    db.refresh(seller)
    return order, seller, trial_expired_alert


def process_seller_payment(
    db: Session,
    seller_id: UUID,
    amount: float = 1000.0,
    payment_method: str = "upi",
    transaction_ref: Optional[str] = None,
) -> User:
    """
    Simulates / processes seller monthly platform subscription payment of Rs. 1,000.
    Upgrades or restores seller to 'subscribed' status for 30 days, re-enabling broadcasts.
    """
    seller = get_user(db, seller_id)
    if not seller:
        raise ValueError(f"Seller with ID '{seller_id}' does not exist.")
    if seller.role != UserRole.SELLER:
        raise ValueError(f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.")

    seller.subscription_status = SubscriptionStatus.SUBSCRIBED
    seller.subscription_expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()
    db.refresh(seller)
    return seller


def get_seller_billing_info(seller: User) -> dict:
    """
    Computes human-readable billing status and broadcast eligibility for a seller.
    """
    status = seller.subscription_status
    completed = seller.completed_orders_count or 0
    remaining = max(0, 2 - completed)
    can_broadcast = seller.can_receive_broadcasts

    if status == SubscriptionStatus.SUBSCRIBED:
        msg = f"Subscription Active: Valid until {seller.subscription_expires_at.strftime('%Y-%m-%d') if seller.subscription_expires_at else 'Active'}"
    elif status == SubscriptionStatus.PENDING_PAYMENT:
        msg = "Free Trial Ended: Completed 2/2 free trial orders. Pay Rs. 1,000 platform fee to resume receiving broadcasts."
    elif status == SubscriptionStatus.TRIAL_EXPIRED:
        msg = "Trial Expired: Pay Rs. 1,000 monthly platform fee to activate broadcast alerts."
    else:
        # ACTIVE_TRIAL
        msg = f"Free Trial Active: {remaining} of 2 free orders remaining before monthly subscription is required."

    return {
        "seller_id": seller.id,
        "seller_name": seller.name,
        "subscription_status": status,
        "completed_orders_count": completed,
        "free_orders_remaining": remaining,
        "monthly_platform_fee": 1000.0,
        "can_receive_broadcasts": can_broadcast,
        "subscription_expires_at": seller.subscription_expires_at,
        "status_message": msg,
    }


def list_orders_for_seller(
    db: Session, seller_id: UUID, skip: int = 0, limit: int = 50
) -> List[Order]:
    return (
        db.query(Order)
        .options(selectinload(Order.seller), selectinload(Order.customer))
        .filter(Order.seller_id == seller_id)
        .order_by(Order.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def create_order_quote(db: Session, quote_in: SellerQuoteSubmitRequest) -> Order:
    """
    Seller accepts an incoming customer requirement and submits an itemized quote/bill.
    Status starts as PENDING until customer approves and settles via mock escrow payment.
    """
    seller = get_user(db, quote_in.seller_id)
    if not seller:
        raise ValueError(f"Seller with ID '{quote_in.seller_id}' does not exist.")
    if seller.role != UserRole.SELLER:
        raise ValueError(f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.")

    from backend.subscription import check_seller_subscription_access
    allowed, message = check_seller_subscription_access(seller)
    if not allowed:
        raise PermissionError(message)

    req = get_requirement(db, quote_in.requirement_id)
    if not req:
        raise ValueError(f"Requirement with ID '{quote_in.requirement_id}' does not exist.")

    itemized_data = {
        "delivery_estimate_minutes": quote_in.delivery_estimate_minutes or 20,
        "items": quote_in.itemized_items or [],
        "notes": quote_in.notes or "",
    }

    order = Order(
        requirement_id=req.id,
        seller_id=seller.id,
        customer_id=req.customer_id,
        quote_amount=quote_in.quote_amount,
        status=OrderStatus.PENDING,
        notes=quote_in.notes,
        itemized_quote=itemized_data,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def settle_order_escrow_payment(
    db: Session,
    order_id: UUID,
    payment_method: str = "upi",
    transaction_ref: Optional[str] = None,
) -> Tuple[Order, User, bool]:
    """
    Mock payment gateway / escrow settlement handler:
    1. Simulates payment verification and marks order as COMPLETED.
    2. Marks linked requirement as FULFILLED.
    3. Increments seller's completed order counter.
    4. Triggers automated check: after 2nd completed order in active_trial,
       transitions seller subscription to 'pending_payment', locking broadcasts.
    """
    order = (
        db.query(Order)
        .options(selectinload(Order.seller), selectinload(Order.customer))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise ValueError(f"Order with ID '{order_id}' not found.")
    if order.status == OrderStatus.COMPLETED:
        raise ValueError(f"Order '{order_id}' is already paid and completed.")

    order.status = OrderStatus.COMPLETED
    order.completed_at = func.now()

    if order.requirement_id:
        req = get_requirement(db, order.requirement_id)
        if req:
            req.status = RequirementStatus.FULFILLED

    seller = order.seller
    seller.completed_orders_count = (seller.completed_orders_count or 0) + 1
    seller.free_orders_remaining = max(0, 2 - seller.completed_orders_count)

    trial_expired_alert = False
    if seller.subscription_status in (SubscriptionStatus.ACTIVE_TRIAL, SubscriptionStatus.TRIAL, "trial", "active_trial"):
        if seller.completed_orders_count >= 2:
            seller.subscription_status = SubscriptionStatus.PENDING_PAYMENT
            trial_expired_alert = True

    db.commit()
    db.refresh(order)
    db.refresh(seller)
    return order, seller, trial_expired_alert


def list_quotes_for_requirement(db: Session, requirement_id: UUID) -> List[Order]:
    return (
        db.query(Order)
        .options(selectinload(Order.seller), selectinload(Order.customer))
        .filter(Order.requirement_id == requirement_id)
        .order_by(Order.created_at.desc())
        .all()
    )


# =============================================================================
# Quotation Operations (Vendor Price Quotes)
# =============================================================================
def create_quotation(db: Session, quote_in: QuotationSubmitRequest) -> Quotation:
    """
    Submits a vendor quotation for a customer requirement.
    Enforces that the quoting seller exists, has role 'seller', and has an active subscription.
    """
    seller = get_user(db, quote_in.seller_id)
    if not seller:
        raise ValueError(f"Seller with ID '{quote_in.seller_id}' does not exist.")
    if seller.role != UserRole.SELLER:
        raise ValueError(f"User '{seller.name}' has role '{seller.role.value}', not 'seller'.")

    from backend.subscription import check_seller_subscription_access
    allowed, message = check_seller_subscription_access(seller)
    if not allowed:
        raise PermissionError(message)

    req = get_requirement(db, quote_in.requirement_id)
    if not req:
        raise ValueError(f"Requirement with ID '{quote_in.requirement_id}' does not exist.")

    quotation = Quotation(
        requirement_id=req.id,
        seller_id=seller.id,
        itemized_prices=quote_in.itemized_prices,
        total_amount=quote_in.total_amount,
        estimated_delivery_time=quote_in.estimated_delivery_time,
        status=QuotationStatus.PENDING,
    )
    db.add(quotation)
    db.commit()
    db.refresh(quotation)
    return quotation


def list_quotations_for_requirement(db: Session, requirement_id: UUID) -> List[Quotation]:
    """Retrieves all vendor price quotes submitted for a specific customer requirement."""
    return (
        db.query(Quotation)
        .options(selectinload(Quotation.seller))
        .filter(Quotation.requirement_id == requirement_id)
        .order_by(Quotation.created_at.desc())
        .all()
    )


def get_quotation(db: Session, quotation_id: UUID) -> Optional[Quotation]:
    """Retrieves a single quotation by ID with seller details."""
    return (
        db.query(Quotation)
        .options(selectinload(Quotation.seller))
        .filter(Quotation.id == quotation_id)
        .first()
    )


# =============================================================================
# Order Lifecycle Operations (Accept Quote & Status Tracking)
# =============================================================================
def get_order(db: Session, order_id: UUID) -> Optional[Order]:
    """Retrieves an order record by UUID with relationships preloaded."""
    return (
        db.query(Order)
        .options(
            selectinload(Order.seller),
            selectinload(Order.customer),
            selectinload(Order.quotation),
            selectinload(Order.requirement),
        )
        .filter(Order.id == order_id)
        .first()
    )


def accept_quotation_and_create_order(
    db: Session, quotation_id: UUID, notes: Optional[str] = None
) -> Order:
    """
    Customer selects a specific seller's quote:
    1. Verifies quotation exists and is in 'pending' status.
    2. Marks selected quotation as 'accepted'.
    3. Marks any other competing quotations for the same requirement as 'rejected'.
    4. Transitions requirement status to 'ACCEPTED'.
    5. Creates or updates an Order in 'ACCEPTED' status linked to the quotation.
    """
    quotation = get_quotation(db, quotation_id)
    if not quotation:
        # Fallback: check if quotation_id refers directly to an Order record
        existing_order = db.query(Order).filter(Order.id == quotation_id).first()
        if existing_order:
            existing_order.status = OrderStatus.ACCEPTED.value
            if notes:
                existing_order.notes = notes
            if existing_order.requirement_id:
                req = get_requirement(db, existing_order.requirement_id)
                if req:
                    req.status = RequirementStatus.ACCEPTED.value
            db.commit()
            db.refresh(existing_order)
            return existing_order
        raise ValueError(f"Quotation with ID '{quotation_id}' does not exist.")

    req = get_requirement(db, quotation.requirement_id)
    if not req:
        raise ValueError(f"Requirement with ID '{quotation.requirement_id}' does not exist.")

    # 1. Update selected quotation to accepted
    quotation.status = QuotationStatus.ACCEPTED

    # 2. Reject other quotes for this requirement
    other_quotes = (
        db.query(Quotation)
        .filter(
            Quotation.requirement_id == req.id,
            Quotation.id != quotation.id,
        )
        .all()
    )
    for q in other_quotes:
        q.status = QuotationStatus.REJECTED

    # 3. Transition requirement status to ACCEPTED
    req.status = RequirementStatus.ACCEPTED.value

    # 4. Find existing order or create new order in ACCEPTED status
    existing_order = (
        db.query(Order)
        .filter(
            or_(
                Order.quotation_id == quotation.id,
                Order.requirement_id == req.id,
            )
        )
        .first()
    )

    itemized_quote_payload = {
        "estimated_delivery_time": quotation.estimated_delivery_time,
        "itemized_prices": quotation.itemized_prices,
        "total_amount": float(quotation.total_amount),
        "notes": notes or "",
    }

    if existing_order:
        existing_order.quotation_id = quotation.id
        existing_order.seller_id = quotation.seller_id
        existing_order.quote_amount = quotation.total_amount
        existing_order.status = OrderStatus.ACCEPTED.value
        if notes:
            existing_order.notes = notes
        existing_order.itemized_quote = itemized_quote_payload
        order = existing_order
    else:
        order = Order(
            requirement_id=req.id,
            quotation_id=quotation.id,
            seller_id=quotation.seller_id,
            customer_id=req.customer_id,
            quote_amount=quotation.total_amount,
            status=OrderStatus.ACCEPTED.value,
            notes=notes,
            itemized_quote=itemized_quote_payload,
        )
        db.add(order)

    db.commit()
    db.refresh(order)
    db.refresh(quotation)
    db.refresh(req)
    return order


def update_order_delivery_status(
    db: Session, order_id: UUID, new_status: str, notes: Optional[str] = None
) -> Order:
    """
    Allows a seller to update the delivery status of an order (e.g. to 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED').
    Enforces that:
    1. The order exists.
    2. Status is one of: 'BROADCASTED', 'QUOTED', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED'.
    3. If status transitions to 'COMPLETED', sets completed_at and increments seller completed orders count.
    4. Automatically syncs linked requirement status.
    """
    order = get_order(db, order_id)
    if not order:
        raise ValueError(f"Order with ID '{order_id}' does not exist.")

    normalized_status = new_status.strip().upper()
    valid_statuses = {
        "BROADCASTED",
        "QUOTED",
        "ACCEPTED",
        "OUT_FOR_DELIVERY",
        "COMPLETED",
        "CANCELLED",
    }
    if normalized_status not in valid_statuses:
        raise ValueError(
            f"Invalid order status '{new_status}'. Allowed values are: {', '.join(sorted(valid_statuses))}"
        )

    prev_status = str(order.status).upper()
    order.status = normalized_status
    if notes:
        order.notes = notes

    # Sync linked requirement
    if order.requirement_id:
        req = get_requirement(db, order.requirement_id)
        if req:
            req.status = normalized_status

    # Completion accounting and freemium trigger
    if normalized_status == "COMPLETED" and prev_status != "COMPLETED":
        order.completed_at = func.now()
        seller = get_user(db, order.seller_id)
        if seller:
            seller.completed_orders_count = (seller.completed_orders_count or 0) + 1
            seller.free_orders_remaining = max(0, 2 - seller.completed_orders_count)
            if seller.subscription_status in (SubscriptionStatus.ACTIVE_TRIAL, SubscriptionStatus.TRIAL, "trial", "active_trial"):
                if seller.completed_orders_count >= 2:
                    seller.subscription_status = SubscriptionStatus.PENDING_PAYMENT

    db.commit()
    db.refresh(order)
    return order
