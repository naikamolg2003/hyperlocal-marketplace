"""
Integration Tests for Order Acceptance and Status Tracking Lifecycle:
1. POST /orders/accept-quote: Customer accepts a seller's quote, transitioning order & requirement to 'ACCEPTED'.
2. Competing quotes rejection: Competing vendor quotes are transitioned to 'rejected'.
3. PATCH /orders/{order_id}/status: Seller updates delivery status (e.g., 'OUT_FOR_DELIVERY', 'COMPLETED', 'CANCELLED').
4. Completed status triggers seller completed orders counter and freemium subscription checks.
5. Error handling and 400/404 validations.
"""

import uuid
import pytest
from fastapi.testclient import TestClient


class TestOrderLifecycle:
    """Test suite for order acceptance and status tracking lifecycle."""

    def test_order_accept_quote_and_competing_rejection(self, test_client: TestClient, make_unique_phone):
        # 1. Register 2 sellers
        seller1_res = test_client.post("/api/v1/users", json={
            "name": f"Fast Grocery {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("91"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "address": "Wakad Main Rd, Pune",
        })
        assert seller1_res.status_code == 201
        seller1_id = seller1_res.json()["id"]

        seller2_res = test_client.post("/api/v1/users", json={
            "name": f"Quick Mart {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("92"),
            "role": "seller",
            "latitude": 18.5990,
            "longitude": 73.7665,
            "address": "Datta Mandir Rd, Pune",
        })
        assert seller2_res.status_code == 201
        seller2_id = seller2_res.json()["id"]

        # 2. Customer submits requirement
        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need fresh bread and farm butter",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("93"),
            "radius_km": 3.0,
        })
        assert req_res.status_code == 201
        requirement_id = req_res.json()["requirement_id"]

        # 3. Both sellers submit quotes
        quote1_res = test_client.post("/quotations/submit", json={
            "requirement_id": requirement_id,
            "seller_id": seller1_id,
            "itemized_prices": [
                {"product_name": "Sourdough Bread", "price": 80.0},
                {"product_name": "Farm Butter 100g", "price": 60.0},
            ],
            "total_amount": 140.0,
            "estimated_delivery_time": "15 mins",
        })
        assert quote1_res.status_code == 201
        quote1_id = quote1_res.json()["id"]

        quote2_res = test_client.post("/quotations/submit", json={
            "requirement_id": requirement_id,
            "seller_id": seller2_id,
            "itemized_prices": [
                {"product_name": "Sourdough Bread", "price": 75.0},
                {"product_name": "Farm Butter 100g", "price": 70.0},
            ],
            "total_amount": 145.0,
            "estimated_delivery_time": "25 mins",
        })
        assert quote2_res.status_code == 201
        quote2_id = quote2_res.json()["id"]

        # 4. Customer accepts Seller 1's quote via POST /orders/accept-quote
        accept_res = test_client.post("/orders/accept-quote", json={
            "quotation_id": quote1_id,
            "notes": "Please deliver to 2nd floor flat 204",
        })
        assert accept_res.status_code == 200, f"Accept quote failed: {accept_res.text}"
        order = accept_res.json()

        order_id = order["id"]
        assert order["status"] == "ACCEPTED"
        assert order["seller_id"] == seller1_id
        assert order["quotation_id"] == quote1_id
        assert float(order["quote_amount"]) == 140.0
        assert order["notes"] == "Please deliver to 2nd floor flat 204"

        # 5. Verify the requirement status is now 'ACCEPTED'
        req_check = test_client.get(f"/api/v1/requirements/{requirement_id}")
        assert req_check.status_code == 200
        assert req_check.json()["status"] == "ACCEPTED"

        # 6. Verify seller 1's quote is 'accepted' and seller 2's quote is 'rejected'
        quotes_list_res = test_client.get(f"/requirements/{requirement_id}/quotations")
        assert quotes_list_res.status_code == 200
        quotes_list = {q["id"]: q["status"] for q in quotes_list_res.json()}
        assert quotes_list[quote1_id] == "accepted"
        assert quotes_list[quote2_id] == "rejected"

        # 7. Seller 1 updates status to 'OUT_FOR_DELIVERY' via PATCH /orders/{order_id}/status
        delivery_res = test_client.patch(f"/orders/{order_id}/status", json={
            "status": "OUT_FOR_DELIVERY",
            "notes": "Delivery executive dispatched on scooter",
        })
        assert delivery_res.status_code == 200
        delivery_order = delivery_res.json()
        assert delivery_order["status"] == "OUT_FOR_DELIVERY"
        assert delivery_order["notes"] == "Delivery executive dispatched on scooter"

        # Verify linked requirement also updated to 'OUT_FOR_DELIVERY'
        req_check2 = test_client.get(f"/api/v1/requirements/{requirement_id}")
        assert req_check2.json()["status"] == "OUT_FOR_DELIVERY"

        # 8. Seller 1 updates status to 'COMPLETED' via PATCH /orders/{order_id}/status
        completed_res = test_client.patch(f"/orders/{order_id}/status", json={
            "status": "COMPLETED",
            "notes": "Package safely handed to customer",
        })
        assert completed_res.status_code == 200
        completed_order = completed_res.json()
        assert completed_order["status"] == "COMPLETED"
        assert completed_order["completed_at"] is not None

        # Verify linked requirement updated to 'COMPLETED'
        req_check3 = test_client.get(f"/api/v1/requirements/{requirement_id}")
        assert req_check3.json()["status"] == "COMPLETED"

        # Verify seller 1's completed order counter incremented to 1
        billing_res = test_client.get(f"/api/v1/billing/seller/{seller1_id}/status")
        assert billing_res.status_code == 200
        billing_data = billing_res.json()
        assert billing_data["completed_orders_count"] == 1
        assert billing_data["free_orders_remaining"] == 1

    def test_order_cancellation_lifecycle(self, test_client: TestClient, make_unique_phone):
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Cancel Mart {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("94"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = seller_res.json()["id"]

        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need organic brown eggs",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("95"),
            "radius_km": 3.0,
        })
        req_id = req_res.json()["requirement_id"]

        quote_res = test_client.post("/quotations/submit", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "itemized_prices": [{"product_name": "Organic Eggs 6-pack", "price": 90.0}],
            "total_amount": 90.0,
            "estimated_delivery_time": "20 mins",
        })
        quote_id = quote_res.json()["id"]

        accept_res = test_client.post("/orders/accept-quote", json={"quotation_id": quote_id})
        assert accept_res.status_code == 200
        order_id = accept_res.json()["id"]

        # Cancel the order
        cancel_res = test_client.patch(f"/orders/{order_id}/status", json={
            "status": "CANCELLED",
            "notes": "Out of fresh eggs, cancelled by merchant",
        })
        assert cancel_res.status_code == 200
        cancelled_order = cancel_res.json()
        assert cancelled_order["status"] == "CANCELLED"
        assert cancelled_order["notes"] == "Out of fresh eggs, cancelled by merchant"

    def test_invalid_status_transition_returns_400(self, test_client: TestClient, make_unique_phone):
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Validation Store {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("96"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = seller_res.json()["id"]

        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need fresh apples 1 kg",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("97"),
            "radius_km": 3.0,
        })
        req_id = req_res.json()["requirement_id"]

        quote_res = test_client.post("/quotations/submit", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "itemized_prices": [{"product_name": "Shimla Apple 1kg", "price": 180.0}],
            "total_amount": 180.0,
            "estimated_delivery_time": "20 mins",
        })
        quote_id = quote_res.json()["id"]

        accept_res = test_client.post("/orders/accept-quote", json={"quotation_id": quote_id})
        order_id = accept_res.json()["id"]

        # Send invalid status
        bad_status_res = test_client.patch(f"/orders/{order_id}/status", json={
            "status": "NONEXISTENT_STATUS",
        })
        assert bad_status_res.status_code == 400
        assert "Invalid order status" in bad_status_res.json()["detail"]

    def test_accept_nonexistent_quotation_returns_404(self, test_client: TestClient):
        random_id = str(uuid.uuid4())
        res = test_client.post("/orders/accept-quote", json={"quotation_id": random_id})
        assert res.status_code == 404
        assert "does not exist" in res.json()["detail"]

    def test_update_status_nonexistent_order_returns_404(self, test_client: TestClient):
        random_id = str(uuid.uuid4())
        res = test_client.patch(f"/orders/{random_id}/status", json={"status": "OUT_FOR_DELIVERY"})
        assert res.status_code == 404
        assert "does not exist" in res.json()["detail"]

    def test_api_v1_alias_routes_work(self, test_client: TestClient, make_unique_phone):
        seller_res = test_client.post("/api/v1/users", json={
            "name": f"Alias Test Store {uuid.uuid4().hex[:4]}",
            "phone": make_unique_phone("98"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = seller_res.json()["id"]

        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need curd 500g",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "customer_phone": make_unique_phone("99"),
            "radius_km": 3.0,
        })
        req_id = req_res.json()["requirement_id"]

        quote_res = test_client.post("/api/v1/quotations/submit", json={
            "requirement_id": req_id,
            "seller_id": seller_id,
            "itemized_prices": [{"product_name": "Curd 500g", "price": 40.0}],
            "total_amount": 40.0,
            "estimated_delivery_time": "10 mins",
        })
        quote_id = quote_res.json()["id"]

        # Test POST /api/v1/orders/accept-quote
        accept_res = test_client.post("/api/v1/orders/accept-quote", json={"quotation_id": quote_id})
        assert accept_res.status_code == 200
        order_id = accept_res.json()["id"]

        # Test PATCH /api/v1/orders/{order_id}/status
        status_res = test_client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "OUT_FOR_DELIVERY"})
        assert status_res.status_code == 200
        assert status_res.json()["status"] == "OUT_FOR_DELIVERY"

        # Test GET /api/v1/orders/{order_id}
        get_res = test_client.get(f"/api/v1/orders/{order_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == order_id
