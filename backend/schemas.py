"""
Pydantic Schemas / DTOs for Hyperlocal Marketplace API.

Provides strict request validation and response serialization models
for Users, Categories, Inventory Items, and Requirements.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models import RequirementStatus, UserRole


# -----------------------------------------------------------------------------
# Base Configuration
# -----------------------------------------------------------------------------
class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------------------------------------------
# Category Schemas
# -----------------------------------------------------------------------------
class CategoryBase(BaseModel):
    category: str = Field(..., min_length=1, max_length=100, description="Primary category name")
    sub_category: Optional[str] = Field(None, max_length=100, description="Optional sub-category name")
    description: Optional[str] = Field(None, description="Detailed category description")


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase, ORMModel):
    id: UUID
    created_at: datetime


# -----------------------------------------------------------------------------
# User Schemas
# -----------------------------------------------------------------------------
class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Full name or business name")
    phone: str = Field(..., min_length=7, max_length=20, description="Unique phone number")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="Role: customer, seller, or admin")
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0, description="WGS84 Latitude")
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0, description="WGS84 Longitude")
    address: Optional[str] = Field(None, description="Human readable physical address")

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, v: str) -> str:
        cleaned = "".join(ch for ch in v if ch.isalnum() or ch == "+")
        if len(cleaned) < 7:
            raise ValueError("Phone number must have at least 7 alphanumeric characters")
        return cleaned


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = Field(None, min_length=7, max_length=20)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    address: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase, ORMModel):
    id: UUID
    is_active: bool
    subscription_status: Optional[str] = "trial"
    completed_orders_count: Optional[int] = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


# -----------------------------------------------------------------------------
# Inventory Item Schemas
# -----------------------------------------------------------------------------
class InventoryItemBase(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255, description="Item or product name")
    price: Decimal = Field(..., gt=0, decimal_places=2, description="Price per unit")
    is_available: bool = Field(default=True, description="Availability toggle for buyers")


class InventoryItemCreate(InventoryItemBase):
    seller_id: UUID = Field(..., description="UUID of the selling merchant")
    category_ids: Optional[List[UUID]] = Field(
        default=None,
        description="Optional list of Category UUIDs to associate with this item",
    )
    category_names: Optional[List[str]] = Field(
        default=None,
        description="Optional list of category/sub-category names to auto-map or create",
    )


class InventoryItemUpdate(BaseModel):
    product_name: Optional[str] = Field(None, min_length=1, max_length=255)
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    is_available: Optional[bool] = None
    category_ids: Optional[List[UUID]] = None
    category_names: Optional[List[str]] = None


class BulkInventoryItemItem(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=255)
    price: Decimal = Field(..., gt=0, decimal_places=2)
    is_available: bool = True
    category_names: Optional[List[str]] = None
    category_ids: Optional[List[UUID]] = None


class BulkInventoryUploadRequest(BaseModel):
    seller_id: UUID = Field(..., description="UUID of the seller")
    items: List[BulkInventoryItemItem] = Field(..., min_length=1, description="List of products to add")


class BulkInventoryUploadResponse(BaseModel):
    success: bool
    total_uploaded: int
    seller_id: UUID
    items: List[Any] = []


class ItemSellerSummary(ORMModel):
    id: UUID
    name: str
    phone: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class InventoryItemResponse(InventoryItemBase, ORMModel):
    id: UUID
    seller_id: UUID
    seller: Optional[ItemSellerSummary] = None
    categories: List[CategoryResponse] = []
    created_at: datetime
    updated_at: Optional[datetime] = None


class NearbyItemResult(BaseModel):
    item: InventoryItemResponse
    distance_meters: float = Field(..., description="Geodesic distance from user in meters")
    distance_km: float = Field(..., description="Geodesic distance formatted in kilometers")


class NearbyItemsResponse(BaseModel):
    count: int
    query_latitude: float
    query_longitude: float
    radius_km: float
    items: List[NearbyItemResult]


# -----------------------------------------------------------------------------
# Requirement Schemas (Customer Demand / Natural Language)
# -----------------------------------------------------------------------------
class RequirementBase(BaseModel):
    raw_text: str = Field(..., min_length=3, description="Natural language customer request")
    structured_json: Optional[Dict[str, Any]] = Field(
        None,
        description="Parsed items, quantities, constraints, and delivery parameters",
    )


class RequirementCreate(RequirementBase):
    customer_id: UUID = Field(..., description="UUID of the demanding customer")
    status: RequirementStatus = Field(
        default=RequirementStatus.SUBMITTED,
        description="Initial status of requirement",
    )


class RequirementUpdate(BaseModel):
    raw_text: Optional[str] = Field(None, min_length=3)
    structured_json: Optional[Dict[str, Any]] = None
    status: Optional[RequirementStatus] = None


class RequirementCustomerSummary(ORMModel):
    id: UUID
    name: str
    phone: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class RequirementResponse(RequirementBase, ORMModel):
    id: UUID
    customer_id: UUID
    status: RequirementStatus
    customer: Optional[RequirementCustomerSummary] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class NearbyRequirementResult(BaseModel):
    requirement: RequirementResponse
    distance_meters: float
    distance_km: float


class NearbyRequirementsResponse(BaseModel):
    count: int
    query_latitude: float
    query_longitude: float
    radius_km: float
    requirements: List[NearbyRequirementResult]


class RequirementSubmitRequest(BaseModel):
    raw_text: str = Field(
        ...,
        min_length=3,
        description="Customer natural language shopping list",
        example="Need 2 packets of milk and some fresh cilantro delivered quickly",
    )
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Customer WGS84 Latitude", example=12.9745)
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Customer WGS84 Longitude", example=77.6350)
    customer_id: Optional[UUID] = Field(None, description="Optional registered customer UUID")
    customer_name: Optional[str] = Field("Guest Customer", description="Optional customer display name")
    customer_phone: Optional[str] = Field(None, description="Optional customer phone number")
    radius_km: float = Field(3.0, gt=0.0, le=50.0, description="Search radius in kilometers (default: 3.0 km)")


class RequirementSubmitResponse(BaseModel):
    requirement_id: UUID
    customer_id: UUID
    raw_text: str
    status: RequirementStatus
    parsed_requirement: Dict[str, Any]
    matching_summary: Dict[str, Any]
    notified_sellers_count: int
    created_at: datetime


# -----------------------------------------------------------------------------
# Billing and Freemium Subscription Schemas
# -----------------------------------------------------------------------------
from backend.models import OrderStatus, QuotationStatus, SubscriptionStatus


class SellerBillingStatusResponse(BaseModel):
    seller_id: UUID
    seller_name: str
    subscription_status: Union[SubscriptionStatus, str]
    completed_orders_count: int
    free_orders_remaining: int
    monthly_platform_fee: float = 1000.0
    can_receive_broadcasts: bool
    subscription_expires_at: Optional[datetime] = None
    status_message: str


class SellerPaymentRequest(BaseModel):
    amount: float = Field(default=1000.0, description="Monthly subscription amount in INR (Rs. 1,000)")
    payment_method: str = Field(default="upi", description="Payment method (upi, card, netbanking)")
    transaction_ref: Optional[str] = Field(None, description="External transaction ID")


class SellerPaymentResponse(BaseModel):
    success: bool
    message: str
    seller_id: UUID
    subscription_status: Union[SubscriptionStatus, str]
    subscription_expires_at: datetime
    can_receive_broadcasts: bool


class OrderCompleteRequest(BaseModel):
    seller_id: UUID
    requirement_id: Optional[UUID] = None
    customer_id: Optional[UUID] = None
    quote_amount: Decimal = Field(..., gt=0, decimal_places=2, description="Completed order total amount (INR)")
    notes: Optional[str] = None


class SellerQuoteSubmitRequest(BaseModel):
    requirement_id: UUID = Field(..., description="UUID of customer requirement")
    seller_id: UUID = Field(..., description="UUID of accepting seller")
    quote_amount: Decimal = Field(..., gt=0, decimal_places=2, description="Total quote amount in INR")
    delivery_estimate_minutes: Optional[int] = Field(20, ge=1, le=240, description="Estimated delivery turnaround time in minutes")
    itemized_items: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed itemized breakdown with prices and quantities")
    notes: Optional[str] = Field(None, description="Seller quote notes, brand substitutions, or delivery details")


class OrderResponse(ORMModel):
    id: UUID
    seller_id: UUID
    customer_id: UUID
    requirement_id: Optional[UUID] = None
    quotation_id: Optional[UUID] = None
    quote_amount: Decimal
    status: Union[OrderStatus, str]
    notes: Optional[str] = None
    itemized_quote: Optional[Dict[str, Any]] = None
    seller: Optional[ItemSellerSummary] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class OrderAcceptQuoteRequest(BaseModel):
    quotation_id: UUID = Field(..., description="UUID of the vendor quotation selected and accepted by customer")
    notes: Optional[str] = Field(None, description="Optional customer instructions or notes for the seller")


class OrderStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        description="Updated lifecycle status: 'BROADCASTED', 'QUOTED', 'ACCEPTED', 'OUT_FOR_DELIVERY', 'COMPLETED', or 'CANCELLED'",
    )
    notes: Optional[str] = Field(None, description="Optional status transition update note or remarks")


class OrderPaymentRequest(BaseModel):
    payment_method: str = Field(default="upi", description="Payment channel: upi, card, netbanking, mock_escrow")
    transaction_ref: Optional[str] = Field(None, description="Transaction ID or simulated payment reference")


class OrderCompleteResultResponse(BaseModel):
    order: OrderResponse
    seller_billing: SellerBillingStatusResponse
    trial_expired_alert: bool


class OrderPaymentSettlementResponse(BaseModel):
    success: bool
    order: OrderResponse
    escrow_settled: bool
    payment_amount: Decimal
    transaction_ref: str
    seller_billing: SellerBillingStatusResponse
    trial_expired_alert: bool
    message: str


# -----------------------------------------------------------------------------
# Quotation Schemas
# -----------------------------------------------------------------------------
class QuotationSubmitRequest(BaseModel):
    requirement_id: UUID = Field(..., description="Target customer requirement UUID")
    seller_id: UUID = Field(..., description="Quoting seller user UUID")
    itemized_prices: Any = Field(..., description="JSON array or object specifying itemized prices/line items")
    total_amount: float = Field(..., gt=0.0, description="Total quoted price in INR")
    estimated_delivery_time: str = Field(..., min_length=1, description="Estimated delivery window (e.g. '20 mins', 'Within 30 mins')")


class QuotationSellerSummary(BaseModel):
    id: UUID
    name: str
    phone: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    subscription_status: Optional[str] = None


class QuotationResponse(ORMModel):
    id: UUID
    requirement_id: UUID
    seller_id: UUID
    itemized_prices: Any
    total_amount: float
    estimated_delivery_time: str
    status: QuotationStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    seller: Optional[QuotationSellerSummary] = None


# -----------------------------------------------------------------------------
# Health and System Schemas
# -----------------------------------------------------------------------------
class HealthCheckResponse(BaseModel):
    status: str
    environment: str
    database: Dict[str, Any]
    counts: Dict[str, int]
    timestamp: datetime
