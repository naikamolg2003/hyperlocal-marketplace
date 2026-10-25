"""
SQLAlchemy Core ORM Models for Hyperlocal Marketplace.

Tables:
1. users: Customers, Sellers, Admins with PostGIS geospatial coordinates.
2. categories: Standardized hierarchy of category and sub_category.
3. item_categories: Many-to-Many association enabling items to be categorized across multiple taxonomies.
4. inventory_items: Products sold by sellers with availability toggles and pricing.
5. requirements: Natural language customer demand inputs with structured JSON parsing and status tracking.
"""

import enum
import uuid
from typing import List, Optional
from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from backend.database import Base


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------
class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    SELLER = "seller"
    ADMIN = "admin"


class RequirementStatus(str, enum.Enum):
    BROADCASTED = "BROADCASTED"
    QUOTED = "QUOTED"
    ACCEPTED = "ACCEPTED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    # Backward compatibility
    DRAFT = "draft"
    SUBMITTED = "submitted"
    BROADCASTING = "broadcasting"
    FULFILLED = "fulfilled"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    # Backward compatibility
    ACTIVE_TRIAL = "active_trial"
    PENDING_PAYMENT = "pending_payment"
    TRIAL_EXPIRED = "trial_expired"
    SUBSCRIBED = "subscribed"


class OrderStatus(str, enum.Enum):
    BROADCASTED = "BROADCASTED"
    QUOTED = "QUOTED"
    ACCEPTED = "ACCEPTED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    # Backward compatibility
    PENDING = "pending"
    accepted = "accepted"
    completed = "completed"
    cancelled = "cancelled"


class QuotationStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


# -----------------------------------------------------------------------------
# Association Table: Many-to-Many (InventoryItem <-> Category)
# Allows a single product to appear under multiple categories/sub-categories
# without duplicating the core inventory record.
# -----------------------------------------------------------------------------
item_categories = Table(
    "item_categories",
    Base.metadata,
    Column(
        "item_id",
        PGUUID(as_uuid=True),
        ForeignKey("inventory_items.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column(
        "category_id",
        PGUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
    Column("is_primary", Boolean, default=False, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)


# -----------------------------------------------------------------------------
# 1. Users Table
# -----------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(120), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    role = Column(
        SQLEnum(
            UserRole,
            name="user_role_enum",
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
        ),
        default=UserRole.CUSTOMER,
        nullable=False,
        index=True,
    )

    # Geospatial location for hyperlocal matching (WGS84 EPSG:4326)
    location = Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=True,
        doc="PostGIS Point (longitude, latitude) in EPSG:4326",
    )
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)

    # Freemium Subscription & Order Tracking
    subscription_status = Column(
        String(50),
        default=SubscriptionStatus.TRIAL.value,
        nullable=False,
        index=True,
    )
    completed_orders_count = Column(Integer, default=0, nullable=False)
    free_orders_remaining = Column(Integer, default=2, nullable=False)
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    inventory_items = relationship("InventoryItem", back_populates="seller", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="customer", cascade="all, delete-orphan")
    seller_orders = relationship("Order", foreign_keys="Order.seller_id", back_populates="seller", cascade="all, delete-orphan")
    customer_orders = relationship("Order", foreign_keys="Order.customer_id", back_populates="customer", cascade="all, delete-orphan")
    quotations = relationship("Quotation", foreign_keys="Quotation.seller_id", back_populates="seller", cascade="all, delete-orphan")

    def set_coordinates(self, lat: float, lon: float):
        """Helper to synchronize float lat/lon with PostGIS Geometry POINT(lon, lat)."""
        self.latitude = lat
        self.longitude = lon
        self.location = f"SRID=4326;POINT({lon} {lat})"

    @property
    def can_receive_broadcasts(self) -> bool:
        """Determines if the seller is currently eligible to receive customer demand broadcasts."""
        if self.role != UserRole.SELLER:
            return True
        status_val = str(self.subscription_status).lower() if self.subscription_status else "trial"
        # Active or subscribed
        if status_val in ("active", "subscribed"):
            from datetime import datetime, timezone

            if self.subscription_expires_at and self.subscription_expires_at < datetime.now(timezone.utc):
                return False
            return True
        # Trial: restricted if completed_orders_count > 2
        if status_val in ("trial", "active_trial"):
            return (self.completed_orders_count or 0) <= 2
        return False

    def __repr__(self) -> str:
        return f"<User id={self.id} name='{self.name}' role='{self.role}' phone='{self.phone}'>"


