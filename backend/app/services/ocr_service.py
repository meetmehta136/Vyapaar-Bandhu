"""OCR service — download image, preprocess, and extract invoice fields via OpenRouter VLM.
Uses loguru for structured logging."""
import os, requests, base64, json
from loguru import logger


def download_and_preprocess(image_url: str) -> bytes:
    """Download image from URL, preprocess with OpenCV if available."""
    logger.info(f"Downloading image from {image_url}")
    resp = requests.get(image_url, timeout=30)
    logger.info(f"Download status: {resp.status_code}")
    image_bytes = resp.content
    logger.info(f"Downloaded: {len(image_bytes)} bytes")

    try:
        import cv2
        import numpy as np

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Quality check
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        quality_score = min(int(laplacian_var), 100)
        issues = []
        if laplacian_var < 10:
            issues.append("blurry")
        if img.shape[0] < 200 or img.shape[1] < 200:
            issues.append("too_small")

        logger.info(f"Image quality score: {quality_score}/100 | Issues: {issues}")

        if quality_score < 30 or issues:
            logger.info("Preprocessing image (CLAHE + denoise + deskew + threshold)...")
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            denoised = cv2.fastNlMeansDenoising(enhanced, h=30)
            coords = np.column_stack(np.where(denoised > 0))
            if len(coords) > 10:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = 90 + angle
                if abs(angle) > 2:
                    h, w = denoised.shape
                    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
                    denoised = cv2.warpAffine(denoised, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            success, buf = cv2.imencode(".jpg", thresh, [cv2.IMWRITE_JPEG_QUALITY, 90])
            if success:
                image_bytes = buf.tobytes()
                logger.info(f"Preprocessed: {len(image_bytes)} bytes")
            else:
                logger.warning("Preprocessing encode failed — using original")
        else:
            logger.info("Image quality good — skipping preprocessing")

    except ImportError:
        logger.debug("OpenCV not available — skipping preprocessing")
    except Exception as e:
        logger.warning(f"Preprocessing skipped: {e}")

    return image_bytes


def parse_invoice_with_openrouter(image_base64: str) -> dict:

    logger.info("Sending to OpenRouter VLM...")

    # Try cache first
    try:
        from app.services.ocr_cache import ocr_cache
        image_bytes = base64.b64decode(image_base64)
        cached = ocr_cache.get_sync(image_bytes)
        if cached:
            logger.info("Cache hit — returning cached result")
            return cached
    except Exception:
        pass

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {"success": False, "error": "OPENROUTER_API_KEY not set"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": """
You are an invoice OCR assistant. Extract fields from this GST invoice image.
Return ONLY valid JSON (no markdown, no backticks).

Schema:
{
  "seller_name": {"value": "...", "confidence": 0.0-1.0},
  "seller_gstin": {"value": "...", "confidence": 0.0-1.0},
  "invoice_no": {"value": "...", "confidence": 0.0-1.0},
  "invoice_date": {"value": "DD-MM-YYYY", "confidence": 0.0-1.0},
  "taxable_amount": {"value": number, "confidence": 0.0-1.0},
  "cgst": {"value": number, "confidence": 0.0-1.0},
  "sgst": {"value": number, "confidence": 0.0-1.0},
  "igst": {"value": number, "confidence": 0.0-1.0},
  "total_amount": {"value": number, "confidence": 0.0-1.0},
  "seller_address": {"value": "...", "confidence": 0.0-1.0},
  "buyer_name": {"value": "...", "confidence": 0.0-1.0},
  "buyer_gstin": {"value": "...", "confidence": 0.0-1.0},
  "description": {"value": "...", "confidence": 0.0-1.0}
}

Rules:
- confidence should be LOW (0.3-0.6) if text is blurry/ambiguous
- description should be the main product/service name — keep it short, 3-8 words
- Return null for missing fields
- Return ONLY the JSON object, nothing else"""
                },
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
            ]
        }],
        "max_tokens": 5000,
        "temperature": 0,
        "include_reasoning": False,
        "transforms": [],
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=40
        )

        logger.info(f"OpenRouter status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"OpenRouter error: {response.text[:300]}")
            return {"success": False, "error": f"OpenRouter error: {response.status_code}"}

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        if content is None:
            logger.error(f"Empty response. Full result: {result}")
            return {"success": False, "error": "Empty response from OpenRouter"}

        raw = content.strip()
        logger.debug(f"OpenRouter response: {raw}")

        # Remove markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]

        fields = json.loads(raw)

        filled = [f for f in fields.values() if f["value"] is not None]
        avg = sum(f["confidence"] for f in filled) / len(filled) if filled else 0

        logger.info(f"Fields extracted: {[(k, v['value']) for k, v in fields.items() if v['value']]}")
        logger.info(f"Confidence: {avg:.2f} | Filled: {len(filled)}/{len(fields)}")
        if fields.get("description", {}).get("value"):
            logger.info(f"Description: {fields['description']['value']}")

        result_data = {
            "success": True,
            "fields": fields,
            "overall_confidence": round(avg, 2),
            "needs_confirmation": avg < 0.85,
            "filled_count": len(filled),
            "total_fields": len(fields)
        }

        # Cache on success
        try:
            from app.services.ocr_cache import ocr_cache
            image_bytes = base64.b64decode(image_base64)
            ocr_cache.set_sync(image_bytes, result_data)
        except Exception:
            pass

        return result_data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e} | Raw: {raw}")
        return {"success": False, "error": "Could not parse response"}

    except Exception as e:
        logger.error(f"OpenRouter error: {e}")
        return {"success": False, "error": str(e)}


def parse_invoice_fields(full_text: str) -> dict:
    pass
