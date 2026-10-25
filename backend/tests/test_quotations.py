"""
Integration Tests for Vendor Quotation Feature:
1. POST /quotations/submit: Subscribed seller submits a price quote.
2. GET /requirements/{requirement_id}/quotations: Customer views all quotes.
3. Subscription gating: Unsubscribed seller cannot submit quote (403 Forbidden).
4. Validation and 404 handling for nonexistent requirements or sellers.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.models import SubscriptionStatus


class TestVendorQuotations:
    """Test suite for the vendor quotation endpoints."""

    def test_subscribed_seller_submits_quotation(self, test_client: TestClient, make_unique_phone):
        # 1. Register a fresh seller (starts with active_trial, eligible)
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Wakad Kirana Store {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("91"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "address": "Dutta Mandir Road, Wakad, Pune",
        })
        assert seller_res.status_code == 201
        seller = seller_res.json()
        seller_id = seller["id"]

        # 2. Customer submits a requirement
        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need 2 packets of milk and sourdough bread",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("92"),
            "radius_km": 3.0,
        })
        assert req_res.status_code == 201
        requirement = req_res.json()
        requirement_id = requirement["requirement_id"]

        # 3. Subscribed seller submits a quotation via POST /quotations/submit
        itemized_prices = [
            {"product_name": "Pasteurized Milk 500ml", "quantity": "2 pkts", "unit_price": 35.0, "total": 70.0},
            {"product_name": "Sourdough Bread 400g", "quantity": "1 loaf", "unit_price": 120.0, "total": 120.0},
        ]
        quote_payload = {
            "requirement_id": requirement_id,
            "seller_id": seller_id,
            "itemized_prices": itemized_prices,
            "total_amount": 190.0,
            "estimated_delivery_time": "15-20 mins",
        }

        quote_res = test_client.post("/quotations/submit", json=quote_payload)
        assert quote_res.status_code == 201, f"Failed to submit quote: {quote_res.text}"
        quote_data = quote_res.json()

        assert quote_data["requirement_id"] == requirement_id
        assert quote_data["seller_id"] == seller_id
        assert float(quote_data["total_amount"]) == 190.0
        assert quote_data["estimated_delivery_time"] == "15-20 mins"
        assert quote_data["status"] == "pending"
        assert len(quote_data["itemized_prices"]) == 2

        # 4. Customer views all quotes via GET /requirements/{requirement_id}/quotations
        quotes_list_res = test_client.get(f"/requirements/{requirement_id}/quotations")
        assert quotes_list_res.status_code == 200
        quotes = quotes_list_res.json()
        assert len(quotes) >= 1

        matched_quote = next((q for q in quotes if q["id"] == quote_data["id"]), None)
        assert matched_quote is not None
        assert matched_quote["seller"]["name"] == seller["name"]
        assert matched_quote["seller"]["phone"] == seller["phone"]
        assert float(matched_quote["total_amount"]) == 190.0

    def test_unsubscribed_seller_cannot_submit_quotation(self, test_client: TestClient, make_unique_phone):
        """A seller whose trial expired (pending_payment) is blocked from submitting quotations."""
        # 1. Create seller
        s_res = test_client.post("/api/v1/users", json={
            "name": f"Trial Expired Vendor {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("93"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = s_res.json()["id"]

        # 2. Simulate 2 completed orders to exhaust trial quota and lock seller
        for i in range(2):
            req_tmp = test_client.post("/requirements/submit", json={
                "raw_text": f"Trial order {i+1}",
                "latitude": 18.5987,
                "longitude": 73.7660,
                "customer_phone": make_unique_phone("94"),
            }).json()

            quote_tmp = test_client.post("/api/v1/orders/quote", json={
                "requirement_id": req_tmp["requirement_id"],
                "seller_id": seller_id,
                "quote_amount": 50.0,
                "delivery_estimate_minutes": 10,
                "itemized_items": [{"item_name": "Test Item", "price": 50.0}],
            }).json()

            test_client.post(f"/api/v1/orders/{quote_tmp['id']}/pay", json={
                "payment_method": "upi",
                "transaction_ref": f"TXN-EXPIRE-{i}",
            })

        # Verify seller billing status is now 'pending_payment'
        billing_status = test_client.get(f"/api/v1/billing/seller/{seller_id}/status").json()
        assert billing_status["subscription_status"] == "pending_payment"
        assert billing_status["can_receive_broadcasts"] is False

        # 3. Create a new requirement
        new_req = test_client.post("/requirements/submit", json={
            "raw_text": "Need fresh apples 1 kg",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("95"),
        }).json()

        # 4. Attempt to submit quotation - MUST be rejected with HTTP 403 Forbidden
        blocked_quote_res = test_client.post("/quotations/submit", json={
            "requirement_id": new_req["requirement_id"],
            "seller_id": seller_id,
            "itemized_prices": [{"item": "Apples", "price": 100.0}],
            "total_amount": 100.0,
            "estimated_delivery_time": "15 mins",
        })
        assert blocked_quote_res.status_code == 403, f"Expected 403 Forbidden, got: {blocked_quote_res.status_code}"
        assert "not subscribed" in blocked_quote_res.json()["detail"].lower() or "expired" in blocked_quote_res.json()["detail"].lower()

        # 5. Seller pays Rs. 1,000 monthly fee -> becomes subscribed -> can submit quotation
        pay_fee_res = test_client.post(f"/api/v1/billing/seller/{seller_id}/pay", json={
            "amount": 1000.0,
            "payment_method": "upi",
        })
        assert pay_fee_res.status_code == 200
        assert pay_fee_res.json()["subscription_status"] == "subscribed"

        # 6. Retry submitting quotation - now SUCCEEDS with HTTP 201
        allowed_quote_res = test_client.post("/quotations/submit", json={
            "requirement_id": new_req["requirement_id"],
            "seller_id": seller_id,
            "itemized_prices": [{"item": "Apples", "price": 100.0}],
            "total_amount": 100.0,
            "estimated_delivery_time": "15 mins",
        })
        assert allowed_quote_res.status_code == 201
        assert allowed_quote_res.json()["status"] == "pending"

    def test_quotation_not_found_handling(self, test_client: TestClient, make_unique_phone):
        """Verifies 404 returned when requirement or seller does not exist."""
        random_id = str(uuid.uuid4())

        # Create valid seller
        s_res = test_client.post("/api/v1/users", json={
            "name": "Sample Store",
            "phone": make_unique_phone("96"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = s_res.json()["id"]

        # Invalid requirement ID
        res1 = test_client.post("/quotations/submit", json={
            "requirement_id": random_id,
            "seller_id": seller_id,
            "itemized_prices": [{"item": "Milk", "price": 30.0}],
            "total_amount": 30.0,
            "estimated_delivery_time": "10 mins",
        })
        assert res1.status_code == 404

        # Nonexistent requirement GET
        res2 = test_client.get(f"/requirements/{random_id}/quotations")
        assert res2.status_code == 404