# -----------------------------------------------------------------------------
# 2. Categories Table
# -----------------------------------------------------------------------------
class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("category", "sub_category", name="uq_category_sub_category"),
    )

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    category = Column(String(100), nullable=False, index=True)
    sub_category = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    items = relationship("InventoryItem", secondary=item_categories, back_populates="categories")

    def __repr__(self) -> str:
        return f"<Category id={self.id} category='{self.category}' sub_category='{self.sub_category}'>"


# -----------------------------------------------------------------------------
# 3. Inventory Items Table
# -----------------------------------------------------------------------------
class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    seller_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name = Column(String(255), nullable=False, index=True)
    price = Column(Numeric(10, 2), nullable=False)
    is_available = Column(Boolean, default=True, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    seller = relationship("User", back_populates="inventory_items")
    categories = relationship(
        "Category",
        secondary=item_categories,
        back_populates="items",
        lazy="selectin",
    )

    # Convenience accessors to satisfy single-category queries while supporting M:N
    @property
    def category(self) -> Optional[str]:
        """Returns the primary category name or first associated category."""
        if self.categories:
            return self.categories[0].category
        return None

    @property
    def sub_category(self) -> Optional[str]:
        """Returns the primary sub-category name or first associated sub-category."""
        if self.categories:
            return self.categories[0].sub_category
        return None

    def __repr__(self) -> str:
        return (
            f"<InventoryItem id={self.id} product_name='{self.product_name}' "
            f"price={self.price} is_available={self.is_available}>"
        )


# -----------------------------------------------------------------------------
# 4. Requirements Table (Customer Demand / Natural Language Requests)
# -----------------------------------------------------------------------------
class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    customer_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_text = Column(Text, nullable=False, doc="Natural language customer input")
    structured_json = Column(
        JSONB,
        nullable=True,
        doc="Parsed items, quantities, constraints, and delivery bounds",
    )
    status = Column(
        String(50),
        default="BROADCASTED",
        nullable=False,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    customer = relationship("User", back_populates="requirements")
    quotations = relationship("Quotation", back_populates="requirement", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Requirement id={self.id} customer_id={self.customer_id} status='{self.status}'>"


# -----------------------------------------------------------------------------
# 5. Orders Table (Order Fulfillment & Completed Orders Tracking)
# -----------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    requirement_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quotation_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("quotations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quote_amount = Column(Numeric(10, 2), nullable=False)
    status = Column(
        String(50),
        default="ACCEPTED",
        nullable=False,
        index=True,
    )
    notes = Column(Text, nullable=True)
    itemized_quote = Column(JSONB, nullable=True, doc="Structured line items and delivery estimate")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    seller = relationship("User", foreign_keys=[seller_id], back_populates="seller_orders")
    customer = relationship("User", foreign_keys=[customer_id], back_populates="customer_orders")
    requirement = relationship("Requirement")
    quotation = relationship("Quotation")

    def __repr__(self) -> str:
        return f"<Order id={self.id} seller_id={self.seller_id} amount={self.quote_amount} status='{self.status}'>"


# -----------------------------------------------------------------------------
# 6. Quotations Table (Vendor Price Quotes for Requirements)
# -----------------------------------------------------------------------------
class Quotation(Base):
    __tablename__ = "quotations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    requirement_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    itemized_prices = Column(JSONB, nullable=False, doc="JSON array/object of line item prices")
    total_amount = Column(Numeric(10, 2), nullable=False)
    estimated_delivery_time = Column(String(100), nullable=False)
    status = Column(
        SQLEnum(
            QuotationStatus,
            name="quotation_status_enum",
            values_callable=lambda x: [e.value for e in x],
            native_enum=True,
        ),
        default=QuotationStatus.PENDING,
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    requirement = relationship("Requirement", back_populates="quotations")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="quotations")

    def __repr__(self) -> str:
        return f"<Quotation id={self.id} req_id={self.requirement_id} seller_id={self.seller_id} total={self.total_amount} status='{self.status}'>"
