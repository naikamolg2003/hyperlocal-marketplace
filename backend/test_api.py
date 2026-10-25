"""
Comprehensive End-to-End Test Suite for Hyperlocal Marketplace API.

Validates:
1. Root & Health Probes (/health, /).
2. Category Taxonomy Management (/api/v1/categories).
3. User Registration with PostGIS Geocoding (/api/v1/users).
4. Multi-Category Inventory Item Creation (/api/v1/items).
5. PostGIS Hyperlocal Radius Search (/api/v1/items/nearby).
6. Customer Requirement Submission & Status Lifecycle (/api/v1/requirements).
7. Merchant Demand Discovery (/api/v1/requirements/nearby).
"""

import sys
import uuid
import warnings
from fastapi.testclient import TestClient

# Suppress Starlette deprecation warning for clean output
warnings.filterwarnings("ignore", category=DeprecationWarning)

from backend.main import app

client = TestClient(app)


def test_01_health_probe():
    """Verify deep health check and database connectivity."""
    response = client.get("/health")
    assert response.status_code == 200, f"Health check failed: {response.text}"
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "connected"
    assert "postgis" in data["database"]["extensions"]
    assert "vector" in data["database"]["extensions"]
    print(f" PASS: /health verified (PostgreSQL {data['database']['postgres_version']}, PostGIS {data['database']['extensions']['postgis']})")


def test_02_categories():
    """Verify category creation and retrieval."""
    test_subcat = f"Test-Sub-{uuid.uuid4().hex[:6]}"
    payload = {
        "category": "Electronics",
        "sub_category": test_subcat,
        "description": "Mobile accessories and electronics",
    }
    create_res = client.post("/api/v1/categories", json=payload)
    assert create_res.status_code == 201, f"Category creation failed: {create_res.text}"
    cat_data = create_res.json()
    assert cat_data["category"] == "Electronics"
    assert cat_data["sub_category"] == test_subcat

    list_res = client.get("/api/v1/categories")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1
    print(f" PASS: /api/v1/categories verified (Created: {cat_data['id']})")
    return cat_data["id"]


def test_03_user_registration():
    """Verify user registration with PostGIS coordinates."""
    unique_suffix = uuid.uuid4().hex[:6]
    seller_phone = f"+919888{unique_suffix[:6]}"
    customer_phone = f"+919777{unique_suffix[:6]}"

    # 1. Register Seller (Indiranagar, Bangalore: 12.9784, 77.6408)
    seller_payload = {
        "name": f"Indiranagar Fresh Bazaar {unique_suffix}",
        "phone": seller_phone,
        "role": "seller",
        "latitude": 12.9784,
        "longitude": 77.6408,
        "address": "100 Feet Road, Indiranagar, Bangalore",
    }
    s_res = client.post("/api/v1/users", json=seller_payload)
    assert s_res.status_code == 201, f"Seller registration failed: {s_res.text}"
    seller = s_res.json()
    assert seller["role"] == "seller"
    assert seller["latitude"] == 12.9784

    # 2. Register Customer (750m away: 12.9745, 77.6350)
    customer_payload = {
        "name": f"Rahul Verma {unique_suffix}",
        "phone": customer_phone,
        "role": "customer",
        "latitude": 12.9745,
        "longitude": 77.6350,
        "address": "Defence Colony, Indiranagar, Bangalore",
    }
    c_res = client.post("/api/v1/users", json=customer_payload)
    assert c_res.status_code == 201, f"Customer registration failed: {c_res.text}"
    customer = c_res.json()
    assert customer["role"] == "customer"

    print(f" PASS: /api/v1/users registered seller '{seller['name']}' and customer '{customer['name']}'")
    return seller["id"], customer["id"]


def test_04_inventory_and_nearby_search(seller_id: str, category_id: str):
    """Verify inventory creation and PostGIS radius search."""
    item_payload = {
        "seller_id": seller_id,
        "product_name": "Artisanal Sourdough Bread 400g",
        "price": 140.00,
        "is_available": True,
        "category_ids": [category_id],
    }
    create_res = client.post("/api/v1/items", json=item_payload)
    assert create_res.status_code == 201, f"Item creation failed: {create_res.text}"
    item = create_res.json()
    assert item["product_name"] == "Artisanal Sourdough Bread 400g"
    assert len(item["categories"]) >= 1

    # Search from customer position (12.9745, 77.6350) with 3km radius
    nearby_res = client.get(
        "/api/v1/items/nearby",
        params={
            "lat": 12.9745,
            "lon": 77.6350,
            "radius_km": 3.0,
            "query": "Sourdough",
        },
    )
    assert nearby_res.status_code == 200, f"Nearby search failed: {nearby_res.text}"
    nearby_data = nearby_res.json()
    assert nearby_data["count"] >= 1, "Expected at least 1 sourdough item within 3km"
    match = nearby_data["items"][0]
    assert match["distance_meters"] > 0
    print(f" PASS: /api/v1/items/nearby found '{match['item']['product_name']}' at {match['distance_meters']}m ({match['distance_km']} km)")

    # Test availability toggle
    toggle_res = client.patch(f"/api/v1/items/{item['id']}/availability", json={"is_available": False})
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_available"] is False
    print(f" PASS: /api/v1/items/{item['id']}/availability toggled to False")

    # Re-toggle to True
    client.patch(f"/api/v1/items/{item['id']}/availability", json={"is_available": True})
    return item["id"]


