import httpx
import time
from uuid import UUID

BASE_URL = "http://localhost:8000"
client = httpx.Client(timeout=20.0)

def test_inventory_and_order_loop():
    print("=== Testing Seller Inventory Management & Order Payment Loop ===")

    # 1. Check health
    health_res = client.get(f"{BASE_URL}/health")
    assert health_res.status_code == 200, f"Health check failed: {health_res.text}"
    print("Health check OK:", health_res.json()["status"])

    # 2. Create fresh test seller
    ts = int(time.time())
    seller_payload = {
        "name": f"Super Mart Wakad {ts % 10000}",
        "phone": f"+9188{ts % 100000000:08d}",
        "role": "seller",
        "latitude": 18.5985,
        "longitude": 73.7662,
        "address": "Kaspate Vasti, Wakad, Pune",
    }
    seller_res = client.post(f"{BASE_URL}/api/v1/users", json=seller_payload)
    assert seller_res.status_code == 201, f"Failed to create seller: {seller_res.text}"
    seller = seller_res.json()
    seller_id = seller["id"]
    print(f"Created Seller '{seller['name']}' (ID: {seller_id})")

    # 3. Add individual item with multiple categories (names)
    print("\n--- 1. Testing Individual Item Creation with Multiple Categories ---")
    item1_res = client.post(f"{BASE_URL}/api/v1/items", json={
        "seller_id": seller_id,
        "product_name": "Artisan Sourdough Loaf 400g",
        "price": 140.0,
        "is_available": True,
        "category_names": ["Bakery & Breads", "Artisan Foods", "Breakfast Essentials"]
    })
    assert item1_res.status_code == 201, f"Failed: {item1_res.text}"
    item1 = item1_res.json()
    cat_names = [c["category"] for c in item1["categories"]]
    print(f"Created Item: '{item1['product_name']}', Price: Rs.{item1['price']}, Categories: {cat_names}")
    assert len(item1["categories"]) == 3, "Expected 3 categories mapped to a single product record without duplicates"

    # 4. Bulk Upload Inventory Items (JSON)
    print("\n--- 2. Testing Bulk Inventory Upload ---")
    bulk_payload = {
        "seller_id": seller_id,
        "items": [
            {
                "product_name": "Organic Cold-Pressed Coconut Oil 500ml",
                "price": 280.0,
                "is_available": True,
                "category_names": ["Cooking Oils", "Organic Staples"]
            },
            {
                "product_name": "Premium California Almonds 250g",
                "price": 320.0,
                "is_available": True,
                "category_names": ["Dry Fruits", "Healthy Snacks"]
            },
            {
                "product_name": "Greek Yogurt Natural 400g",
                "price": 95.0,
                "is_available": True,
                "category_names": ["Dairy", "Breakfast Essentials"]
            }
        ]
    }
    bulk_res = client.post(f"{BASE_URL}/api/v1/items/bulk", json=bulk_payload)
    assert bulk_res.status_code == 201, f"Bulk upload failed: {bulk_res.text}"
    bulk_data = bulk_res.json()
    print(f"Bulk Upload Success: {bulk_data['total_uploaded']} items added!")
    assert bulk_data["total_uploaded"] == 3

    # 5. Test Availability Toggle
    print("\n--- 3. Testing Real-Time Availability Toggle ---")
    toggle_res = client.patch(f"{BASE_URL}/api/v1/items/{item1['id']}/availability", json={"is_available": False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_available"] is False
    print(f"Toggled '{item1['product_name']}' availability to FALSE (offboarded)")

    toggle_back = client.patch(f"{BASE_URL}/api/v1/items/{item1['id']}/availability", json={"is_available": True})
    assert toggle_back.status_code == 200
    assert toggle_back.json()["is_available"] is True
    print(f"Toggled '{item1['product_name']}' availability to TRUE (onboarded)")

    # 6. Test Price Update
    print("\n--- 4. Testing Real-Time Pricing Adjustment ---")
    update_res = client.put(f"{BASE_URL}/api/v1/items/{item1['id']}", json={"price": 155.0})
    assert update_res.status_code == 200
    assert float(update_res.json()["price"]) == 155.0
    print(f"Adjusted '{item1['product_name']}' price to Rs.155.00")

    # 7. Customer submits a requirement
    print("\n--- 5. Customer Submits Demand Broadcast ---")
    req_res = client.post(f"{BASE_URL}/requirements/submit", json={
        "raw_text": "Need fresh artisan bread and cold pressed coconut oil urgent",
        "latitude": 18.5987,
        "longitude": 73.7660,
        "radius_km": 3.0
    })
    assert req_res.status_code == 201
    req_data = req_res.json()
    requirement_id = req_data["requirement_id"]
    print(f"Requirement Created: '{req_data['raw_text']}' (ID: {requirement_id})")

    # 8. Seller accepts requirement and submits itemized quote/bill
    print("\n--- 6. Seller Accepts & Submits Itemized Quote/Bill ---")
    quote_res = client.post(f"{BASE_URL}/api/v1/orders/quote", json={
        "requirement_id": requirement_id,
        "seller_id": seller_id,
        "quote_amount": 435.0,
        "delivery_estimate_minutes": 25,
        "itemized_items": [
            {"product_name": "Artisan Sourdough Loaf 400g", "quantity": 1, "unit_price": 155.0, "total": 155.0},
            {"product_name": "Organic Cold-Pressed Coconut Oil 500ml", "quantity": 1, "unit_price": 280.0, "total": 280.0}
        ],
        "notes": "Both items packed and ready for immediate delivery"
    })
    assert quote_res.status_code == 201, f"Quote submission failed: {quote_res.text}"
    quote_order = quote_res.json()
    order_id = quote_order["id"]
    print(f"Quote Order Created: ID = {order_id}, Amount = Rs.{quote_order['quote_amount']}, Status = {quote_order['status']}")
    assert quote_order["status"] == "pending"

    # 9. Customer views quotes received for requirement
    quotes_list = client.get(f"{BASE_URL}/api/v1/orders/requirement/{requirement_id}").json()
    print(f"Quotes received for customer requirement: {len(quotes_list)}")
    assert len(quotes_list) >= 1

    # 10. Customer approves and settles payment via Mock Escrow Gateway
    print("\n--- 7. Customer Approves & Settles Payment (Mock Escrow Gateway) ---")
    pay_res = client.post(f"{BASE_URL}/api/v1/orders/{order_id}/pay", json={
        "payment_method": "upi",
        "transaction_ref": "UPI-ESCROW-892348"
    })
    assert pay_res.status_code == 200, f"Escrow payment failed: {pay_res.text}"
    pay_data = pay_res.json()
    print("Payment Succeeded:", pay_data["message"])
    assert pay_data["success"] is True
    assert pay_data["escrow_settled"] is True
    assert pay_data["order"]["status"] == "completed"

    # 11. Check seller completed order count and freemium trigger
    seller_billing = pay_data["seller_billing"]
    print(f"Seller Billing After Order: Completed Orders = {seller_billing['completed_orders_count']}, Remaining Free = {seller_billing['free_orders_remaining']}, Status = {seller_billing['subscription_status']}")
    assert seller_billing["completed_orders_count"] == 1
    assert seller_billing["free_orders_remaining"] == 1
    assert pay_data["trial_expired_alert"] is False

    # 12. Submit a 2nd quote and pay to verify freemium trigger (2nd completed order)
    print("\n--- 8. Completing 2nd Order to Trigger Freemium Milestone ---")
    req2 = client.post(f"{BASE_URL}/requirements/submit", json={
        "raw_text": "Need greek yogurt natural",
        "latitude": 18.5987,
        "longitude": 73.7660
    }).json()

    quote2 = client.post(f"{BASE_URL}/api/v1/orders/quote", json={
        "requirement_id": req2["requirement_id"],
        "seller_id": seller_id,
        "quote_amount": 95.0,
        "delivery_estimate_minutes": 15,
        "itemized_items": [{"product_name": "Greek Yogurt Natural 400g", "quantity": 1, "unit_price": 95.0}],
        "notes": "Chilled container ready"
    }).json()

    pay2 = client.post(f"{BASE_URL}/api/v1/orders/{quote2['id']}/pay", json={
        "payment_method": "card",
        "transaction_ref": "CARD-ESCROW-112233"
    }).json()

    print("Order 2 Payment Succeeded:", pay2["message"])
    b2 = pay2["seller_billing"]
    print(f"Seller Billing After 2nd Order: Completed = {b2['completed_orders_count']}, Remaining = {b2['free_orders_remaining']}, Status = {b2['subscription_status']}, Trial Alert = {pay2['trial_expired_alert']}")
    assert b2["completed_orders_count"] == 2
    assert b2["free_orders_remaining"] == 0
    assert b2["subscription_status"] == "pending_payment"
    assert pay2["trial_expired_alert"] is True
    assert b2["can_receive_broadcasts"] is False

    print("\n ALL INVENTORY MANAGEMENT & ORDER PAYMENT LOOP TESTS PASSED!")

if __name__ == "__main__":
    test_inventory_and_order_loop()
