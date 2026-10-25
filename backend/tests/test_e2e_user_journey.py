"""
End-to-End User Journey Integration Tests.

Simulates the complete Hyperlocal Reverse-Marketplace lifecycle:
a. Customer submits a natural language requirement with GPS coordinates.
b. AI parser successfully converts it to a structured JSON shopping list.
c. PostGIS spatial query correctly filters sellers within the 3 km radius and excludes distant sellers.
d. Seller accepts the order, submits an itemized quote/bill.
e. Customer approves and settles payment via Mock Escrow Gateway.
f. Successful order increments counter and triggers the freemium billing milestone upon the 2nd order.
"""

import time
import uuid
import pytest
from fastapi.testclient import TestClient


class TestEndToEndUserJourney:
    """Complete customer-to-seller-to-payment integration workflow."""

    def test_full_user_journey_e2e(self, test_client: TestClient, make_unique_phone):
        # ---------------------------------------------------------------------
        # 1. Setup: Register sellers at different distances from customer pin
        # ---------------------------------------------------------------------
        # Customer Pin: Indiranagar, Bangalore (12.9745, 77.6350)
        customer_lat = 12.9745
        customer_lon = 77.6350

        # Seller 1 (Nearby - ~650m away): 100 Feet Road, Indiranagar (12.9784, 77.6408)
        seller_near_phone = make_unique_phone("91")
        seller_near_res = test_client.post("/api/v1/users", json={
            "name": f"Indiranagar Fresh Mart {uuid.uuid4().hex[:4]}",
            "phone": seller_near_phone,
            "role": "seller",
            "latitude": 12.9784,
            "longitude": 77.6408,
            "address": "100 Feet Road, Indiranagar, Bangalore",
        })
        assert seller_near_res.status_code == 201
        seller_near = seller_near_res.json()
        seller_near_id = seller_near["id"]

        # Seller 2 (Far Away - ~11.5 km away in Whitefield): (12.9698, 77.7499)
        seller_far_phone = make_unique_phone("92")
        seller_far_res = test_client.post("/api/v1/users", json={
            "name": f"Whitefield Mega Hypermarket {uuid.uuid4().hex[:4]}",
            "phone": seller_far_phone,
            "role": "seller",
            "latitude": 12.9698,
            "longitude": 77.7499,
            "address": "ITPB Main Road, Whitefield, Bangalore",
        })
        assert seller_far_res.status_code == 201
        seller_far = seller_far_res.json()
        seller_far_id = seller_far["id"]

        # ---------------------------------------------------------------------
        # 2. Stock inventory for both sellers
        # ---------------------------------------------------------------------
        # Add Milk and Cilantro to Nearby Seller
        test_client.post("/api/v1/items/bulk", json={
            "seller_id": seller_near_id,
            "items": [
                {
                    "product_name": "Organic Whole Milk 500ml",
                    "price": 34.0,
                    "is_available": True,
                    "category_names": ["Dairy", "Essentials"],
                },
                {
                    "product_name": "Fresh Coriander Cilantro Leaves",
                    "price": 15.0,
                    "is_available": True,
                    "category_names": ["Produce", "Vegetables"],
                },
            ],
        })

        # Add same items to Far Seller (to prove spatial exclusion, not inventory exclusion)
        test_client.post("/api/v1/items/bulk", json={
            "seller_id": seller_far_id,
            "items": [
                {
                    "product_name": "Organic Whole Milk 500ml",
                    "price": 32.0,
                    "is_available": True,
                    "category_names": ["Dairy", "Essentials"],
                },
                {
                    "product_name": "Fresh Coriander Cilantro Leaves",
                    "price": 12.0,
                    "is_available": True,
                    "category_names": ["Produce", "Vegetables"],
                },
            ],
        })

        # ---------------------------------------------------------------------
        # 3. Step A & B: Customer submits Natural Language requirement -> AI Parsed
        # ---------------------------------------------------------------------
        raw_prompt = "Need 2 packets of milk and fresh cilantro delivered quickly"
        submit_res = test_client.post("/requirements/submit", json={
            "raw_text": raw_prompt,
            "latitude": customer_lat,
            "longitude": customer_lon,
            "customer_name": "Aditi Rao",
            "customer_phone": make_unique_phone("95"),
            "radius_km": 3.0,
        })
        assert submit_res.status_code == 201, f"Demand submission failed: {submit_res.text}"
        demand = submit_res.json()
        requirement_id = demand["requirement_id"]

        # Validate AI Parsing structure
        parsed = demand["parsed_requirement"]
        assert len(parsed["items"]) >= 2
        item_names = [it["product_name"].lower() for it in parsed["items"]]
        assert any("milk" in name for name in item_names)
        assert any("cilantro" in name or "coriander" in name for name in item_names)
        assert parsed["urgency"] in ("high", "immediate", "medium")

        # ---------------------------------------------------------------------
        # 4. Step C: PostGIS 3 km Spatial Query Filtering
        # ---------------------------------------------------------------------
        matching = demand["matching_summary"]
        sellers_in_radius = matching["sellers"]
        seller_ids_in_radius = [s["seller_id"] for s in sellers_in_radius]

        # Assert PostGIS correctly INCLUDED the seller at ~650m
        assert seller_near_id in seller_ids_in_radius, "Nearby seller within 3km MUST be included"

        # Assert PostGIS strictly EXCLUDED the seller at 11.5 km (Whitefield)
        assert seller_far_id not in seller_ids_in_radius, "Far seller (>3km) MUST be strictly excluded by PostGIS ST_DWithin"

        # Verify matched seller metadata and full match status
        matched_near = next(s for s in sellers_in_radius if s["seller_id"] == seller_near_id)
        assert matched_near["distance_meters"] < 3000.0
        assert matched_near["fulfillment_percentage"] > 0.0

        # ---------------------------------------------------------------------
        # 5. Step D: Seller accepts order & submits itemized quote
        # ---------------------------------------------------------------------
        quote_payload = {
            "requirement_id": requirement_id,
            "seller_id": seller_near_id,
            "quote_amount": 83.0,
            "delivery_estimate_minutes": 20,
            "itemized_items": [
                {"item_name": "Organic Whole Milk 500ml", "quantity": "2 pkts", "price": 34.0, "total": 68.0},
                {"item_name": "Fresh Coriander Cilantro Leaves", "quantity": "1 bunch", "price": 15.0, "total": 15.0},
            ],
            "notes": "Packed fresh from morning batch. Driver ready.",
        }
        quote_res = test_client.post("/api/v1/orders/quote", json=quote_payload)
        assert quote_res.status_code == 201, f"Quote submission failed: {quote_res.text}"
        quote_data = quote_res.json()
        order_id = quote_data["id"]
        assert quote_data["status"] == "pending"
        assert float(quote_data["quote_amount"]) == 83.0

        # Customer retrieves quotes list for requirement
        quotes_list_res = test_client.get(f"/api/v1/orders/requirement/{requirement_id}")
        assert quotes_list_res.status_code == 200
        quotes_list = quotes_list_res.json()
        assert len(quotes_list) >= 1
        assert any(q["id"] == order_id for q in quotes_list)

        # ---------------------------------------------------------------------
        # 6. Step E: Customer approves & pays via Mock Escrow Settlement
        # ---------------------------------------------------------------------
        pay_res = test_client.post(f"/api/v1/orders/{order_id}/pay", json={
            "payment_method": "upi",
            "transaction_ref": f"TXN-ESCROW-TEST-{int(time.time())}",
        })
        assert pay_res.status_code == 200, f"Escrow payment failed: {pay_res.text}"
        pay_data = pay_res.json()
        assert pay_data["success"] is True
        assert pay_data["escrow_settled"] is True
        assert pay_data["order"]["status"].upper() == "COMPLETED"

        # Verify completed order counter incremented to 1 (1 trial order remaining)
        billing_info = pay_data["seller_billing"]
        assert billing_info["completed_orders_count"] == 1
        assert billing_info["free_orders_remaining"] == 1
        assert billing_info["subscription_status"] in ("trial", "active_trial")
        assert pay_data["trial_expired_alert"] is False

        # ---------------------------------------------------------------------
        # 7. Step F: Second order triggers Freemium Milestone ('pending_payment')
        # ---------------------------------------------------------------------
        # Create 2nd customer demand
        req2_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need fresh cilantro 1 bunch",
            "latitude": customer_lat,
            "longitude": customer_lon,
            "customer_phone": make_unique_phone("96"),
            "radius_km": 3.0,
        })
        req2_id = req2_res.json()["requirement_id"]

        # Seller submits quote for order 2
        quote2_res = test_client.post("/api/v1/orders/quote", json={
            "requirement_id": req2_id,
            "seller_id": seller_near_id,
            "quote_amount": 15.0,
            "delivery_estimate_minutes": 15,
            "itemized_items": [{"item_name": "Fresh Coriander Cilantro Leaves", "quantity": "1 bunch", "price": 15.0}],
            "notes": "Express delivery",
        })
        order2_id = quote2_res.json()["id"]

        # Customer settles payment for order 2
        pay2_res = test_client.post(f"/api/v1/orders/{order2_id}/pay", json={
            "payment_method": "card",
            "transaction_ref": f"TXN-ESCROW-CARD-{int(time.time())}",
        })
        assert pay2_res.status_code == 200
        pay2_data = pay2_res.json()

        # Assert 2nd completed order triggers freemium milestone
        billing2 = pay2_data["seller_billing"]
        assert billing2["completed_orders_count"] == 2
        assert billing2["free_orders_remaining"] == 0
        assert billing2["subscription_status"] == "pending_payment"
        assert pay2_data["trial_expired_alert"] is True
        assert billing2["can_receive_broadcasts"] is False

        # ---------------------------------------------------------------------
        # 8. Step G: Verify Broadcast Gating & Subscription Fee Payment
        # ---------------------------------------------------------------------
        # Submit a 3rd requirement - the locked seller should NOT be counted in notified sellers
        req3_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need whole milk 500ml",
            "latitude": customer_lat,
            "longitude": customer_lon,
            "customer_phone": make_unique_phone("97"),
            "radius_km": 3.0,
        })
        req3_matching = req3_res.json()["matching_summary"]
        seller_near_in_3 = next((s for s in req3_matching["sellers"] if s["seller_id"] == seller_near_id), None)
        assert seller_near_in_3 is not None
        assert seller_near_in_3["can_receive_broadcasts"] is False

        # Seller settles Rs. 1000 platform fee to unlock
        unlock_res = test_client.post(f"/api/v1/billing/seller/{seller_near_id}/pay", json={
            "amount": 1000.0,
            "payment_method": "upi",
        })
        assert unlock_res.status_code == 200
        unlock_data = unlock_res.json()
        assert unlock_data["subscription_status"] == "subscribed"
        assert unlock_data["can_receive_broadcasts"] is True