def test_05_customer_requirements(customer_id: str):
    """Verify customer natural language requirement submission and merchant search."""
    req_payload = {
        "customer_id": customer_id,
        "raw_text": "Need 1kg fresh A2 organic milk and 6 brown eggs before 8:00 AM tomorrow",
        "structured_json": {
            "items": [
                {"name": "A2 organic milk", "quantity": "1L", "unit": "bottle"},
                {"name": "brown eggs", "quantity": 6, "unit": "pieces"},
            ],
            "urgency": "high",
            "deliver_by": "08:00 AM",
        },
        "status": "submitted",
    }
    create_res = client.post("/api/v1/requirements", json=req_payload)
    assert create_res.status_code == 201, f"Requirement creation failed: {create_res.text}"
    req = create_res.json()
    assert req["status"] == "submitted"
    assert req["structured_json"]["urgency"] == "high"

    # Search nearby requirements from seller position (12.9784, 77.6408)
    nearby_res = client.get(
        "/api/v1/requirements/nearby",
        params={
            "lat": 12.9784,
            "lon": 77.6408,
            "radius_km": 3.0,
        },
    )
    assert nearby_res.status_code == 200
    nearby_reqs = nearby_res.json()
    assert nearby_reqs["count"] >= 1
    matched_req = nearby_reqs["requirements"][0]
    print(f" PASS: /api/v1/requirements/nearby found customer demand at {matched_req['distance_meters']}m")

    # Update lifecycle status: submitted -> broadcasting
    status_res = client.patch(f"/api/v1/requirements/{req['id']}/status", json={"status": "broadcasting"})
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "broadcasting"
    print(f" PASS: /api/v1/requirements status transitioned to 'broadcasting'")


def test_06_ai_parsing_and_3km_matching():
    """Verify POST /requirements/submit pipeline: AI parsing + PostGIS 3km matching."""
    submit_payload = {
        "raw_text": "Need 2 packets of milk and some fresh cilantro delivered quickly",
        "latitude": 12.9745,
        "longitude": 77.6350,
        "customer_name": "Priya Sharma",
        "radius_km": 3.0,
    }

    # 1. Test root route: POST /requirements/submit
    res = client.post("/requirements/submit", json=submit_payload)
    assert res.status_code == 201, f"POST /requirements/submit failed: {res.text}"
    data = res.json()

    assert "requirement_id" in data
    assert "parsed_requirement" in data
    assert "matching_summary" in data
    assert data["notified_sellers_count"] >= 1

    parsed = data["parsed_requirement"]
    assert len(parsed["items"]) >= 1
    assert parsed["urgency"] == "high"
    print(f" PASS: /requirements/submit parsed {len(parsed['items'])} items (Urgency: {parsed['urgency']}, Engine: {parsed.get('parsing_engine')})")

    summary = data["matching_summary"]
    assert summary["total_active_sellers_within_radius"] >= 1
    top_seller = summary["sellers"][0]
    print(
        f" PASS: 3 km PostGIS matching found {summary['total_active_sellers_within_radius']} sellers. "
        f"Top seller: '{top_seller['name']}' at {top_seller['distance_meters']}m "
        f"({top_seller['coverage_summary']}, Status: {top_seller['match_status']})"
    )

    # 2. Test versioned alias: POST /api/v1/requirements/submit
    v1_res = client.post("/api/v1/requirements/submit", json=submit_payload)
    assert v1_res.status_code == 201
    print(" PASS: /api/v1/requirements/submit versioned alias verified")


def main():
    print("=" * 70)
    print("RUNNING FASTAPI HYPERLOCAL MARKETPLACE END-TO-END TEST SUITE")
    print("=" * 70)
    test_01_health_probe()
    cat_id = test_02_categories()
    seller_id, customer_id = test_03_user_registration()
    test_04_inventory_and_nearby_search(seller_id, cat_id)
    test_05_customer_requirements(customer_id)
    test_06_ai_parsing_and_3km_matching()
    print("=" * 70)
    print(" ALL FASTAPI END-TO-END INTEGRATION TESTS PASSED CLEANLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
