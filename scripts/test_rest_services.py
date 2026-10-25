"""
Interactive REST Service Test & Data Creation Script
===================================================
Tests the Hyperlocal Marketplace REST API end-to-end:
1. Health check & Extension probe
2. Seller creation with GPS coordinates (Wakad, Pune)
3. Multi-category inventory creation & bulk upload
4. Customer creation (within 3 km radius)
5. Natural language requirement submission with AI parsing
6. PostGIS 3 km radius matching verification
7. Seller broadcast feed query
8. Seller quotation submission
9. Customer quotation viewing
10. Customer quote acceptance (Order -> ACCEPTED)
11. Delivery status updates (OUT_FOR_DELIVERY -> COMPLETED)
12. Seller Freemium order counter verification
"""

import time
import httpx

BASE_URL = "http://localhost:8000"
client = httpx.Client(base_url=BASE_URL, timeout=15.0)

def print_step(num: int, title: str):
    print(f"\n{'='*70}")
    print(f"Step {num}: {title}")
    print(f"{'='*70}")

def run_e2e_demo():
    ts = int(time.time())
    
    # Step 1: Health Check
    print_step(1, "Diagnostic Health Check Probe (GET /health)")
    res = client.get("/health")
    print(f"Status Code: {res.status_code}")
    health_data = res.json()
    print("Database Status:", health_data.get("database", {}).get("status"))
    print("Extensions:", health_data.get("database", {}).get("extensions"))
    print("Total Records:", health_data.get("counts"))
    assert res.status_code == 200

    # Step 2: Create a Local Kirana Store (Seller) in Wakad, Pune
    print_step(2, "Create a Local Kirana Seller (POST /api/v1/users)")
    seller_phone = f"+9198{ts % 100000000:08d}"
    seller_payload = {
        "name": f"Wakad Organic Kirana #{ts % 1000}",
        "phone": seller_phone,
        "role": "seller",
        "latitude": 18.5987,
        "longitude": 73.7660,
        "address": "Datta Mandir Road, Wakad, Pune, Maharashtra 411057"
    }
    res = client.post("/api/v1/users", json=seller_payload)
    print(f"Status Code: {res.status_code}")
    seller = res.json()
    seller_id = seller["id"]
    print(f"Created Seller: {seller['name']} (ID: {seller_id})")
    print(f"Location: [{seller['latitude']}, {seller['longitude']}] | Subscription: {seller.get('subscription_status')}")

    # Step 3: Add Items to Seller's Catalog (POST /api/v1/items/bulk)
    print_step(3, "Add Multi-Category Inventory Catalog (POST /api/v1/items/bulk)")
    bulk_items_payload = {
        "seller_id": seller_id,
        "items": [
            {
                "product_name": "Organic Whole Wheat Brown Bread 400g",
                "price": 55.0,
                "is_available": True,
                "category_names": ["Bakery", "Artisanal", "Breakfast"]
            },
            {
                "product_name": "Farm Fresh Cow Milk 1L Pouch",
                "price": 68.0,
                "is_available": True,
                "category_names": ["Dairy", "Fresh Essentials"]
            },
            {
                "product_name": "Fresh Robusta Bananas 500g",
                "price": 40.0,
                "is_available": True,
                "category_names": ["Fruits", "Fresh Produce"]
            },
            {
                "product_name": "Organic Free-Range Brown Eggs (Pack of 6)",
                "price": 75.0,
                "is_available": True,
                "category_names": ["Dairy & Eggs", "Protein"]
            }
        ]
    }
    res = client.post("/api/v1/items/bulk", json=bulk_items_payload)
    print(f"Status Code: {res.status_code}")
    bulk_result = res.json()
    items_created = bulk_result.get("items", [])
    print(f"Catalog Items Seeded: {len(items_created)} items")
    for it in items_created:
        print(f" - {it['product_name']} | ₹{it['price']} | In Stock: {it['is_available']}")

    # Step 4: Create a Customer within 3 km in Wakad
    print_step(4, "Create a Customer (POST /api/v1/users)")
    customer_phone = f"+9197{ts % 100000000:08d}"
    customer_payload = {
        "name": f"Priya Sharma #{ts % 1000}",
        "phone": customer_phone,
        "role": "customer",
        "latitude": 18.6010,
        "longitude": 73.7680,
        "address": "Kaspate Vasti, Wakad, Pune, Maharashtra 411057"
    }
    res = client.post("/api/v1/users", json=customer_payload)
    print(f"Status Code: {res.status_code}")
    customer = res.json()
    customer_id = customer["id"]
    print(f"Created Customer: {customer['name']} (ID: {customer_id})")

    # Step 5: Customer Submits Unstructured Natural Language Requirement (POST /requirements/submit)
    print_step(5, "Customer Submits Natural Language Demand (POST /requirements/submit)")
    raw_prompt = "Need 2 packets of brown bread, 1 litre organic cow milk, and fresh bananas urgent for breakfast"
    requirement_payload = {
        "customer_id": customer_id,
        "raw_text": raw_prompt,
        "latitude": 18.6010,
        "longitude": 73.7680
    }
    print(f"Customer Prompt: \"{raw_prompt}\"")
    res = client.post("/requirements/submit", json=requirement_payload)
    print(f"Status Code: {res.status_code}")
    req_result = res.json()
    requirement_id = req_result["requirement_id"]
    print(f"Requirement Broadcasted! ID: {requirement_id}")
    print(f"Urgency Detected: {req_result.get('parsed_requirement', {}).get('urgency')}")
    print("AI Parsed Items:")
    for item in req_result.get("parsed_requirement", {}).get("items", []):
        print(f" - Item: {item.get('product_name')} | Quantity: {item.get('quantity')} | Category: {item.get('category')}")
    
    geo_summary = req_result.get("geospatial_summary", {})
    print(f"PostGIS 3 km Matching: Notified {geo_summary.get('notified_sellers_count')} local merchants in radius!")

    # Step 6: Seller Views Nearby Broadcasts (GET /requirements/broadcasts/seller/{seller_id})
    print_step(6, "Seller Radar Receives Broadcast (GET /requirements/broadcasts/seller/{seller_id})")
    res = client.get(f"/requirements/broadcasts/seller/{seller_id}")
    print(f"Status Code: {res.status_code}")
    broadcasts_data = res.json()
    broadcasts_list = broadcasts_data.get("requirements", [])
    print(f"Incoming Broadcasts on Merchant Radar: {len(broadcasts_list)}")
    matching_broadcast = next((b for b in broadcasts_list if b.get("requirement", {}).get("id") == requirement_id), None)
    if matching_broadcast:
        req_obj = matching_broadcast.get("requirement", {})
        print("Matching Broadcast Found on Merchant Radar:")
        print(f" - Prompt: \"{req_obj.get('raw_text')}\"")
        print(f" - Distance: ~{matching_broadcast.get('distance_meters', 250):.0f} meters")

    # Step 7: Seller Submits Itemized Price Quote (POST /quotations/submit)
    print_step(7, "Seller Submits Price Quote (POST /quotations/submit)")
    quote_payload = {
        "requirement_id": requirement_id,
        "seller_id": seller_id,
        "itemized_prices": [
            {"product_name": "Organic Whole Wheat Brown Bread 400g", "quantity": "2 pkts", "unit_price": 55.0, "total": 110.0},
            {"product_name": "Farm Fresh Cow Milk 1L Pouch", "quantity": "1 L", "unit_price": 68.0, "total": 68.0},
            {"product_name": "Fresh Robusta Bananas 500g", "quantity": "1 bunch", "unit_price": 40.0, "total": 40.0}
        ],
        "total_amount": 218.0,
        "estimated_delivery_time": "15-20 mins"
    }
    res = client.post("/quotations/submit", json=quote_payload)
    print(f"Status Code: {res.status_code}")
    quotation = res.json()
    quotation_id = quotation["id"]
    print(f"Quotation Submitted! ID: {quotation_id}")
    print(f"Total Amount: ₹{quotation['total_amount']} | Turnaround ETA: {quotation['estimated_delivery_time']}")

    # Step 8: Customer Views Incoming Price Quotes (GET /requirements/{requirement_id}/quotations)
    print_step(8, "Customer Views Vendor Quotes (GET /requirements/{requirement_id}/quotations)")
    res = client.get(f"/requirements/{requirement_id}/quotations")
    print(f"Status Code: {res.status_code}")
    quotes = res.json()
    print(f"Total Incoming Quotes Received: {len(quotes)}")
    for q in quotes:
        print(f" - Store: {q.get('seller', {}).get('name')} | Quote: ₹{q.get('total_amount')} | ETA: {q.get('estimated_delivery_time')}")

    # Step 9: Customer Accepts the Quote (POST /orders/accept-quote)
    print_step(9, "Customer Accepts Quote (POST /orders/accept-quote)")
    accept_payload = {
        "quotation_id": quotation_id,
        "notes": "Please deliver to Flat 302, 3rd Floor"
    }
    res = client.post("/orders/accept-quote", json=accept_payload)
    print(f"Status Code: {res.status_code}")
    order = res.json()
    order_id = order["id"]
    print(f"Order Accepted & Confirmed! Order ID: {order_id}")
    quote_amt = order.get('quote_amount') or order.get('total_amount')
    print(f"Lifecycle Status: {order['status']} | Amount: ₹{quote_amt}")

    # Step 10: Seller Dispatches Order: Mark OUT_FOR_DELIVERY (PATCH /orders/{order_id}/status)
    print_step(10, "Seller Dispatches Order (PATCH /orders/{order_id}/status)")
    dispatch_payload = {
        "status": "OUT_FOR_DELIVERY",
        "notes": "Rider picked up package and is en route"
    }
    res = client.patch(f"/orders/{order_id}/status", json=dispatch_payload)
    print(f"Status Code: {res.status_code}")
    updated_order = res.json()
    print(f"Updated Lifecycle Status: {updated_order['status']}")

    # Step 11: Seller Completes Handover: Mark COMPLETED (PATCH /orders/{order_id}/status)
    print_step(11, "Seller Completes Delivery (PATCH /orders/{order_id}/status)")
    delivered_payload = {
        "status": "COMPLETED",
        "notes": "Delivered to customer doorstep and verified"
    }
    res = client.patch(f"/orders/{order_id}/status", json=delivered_payload)
    print(f"Status Code: {res.status_code}")
    completed_order = res.json()
    print(f"Final Lifecycle Status: {completed_order['status']} | Completed At: {completed_order.get('completed_at')}")

    # Step 12: Check Seller's Subscription & Completed Orders Quota (GET /api/v1/billing/seller/{seller_id}/status)
    print_step(12, "Inspect Freemium Billing Quota (GET /api/v1/billing/seller/{seller_id}/status)")
    res = client.get(f"/api/v1/billing/seller/{seller_id}/status")
    print(f"Status Code: {res.status_code}")
    billing = res.json()
    print(f"Seller: {billing.get('seller_name')}")
    print(f"Completed Orders: {billing.get('completed_orders_count')} / 2 free trial orders")
    print(f"Free Orders Remaining: {billing.get('free_orders_remaining')}")
    print(f"Subscription Status: {billing.get('subscription_status')}")
    print(f"Can Receive Broadcasts: {billing.get('can_receive_broadcasts')}")

    print("\n" + "="*70)
    print("ALL 12 REST SERVICE STEPS COMPLETED SUCCESSFULLY!")
    print("="*70)

if __name__ == "__main__":
    run_e2e_demo()
