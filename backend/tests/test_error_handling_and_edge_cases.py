"""
Error Handling and Edge Cases Integration Tests.

Validates system robustness and graceful degradation:
1. LLM API timeouts fallback to deterministic offline NLP rule parser.
2. Resilient JSON extraction handles markdown fences, chatter, and trailing commas.
3. Blank or whitespace requirements return graceful response without server errors.
4. Geospatial queries when zero sellers exist in radius return friendly empty summary.
5. Coordinate validation rejects out-of-bound WGS84 coordinates.
6. Offboarded products (is_available=False) are excluded from in-stock matches.
"""

import pytest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient

from backend.ai_parser import (
    parse_requirement_text,
    _sanitize_and_parse_json,
    _parse_offline_fallback,
    UrgencyLevel,
)
from backend.matching_engine import find_matching_sellers
from backend.models import User, UserRole


class TestErrorHandlingAndEdgeCases:
    """Robustness and resilience test cases."""

    # -------------------------------------------------------------------------
    # 1. LLM API Timeout & Network Error Fallback
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_llm_api_timeout_fallback(self, monkeypatch):
        """Simulate an external LLM API timeout and verify fallback to offline rule parser."""
        monkeypatch.setenv("GEMINI_API_KEY", "mock-test-key")
        monkeypatch.setenv("LLM_PROVIDER", "gemini")

        # Mock httpx client post to raise a TimeoutException
        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("Connection timed out to LLM provider")

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            result = await parse_requirement_text("Need 2 packets of milk quickly")
            assert result is not None
            assert result.parsing_engine == "offline_fallback_rules"
            assert len(result.items) >= 1
            assert any("milk" in it.product_name.lower() for it in result.items)
            assert result.urgency in (UrgencyLevel.HIGH, UrgencyLevel.IMMEDIATE)

    # -------------------------------------------------------------------------
    # 2. Resilient JSON Sanitization & Malformed Response Handling
    # -------------------------------------------------------------------------
    def test_sanitize_and_parse_json_markdown_fence(self):
        """Handle LLM response enclosed in markdown backticks."""
        raw_output = """```json
        {
            "items": [{"product_name": "Organic Milk", "quantity": "1L", "category": "Dairy"}],
            "urgency": "medium",
            "additional_notes": null
        }
        ```"""
        parsed = _sanitize_and_parse_json(raw_output)
        assert "items" in parsed
        assert parsed["items"][0]["product_name"] == "Organic Milk"

    def test_sanitize_and_parse_json_with_conversational_chatter(self):
        """Handle conversational pre-text and post-text around JSON output."""
        raw_output = """Certainly! Here is the structured shopping list you requested:
        {
            "items": [{"product_name": "Coriander", "quantity": "1 bunch", "category": "Produce"}],
            "urgency": "high"
        }
        I hope this fulfills your request! Let me know if you need anything else."""
        parsed = _sanitize_and_parse_json(raw_output)
        assert "items" in parsed
        assert parsed["urgency"] == "high"

    def test_sanitize_and_parse_json_trailing_commas(self):
        """Handle syntax errors caused by trailing commas in JSON."""
        raw_output = """{
            "items": [
                {"product_name": "Eggs", "quantity": "6 pcs", "category": "Dairy",},
            ],
            "urgency": "medium",
        }"""
        parsed = _sanitize_and_parse_json(raw_output)
        assert "items" in parsed
        assert parsed["items"][0]["product_name"] == "Eggs"

    def test_sanitize_and_parse_json_completely_broken_fallback(self):
        """Verify broken non-JSON text raises ValueError to trigger offline fallback."""
        broken_output = "I cannot fulfill this request as I am just an AI language model."
        with pytest.raises(ValueError):
            _sanitize_and_parse_json(broken_output)

    # -------------------------------------------------------------------------
    # 3. Blank or Whitespace Requirement Handling
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_empty_and_whitespace_requirement_handling(self):
        """Verify empty and whitespace inputs do not cause unhandled crashes."""
        empty_res = await parse_requirement_text("")
        assert empty_res.parsing_engine == "empty_input_handler"
        assert len(empty_res.items) == 0

        whitespace_res = await parse_requirement_text("     ")
        assert whitespace_res.parsing_engine == "empty_input_handler"
        assert len(whitespace_res.items) == 0

    def test_endpoint_empty_prompt_validation(self, test_client: TestClient):
        """Verify requirement submission endpoint rejects empty text with 422."""
        res = test_client.post("/requirements/submit", json={
            "raw_text": "  ",
            "latitude": 12.9745,
            "longitude": 77.6350,
        })
        assert res.status_code == 422, "Short or blank text should trigger 422 validation"

    # -------------------------------------------------------------------------
    # 4. Geospatial Queries: Zero Sellers Found Within Radius
    # -------------------------------------------------------------------------
    def test_geospatial_zero_sellers_in_radius(self, test_client: TestClient):
        """
        Customer pin located in a remote unpopulated coordinate (e.g. Pacific Ocean).
        Asserts system returns HTTP 201 with empty seller list and helpful coverage note.
        """
        remote_lat = -48.8766  # Point Nemo
        remote_lon = -123.3933

        res = test_client.post("/requirements/submit", json={
            "raw_text": "Need fresh apples and mineral water",
            "latitude": remote_lat,
            "longitude": remote_lon,
            "radius_km": 3.0,
        })
        assert res.status_code == 201
        data = res.json()
        matching = data["matching_summary"]

        assert matching["total_active_sellers_within_radius"] == 0
        assert matching["notified_sellers_count"] == 0
        assert matching["sellers"] == []
        assert matching["coverage_status"] == "no_sellers_within_radius"
        assert "No active merchants found" in matching["status_message"]

    # -------------------------------------------------------------------------
    # 5. Invalid Coordinate Validation
    # -------------------------------------------------------------------------
    def test_invalid_wgs84_coordinate_bounds(self, test_client: TestClient):
        """Latitude must be between -90 and 90; Longitude between -180 and 180."""
        # Latitude out of bounds (> 90)
        res1 = test_client.post("/requirements/submit", json={
            "raw_text": "Need groceries",
            "latitude": 95.0,
            "longitude": 77.0,
        })
        assert res1.status_code == 422

        # Longitude out of bounds (< -180)
        res2 = test_client.post("/requirements/submit", json={
            "raw_text": "Need groceries",
            "latitude": 12.0,
            "longitude": -195.0,
        })
        assert res2.status_code == 422

    # -------------------------------------------------------------------------
    # 6. Real-Time Offboarded Product Exclusion
    # -------------------------------------------------------------------------
    def test_offboarded_products_excluded_from_stock_match(self, test_client: TestClient, make_unique_phone):
        """When seller marks is_available=False, item should not appear in in-stock match."""
        # Register seller
        s_res = test_client.post("/api/v1/users", json={
            "name": "Quick Mart Pune",
            "phone": make_unique_phone("93"),
            "role": "seller",
            "latitude": 18.5987,
            "longitude": 73.7660,
        })
        seller_id = s_res.json()["id"]

        # Add item that is currently in stock
        it_res = test_client.post("/api/v1/items", json={
            "seller_id": seller_id,
            "product_name": "Premium Basmati Rice 5kg",
            "price": 450.0,
            "is_available": True,
            "category_names": ["Grocery", "Staples"],
        })
        item_id = it_res.json()["id"]

        # Toggle item availability to FALSE (offboarded / out of stock)
        toggle_res = test_client.patch(f"/api/v1/items/{item_id}/availability", json={
            "is_available": False,
        })
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_available"] is False

        # Submit customer requirement for basmati rice
        req_res = test_client.post("/requirements/submit", json={
            "raw_text": "Need 1 packet basmati rice",
            "latitude": 18.5987,
            "longitude": 73.7660,
            "radius_km": 3.0,
        })
        req_data = req_res.json()
        sellers = req_data["matching_summary"]["sellers"]
        matched_seller = next((s for s in sellers if s["seller_id"] == seller_id), None)

        assert matched_seller is not None
        # Assert item does NOT appear in matched_items because is_available=False
        matched_item_names = [it["product_name"] for it in matched_seller["matched_items"]]
        assert "Premium Basmati Rice 5kg" not in matched_item_names
        assert matched_seller["fulfillment_percentage"] == 0.0
