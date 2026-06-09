"""Invoice classification — 3-layer fallback: keywords, BART, custom model."""
import os, requests, json
from loguru import logger


# ── Category definitions ──────────────────────────────────────────────────────

CATEGORIES = [
    "Raw Materials",
    "Capital Goods",
    "Services",
    "Other",
    "Office Expenses",
    "Transport",
    "IT & Software",
    "Professional Fees",
    "Rent & Utilities",
    "Travel",
]

KEYWORD_RULES = {
    "steel|iron|cement|brick|tile|paint|pipe|plywood|timber|chemical|raw material": "Raw Materials",
    "machine|equipment|motor|pump|generator|compressor|tool|plant|machinery": "Capital Goods",
    "repair|maintenance|service|consult|legal|audit|fee|professional": "Professional Fees",
    "rent|electricity|water|gas|utility|bill|maintenance charge": "Rent & Utilities",
    "travel|ticket|hotel|lodging|boarding|fuel|diesel|petrol|toll": "Travel",
    "transport|freight|logistic|courier|delivery|shipping|loading|unloading": "Transport",
    "software|license|server|hosting|domain|it support|cloud|saas": "IT & Software",
    "stationery|print|office|furniture|consumable|supply": "Office Expenses",
    "food|catering|canteen|snack|beverage": "Other",
}


def classify_invoice(fields: dict) -> dict:
    """Classify invoice using 3-layer fallback: keyword -> BART -> custom model."""

    description = (fields.get("description") or {}).get("value") or ""
    seller_name = (fields.get("seller_name") or {}).get("value") or ""
    text = f"{seller_name} {description}".lower()

    # Layer 1: Fast keyword match
    for pattern, category in KEYWORD_RULES.items():
        import re
        if re.search(pattern, text):
            logger.info(f"Layer 1 (keyword): {category}")
            return _result(category, 0.85, "keyword")

    # Layer 2: BART MNLI via HuggingFace API
    bart_result = _classify_bart(text)
    if bart_result and bart_result["confidence"] > 0.5:
        logger.info(f"Layer 2 (bart): {bart_result['category']} | score: {bart_result['confidence']}")
        return bart_result

    # Layer 3: Custom model
    your_result = _classify_your_model(text)
    if your_result and your_result["confidence"] > 0.5:
        logger.info(f"Layer 3 (your model): {your_result['category']} | score: {your_result['confidence']}")
        return your_result

    return _result("Other", 0.5, "fallback")


def _result(category: str, confidence: float, source: str) -> dict:
    itc_blocked = category in ("Other", "Travel", "Food", "Rent & Utilities")
    return {
        "category": category,
        "confidence": confidence,
        "source": source,
        "itc_eligible": 0 if itc_blocked else 1,
        "itc_blocked": 1 if itc_blocked else 0,
        "reason": f"Section 17(5) - {category}" if itc_blocked else "",
    }


def _classify_bart(text: str) -> dict | None:
    if not text:
        return None
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        return None
    try:
        logger.info(f"Layer 2 (bart-large-mnli): classifying '{text[:60]}'")
        resp = requests.post(
            "https://api-inference.huggingface.co/models/facebook/bart-large-mnli",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": text, "parameters": {"candidate_labels": CATEGORIES}},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            scores = data["scores"]
            labels = data["labels"]
            top = max(zip(labels, scores), key=lambda x: x[1])
            return _result(top[0], top[1], "bart-mnli")
        else:
            logger.warning(f"BART API error: {resp.status_code} {resp.text[:100]}")
            return None
    except Exception as e:
        logger.warning(f"BART error: {e}")
        return None


# Map from HF model consumer labels to ITC compliance categories
LABEL_TO_ITC_CATEGORY = {
    "Clothing": "Other",
    "Electronics": "IT & Software",
    "Food": "Other",
    "Office": "Office Expenses",
    "Pharma": "Professional Fees",
    "Travel": "Travel",
    "Vehicle": "Capital Goods",
}

def _classify_your_model(text: str) -> dict | None:
    if not text:
        return None
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        return None
    try:
        logger.info("Layer 3 (custom model): classifying...")
        resp = requests.post(
            "https://api-inference.huggingface.co/models/meet136/indicbert-gst-classifier",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"inputs": text},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                top = max(data[0], key=lambda x: x["score"])
                mapped_category = LABEL_TO_ITC_CATEGORY.get(top["label"], "Other")
                return _result(mapped_category, top["score"], "your-model")
        else:
            logger.warning(f"Custom model error: {resp.status_code} {resp.text[:100]}")
            return None
    except Exception as e:
        logger.warning(f"Custom model error: {e}")
        return None
