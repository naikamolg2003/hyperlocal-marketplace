"""
AI Natural Language Customer Requirement Parser.

Extracts structured shopping items, quantities, categories, urgency levels,
and delivery constraints from raw customer prompts.

Supported LLM Providers:
1. Google Gemini (via GEMINI_API_KEY)
2. OpenAI (via OPENAI_API_KEY)
3. Anthropic Claude (via ANTHROPIC_API_KEY)
4. Deterministic Offline Fallback Parser (active when no API keys are configured)
"""

import enum
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("hyperlocal-ai-parser")


# -----------------------------------------------------------------------------
# Structured Output Pydantic Schemas
# -----------------------------------------------------------------------------
class UrgencyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    IMMEDIATE = "immediate"


class ParsedItem(BaseModel):
    product_name: str = Field(
        ...,
        description="Clean normalized product or item name (e.g. 'Whole Milk', 'Cilantro', 'Sourdough Bread')",
        example="Whole Milk",
    )
    quantity: str = Field(
        ...,
        description="Quantity specification with unit (e.g. '2 packets', '1 bunch', '500g', '1L', '1 kg')",
        example="2 packets",
    )
    category: Optional[str] = Field(
        None,
        description="Broad product category (e.g. 'Dairy', 'Produce', 'Bakery', 'Grocery', 'Beverages')",
        example="Dairy",
    )
    estimated_price_range: Optional[str] = Field(
        None,
        description="Optional expected budget or price estimate if mentioned",
        example="₹60-₹80",
    )


class ParsedRequirement(BaseModel):
    items: List[ParsedItem] = Field(
        ...,
        description="List of distinct grocery/product items extracted from the customer request",
    )
    urgency: UrgencyLevel = Field(
        default=UrgencyLevel.MEDIUM,
        description="Inferred urgency level based on customer wording",
        example=UrgencyLevel.HIGH,
    )
    estimated_delivery_time: Optional[str] = Field(
        None,
        description="Target delivery timeframe (e.g. 'Within 30 minutes', 'Before 8:00 AM')",
        example="Within 30 minutes",
    )
    additional_notes: Optional[str] = Field(
        None,
        description="Dietary constraints, brand preferences, or delivery instructions",
        example="Delivered quickly, contactless",
    )
    parsing_engine: str = Field(
        default="unknown",
        description="Identifier of LLM provider or fallback engine that performed the extraction",
    )


# -----------------------------------------------------------------------------
# System Prompt & JSON Schema for LLMs
# -----------------------------------------------------------------------------
SYSTEM_PROMPT = """You are an expert AI parser for a hyperlocal quick-commerce marketplace.
Your task is to analyze raw customer requirement text and extract a structured shopping list.

Always output strict JSON adhering exactly to this schema:
{
  "items": [
    {
      "product_name": "clean product name",
      "quantity": "quantity with unit",
      "category": "Dairy | Produce | Bakery | Grocery | Beverages | Snacks | Personal Care | Other",
      "estimated_price_range": "optional estimate or null"
    }
  ],
  "urgency": "low | medium | high | immediate",
  "estimated_delivery_time": "target window or null",
  "additional_notes": "special instructions, brand preference, or null"
}

Guidelines:
- Normalize names (e.g. 'cilantro' -> 'Fresh Cilantro', 'milk' -> 'Milk / Whole Milk').
- Extract accurate quantities ('2 packets', '500g', '1 kg', 'a dozen').
- Identify urgency ('quickly', 'asap', 'emergency', 'fast' -> 'high' or 'immediate').
- Return ONLY valid JSON, with no markdown code blocks or surrounding commentary.
"""


LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "10.0"))


def _sanitize_and_parse_json(content_text: str) -> Dict[str, Any]:
    """
    Extracts and parses JSON from raw LLM output, resiliently handling:
    - Markdown code fences (```json ... ``` or ``` ...)
    - Preceding or trailing conversational text
    - Trailing commas before closing braces/brackets
    """
    text = content_text.strip()

    # 1. Strip markdown fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # 2. Extract outermost curly brackets
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx : end_idx + 1]

    # 3. Direct JSON decode
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 4. Remove trailing commas before '}' or ']'
        cleaned_text = re.sub(r",\s*([\]}])", r"\1", text)
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as err:
            logger.warning("Failed to decode JSON from LLM response: %s (Raw preview: %.120s)", err, text)
            raise ValueError(f"Malformed JSON from LLM: {err}") from err


