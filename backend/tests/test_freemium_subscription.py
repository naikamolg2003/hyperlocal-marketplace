"""
Integration and Unit Tests for the Rs. 1,000 Monthly Freemium Subscription Rule:
1. Seller model fields: subscription_status ('trial', 'active', 'expired') and completed_orders_count.
2. Helper function / middleware: check_seller_subscription_access and enforce_seller_broadcast_access.
3. Access restriction: If completed_orders_count > 2 and subscription_status != 'active',
   restrict viewing or responding to requirement broadcasts, returning a message requiring
   the Rs. 1,000 monthly platform fee payment to continue.
4. Payment restoration: Once subscription_status becomes 'active', access is restored.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.models import SubscriptionStatus, User, UserRole
from backend.subscription import (
    SUBSCRIPTION_RESTRICTION_MESSAGE,
    check_seller_subscription_access,
    enforce_seller_broadcast_access,
)


class TestFreemiumSubscriptionEnforcement:
    """Test suite for Rs. 1,000 monthly freemium subscription enforcement."""

    def test_helper_function_evaluation_states(self):
        """Unit test the check_seller_subscription_access helper function across all states."""
        # Case 1: Fresh trial seller (0 completed orders) -> Allowed
        seller_fresh = User(
            id=uuid.uuid4(),
            name="Fresh Seller",
            phone="+919800000001",
            role=UserRole.SELLER,
            subscription_status="trial",
            completed_orders_count=0,
        )
        allowed, msg = check_seller_subscription_access(seller_fresh)
        assert allowed is True
        assert "Trial active" in msg

        # Case 2: Trial seller with 2 completed orders -> Allowed (threshold is > 2)
        seller_two_orders = User(
            id=uuid.uuid4(),
            name="Two Orders Seller",
            phone="+919800000002",
            role=UserRole.SELLER,
            subscription_status="trial",
            completed_orders_count=2,
        )
        allowed, msg = check_seller_subscription_access(seller_two_orders)
        assert allowed is True

        # Case 3: Seller with completed_orders_count > 2 and subscription_status != 'active' -> RESTRICTED
        seller_over_limit = User(
            id=uuid.uuid4(),
            name="Over Limit Seller",
            phone="+919800000003",
            role=UserRole.SELLER,
            subscription_status="trial",
            completed_orders_count=3,
        )
        allowed, msg = check_seller_subscription_access(seller_over_limit)
        assert allowed is False
        assert "completed_orders_count > 2" in msg
        assert "subscription_status != 'active'" in msg
        assert "Rs. 1,000 monthly platform fee payment to continue" in msg

        # Case 4: Seller with expired trial -> RESTRICTED
        seller_expired = User(
            id=uuid.uuid4(),
            name="Expired Seller",
            phone="+919800000004",
            role=UserRole.SELLER,
            subscription_status="expired",
            completed_orders_count=1,
        )
        allowed, msg = check_seller_subscription_access(seller_expired)
        assert allowed is False
        assert "Rs. 1,000 monthly platform fee payment to continue" in msg

        # Case 5: Active paid seller with completed_orders_count > 2 -> ALLOWED
        seller_active = User(
            id=uuid.uuid4(),
            name="Active Paid Seller",
            phone="+919800000005",
            role=UserRole.SELLER,
            subscription_status="active",
            completed_orders_count=10,
        )
        allowed, msg = check_seller_subscription_access(seller_active)
        assert allowed is True
        assert "active" in msg.lower()

    def test_seller_attempt_to_view_broadcasts_restricted_after_two_orders(
        self, test_client: TestClient, db_session, make_unique_phone
    ):
        """
        When a seller with completed_orders_count > 2 and subscription_status != 'active'
        attempts to view requirement broadcasts, access is restricted with HTTP 403 Forbidden.
        """
        # 1. Register a seller in trial
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Broadcast View Seller {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("91"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        assert seller_res.status_code == 201
        seller = seller_res.json()
        seller_id = seller["id"]
        assert seller["subscription_status"] in ("trial", "active_trial")
        assert seller["completed_orders_count"] == 0

        # 2. Seller CAN view broadcasts during active trial
        view_res1 = test_client.get(
            f"/api/v1/requirements/nearby?lat=18.5987&lon=73.7660&radius_km=3.0&seller_id={seller_id}"
        )
        assert view_res1.status_code == 200

        view_res2 = test_client.get(f"/requirements/broadcasts/seller/{seller_id}")
        assert view_res2.status_code == 200

        # 3. Simulate seller exceeding trial (> 2 completed orders without paying platform fee)
        db_seller = db_session.query(User).filter(User.id == seller_id).first()
        db_seller.completed_orders_count = 3
        db_seller.subscription_status = "trial"  # Not active
        db_session.commit()

        # 4. Attempt to view broadcasts via GET /requirements/nearby?seller_id=... -> HTTP 403 Forbidden
        blocked_view = test_client.get(
            f"/api/v1/requirements/nearby?lat=18.5987&lon=73.7660&radius_km=3.0&seller_id={seller_id}"
        )
        assert blocked_view.status_code == 403
        detail = blocked_view.json()["detail"]
        assert "completed_orders_count > 2" in detail or "exceeds" in detail.lower()
        assert "Rs. 1,000 monthly platform fee payment to continue" in detail

        # 5. Attempt to view broadcasts via GET /requirements/broadcasts/seller/{seller_id} -> HTTP 403 Forbidden
        blocked_feed = test_client.get(f"/requirements/broadcasts/seller/{seller_id}")
        assert blocked_feed.status_code == 403
        detail_feed = blocked_feed.json()["detail"]
        assert "Rs. 1,000 monthly platform fee payment to continue" in detail_feed

        # 6. Seller pays Rs. 1,000 monthly platform fee -> Access is restored
        pay_res = test_client.post(f"/api/v1/billing/seller/{seller_id}/pay", json={
            "amount": 1000.0,
            "payment_method": "upi",
        })
        assert pay_res.status_code == 200

        # Now seller CAN view requirement broadcasts again
        unblocked_view = test_client.get(
            f"/api/v1/requirements/nearby?lat=18.5987&lon=73.7660&radius_km=3.0&seller_id={seller_id}"
        )
        assert unblocked_view.status_code == 200

        unblocked_feed = test_client.get(f"/requirements/broadcasts/seller/{seller_id}")
        assert unblocked_feed.status_code == 200

    def test_seller_attempt_to_respond_to_broadcast_restricted_after_two_orders(
        self, test_client: TestClient, db_session, make_unique_phone
    ):
        """
        When a seller with completed_orders_count > 2 and subscription_status != 'active'
        attempts to respond to a requirement with a quote, access is restricted with HTTP 403 Forbidden.
        """
        # 1. Register seller
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Quote Quota Seller {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("92"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = seller_res.json()["id"]

        # 2. Customer submits a requirement broadcast
        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need sunflower oil 1L",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("93"),
            "radius_km": 3.0,
        })
        req_id = req_res.json()["requirement_id"]

        # 3. Update seller to completed_orders_count = 3 with subscription_status = 'trial'
        db_seller = db_session.query(User).filter(User.id == seller_id).first()
        db_seller.completed_orders_count = 3
        db_seller.subscription_status = "trial"
        db_session.commit()

        # 4. Attempt to respond via POST /quotations/submit -> MUST fail with 403
        blocked_quote = test_client.post("/quotations/submit", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "itemized_prices": [{"product_name": "Sunflower Oil", "price": 140.0}],
            "total_amount": 140.0,
            "estimated_delivery_time": "15 mins",
        })
        assert blocked_quote.status_code == 403
        assert "Rs. 1,000 monthly platform fee payment to continue" in blocked_quote.json()["detail"]

        # 5. Attempt to respond via POST /api/v1/orders/quote -> MUST fail with 403
        blocked_order_quote = test_client.post("/api/v1/orders/quote", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "quote_amount": 140.0,
            "delivery_estimate_minutes": 15,
            "notes": "Sunflower oil delivery",
        })
        assert blocked_order_quote.status_code == 403
        assert "Rs. 1,000 monthly platform fee payment to continue" in blocked_order_quote.json()["detail"]

        # 6. Seller pays Rs. 1,000 subscription fee
        test_client.post(f"/api/v1/billing/seller/{seller_id}/pay", json={
            "amount": 1000.0,
            "payment_method": "upi",
        })

        # 7. Responding is now permitted
        allowed_quote = test_client.post("/quotations/submit", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "itemized_prices": [{"product_name": "Sunflower Oil", "price": 140.0}],
            "total_amount": 140.0,
            "estimated_delivery_time": "15 mins",
        })
        assert allowed_quote.status_code == 201
        assert float(allowed_quote.json()["total_amount"]) == 140.0

    def test_explicit_expired_subscription_blocks_broadcast_access(
        self, test_client: TestClient, db_session, make_unique_phone
    ):
        """A seller whose subscription_status is explicitly 'expired' is restricted from viewing or responding."""
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Explicit Expired Seller {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("94"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = seller_res.json()["id"]

        # Mark seller as 'expired'
        db_seller = db_session.query(User).filter(User.id == seller_id).first()
        db_seller.subscription_status = "expired"
        db_session.commit()

        # View broadcast attempt
        view_res = test_client.get(f"/requirements/broadcasts/seller/{seller_id}")
        assert view_res.status_code == 403
        assert "Rs. 1,000 monthly platform fee payment to continue" in view_res.json()["detail"]