# -----------------------------------------------------------------------------
# Provider Implementations
# -----------------------------------------------------------------------------
async def _parse_with_gemini(raw_text: str, api_key: str, model: str) -> ParsedRequirement:
    """Call Google Gemini API using native JSON output mode with timeout."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nCustomer Request: \"{raw_text}\""}
                ],
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        },
    }

    timeout = httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No response candidates returned by Gemini")

    content_text = candidates[0]["content"]["parts"][0]["text"]
    parsed_json = _sanitize_and_parse_json(content_text)
    parsed_json["parsing_engine"] = f"gemini:{model}"
    return ParsedRequirement(**parsed_json)


async def _parse_with_openai(raw_text: str, api_key: str, model: str) -> ParsedRequirement:
    """Call OpenAI Chat Completions API with JSON object response format and timeout."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    timeout = httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content_text = data["choices"][0]["message"]["content"]
    parsed_json = _sanitize_and_parse_json(content_text)
    parsed_json["parsing_engine"] = f"openai:{model}"
    return ParsedRequirement(**parsed_json)


async def _parse_with_anthropic(raw_text: str, api_key: str, model: str) -> ParsedRequirement:
    """Call Anthropic Claude Messages API with timeout and sanitized JSON extraction."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"Parse this request into valid JSON: {raw_text}"}
        ],
        "temperature": 0.1,
    }

    timeout = httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    content_text = data["content"][0]["text"]
    parsed_json = _sanitize_and_parse_json(content_text)
    parsed_json["parsing_engine"] = f"anthropic:{model}"
    return ParsedRequirement(**parsed_json)


# -----------------------------------------------------------------------------
# Deterministic Rule-Based Fallback Engine
# Active when no API keys are configured (e.g. offline testing, development)
# -----------------------------------------------------------------------------
def _parse_offline_fallback(raw_text: str) -> ParsedRequirement:
    """
    Intelligent NLP fallback parser using regex tokenization and category taxonomy dictionaries.
    Guarantees reliable, zero-latency extraction when external LLM APIs are unconfigured or unavailable.
    """
    text_lower = raw_text.lower()

    # Determine Urgency
    urgency = UrgencyLevel.MEDIUM
    if any(w in text_lower for w in ["immediately", "emergency", "right now", "urgent", "asap"]):
        urgency = UrgencyLevel.IMMEDIATE
    elif any(w in text_lower for w in ["quickly", "fast", "soon", "hurry", "quick", "speedy"]):
        urgency = UrgencyLevel.HIGH
    elif any(w in text_lower for w in ["whenever", "later", "no rush", "evening", "tomorrow"]):
        urgency = UrgencyLevel.LOW

    # Category and Item Vocabulary Knowledge Base
    catalog_taxonomy = {
        "milk": ("Whole Milk", "Dairy", "1 packet"),
        "curd": ("Fresh Dahi / Curd", "Dairy", "1 tub (400g)"),
        "yogurt": ("Greek Yogurt", "Dairy", "1 cup"),
        "cheese": ("Cheddar Cheese", "Dairy", "200g"),
        "butter": ("Salted Butter", "Dairy", "100g"),
        "paneer": ("Fresh Malai Paneer", "Dairy", "200g"),
        "cilantro": ("Fresh Cilantro / Coriander", "Produce", "1 bunch"),
        "coriander": ("Fresh Coriander", "Produce", "1 bunch"),
        "tomato": ("Country Tomatoes", "Produce", "500g"),
        "tomatoes": ("Country Tomatoes", "Produce", "1 kg"),
        "potato": ("Potatoes", "Produce", "1 kg"),
        "potatoes": ("Potatoes", "Produce", "1 kg"),
        "onion": ("Red Onions", "Produce", "1 kg"),
        "onions": ("Red Onions", "Produce", "1 kg"),
        "banana": ("Robusta Bananas", "Produce", "6 pcs"),
        "bananas": ("Robusta Bananas", "Produce", "1 dozen"),
        "apple": ("Shimla Apples", "Produce", "500g"),
        "apples": ("Shimla Apples", "Produce", "1 kg"),
        "bread": ("Artisanal Bread", "Bakery", "1 loaf"),
        "sourdough": ("Artisanal Sourdough Bread", "Bakery", "400g"),
        "eggs": ("Farm Fresh Brown Eggs", "Dairy", "6 pcs"),
        "egg": ("Farm Fresh Brown Eggs", "Dairy", "6 pcs"),
        "coffee": ("Arabica Ground Coffee", "Beverages", "250g"),
        "tea": ("Assam CTC Tea", "Beverages", "250g"),
        "rice": ("Basmati Rice", "Grocery", "1 kg"),
        "atta": ("Whole Wheat Atta", "Grocery", "5 kg"),
        "flour": ("Wheat Flour", "Grocery", "1 kg"),
        "oil": ("Cold Pressed Cooking Oil", "Grocery", "1L"),
        "salt": ("Iodized Table Salt", "Grocery", "1 kg"),
        "sugar": ("Organic Cane Sugar", "Grocery", "1 kg"),
    }

    # Split text into segments
    segments = re.split(r",| and | with | & |\+", text_lower)
    extracted_items: List[ParsedItem] = []

    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue

        matched_key = None
        for key in catalog_taxonomy:
            # Match word boundary
            if re.search(r"\b" + re.escape(key) + r"\b", seg):
                matched_key = key
                break

        if matched_key:
            norm_name, norm_cat, default_qty = catalog_taxonomy[matched_key]

            # Extract numeric quantities and units if present
            qty_match = re.search(r"(\d+(?:\.\d+)?\s*(?:kg|g|gm|packet|packets|litres?|liter|l|ml|bunch|bunches|dozen|pcs|pieces|loaf|bottles?|tubs?))", seg)
            if qty_match:
                extracted_qty = qty_match.group(1).strip()
            else:
                extracted_qty = default_qty

            extracted_items.append(
                ParsedItem(
                    product_name=norm_name,
                    quantity=extracted_qty,
                    category=norm_cat,
                )
            )

    # Fallback if no specific catalog keywords matched: create a generic item from raw text
    if not extracted_items:
        clean_name = re.sub(r"^(need|want|please bring|deliver|get me|buy)\s+", "", raw_text, flags=re.I).strip()
        extracted_items.append(
            ParsedItem(
                product_name=clean_name.capitalize() if clean_name else "Requested Item",
                quantity="1 unit",
                category="Grocery",
            )
        )

    # Inferred delivery time
    delivery_time = None
    if urgency in (UrgencyLevel.IMMEDIATE, UrgencyLevel.HIGH):
        delivery_time = "Within 30-45 minutes"

    return ParsedRequirement(
        items=extracted_items,
        urgency=urgency,
        estimated_delivery_time=delivery_time,
        additional_notes="Extracted via intelligent fallback parser",
        parsing_engine="offline_fallback_rules",
    )


# -----------------------------------------------------------------------------
# Main Public Entrypoint
# -----------------------------------------------------------------------------
async def parse_requirement_text(
    raw_text: str,
    provider: Optional[str] = None,
) -> ParsedRequirement:
    """
    Main entrypoint to parse raw customer requirement text into a structured shopping list.

    Auto-detects API key priority:
    1. Gemini (GEMINI_API_KEY)
    2. OpenAI (OPENAI_API_KEY)
    3. Anthropic (ANTHROPIC_API_KEY)
    4. Deterministic Offline Fallback Parser (if no keys configured or provider fails)
    """
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "auto")).lower()

    # Handle blank or whitespace-only inputs gracefully
    if not raw_text or not raw_text.strip():
        return ParsedRequirement(
            items=[],
            urgency=UrgencyLevel.LOW,
            estimated_delivery_time=None,
            additional_notes="Empty requirement submitted",
            parsing_engine="empty_input_handler",
        )

    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    # 1. Gemini
    if (selected_provider in ("gemini", "auto")) and gemini_key:
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        try:
            logger.info("Parsing requirement using Gemini (%s)...", model)
            return await _parse_with_gemini(raw_text, gemini_key, model)
        except Exception as exc:
            logger.warning("Gemini parsing failed (%s). Falling back...", exc)

    # 2. OpenAI
    if (selected_provider in ("openai", "auto")) and openai_key:
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        try:
            logger.info("Parsing requirement using OpenAI (%s)...", model)
            return await _parse_with_openai(raw_text, openai_key, model)
        except Exception as exc:
            logger.warning("OpenAI parsing failed (%s). Falling back...", exc)

    # 3. Anthropic
    if (selected_provider in ("anthropic", "auto")) and anthropic_key:
        model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
        try:
            logger.info("Parsing requirement using Anthropic (%s)...", model)
            return await _parse_with_anthropic(raw_text, anthropic_key, model)
        except Exception as exc:
            logger.warning("Anthropic parsing failed (%s). Falling back...", exc)

    # 4. Deterministic Offline Fallback
    logger.info("Using deterministic offline rule parser for customer requirement.")
    return _parse_offline_fallback(raw_text)
