"""WhatsApp webhook — handles inbound messages and confirms OCR fields."""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from twilio.rest import Client
from loguru import logger
from app.core.security import limiter, sanitize_text
import os
import threading

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])


def get_twilio_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("host", request.url.hostname)
    path = request.url.path
    query = request.url.query
    url = f"{proto}://{host}{path}"
    if query:
        url += f"?{query}"
    return url


async def verify_twilio_signature(request: Request) -> dict:
    """Validate X-Twilio-Signature header. Returns form params dict."""
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    url = get_twilio_url(request)
    form_data = await request.form()
    params = dict(form_data)

    if not auth_token or not auth_token.strip():
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature verification (dev mode)")
        return params

    validator = RequestValidator(auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")

    logger.info(f"[Twilio] validating against URL: {url}")

    if not validator.validate(url, params, signature):
        logger.warning(f"Twilio signature validation failed for URL: {url}")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params

PENDING_CONFIRMATIONS = {}

FIELD_ALIASES = {
    "gstin":    "seller_gstin",
    "gst":      "seller_gstin",
    "invoice":  "invoice_no",
    "number":   "invoice_no",
    "date":     "invoice_date",
    "taxable":  "taxable_amount",
    "cgst":     "cgst",
    "sgst":     "sgst",
    "igst":     "igst",
    "total":    "total_amount",
    "amount":   "total_amount",
}

FIELD_LABELS = {
    "seller_gstin":   "GSTIN",
    "invoice_no":     "Invoice No",
    "invoice_date":   "Date (DD-MM-YYYY)",
    "taxable_amount": "Taxable Amount (Rs.)",
    "cgst":           "CGST (Rs.)",
    "sgst":           "SGST (Rs.)",
    "igst":           "IGST (Rs.)",
    "total_amount":   "Total (Rs.)",
}


def send_whatsapp(to: str, body: str):
    client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
    msg = client.messages.create(from_="whatsapp:+14155238886", to=f"whatsapp:{to}", body=body)
    logger.info(f"Sent WhatsApp to {to}: '{body[:80]}...'")
    return msg


# ═══════════════════════════════════════════════════════════════════════════════
# Inline OCR — no external dep, runs fully inside Twilio webhook time limit
# ═══════════════════════════════════════════════════════════════════════════════

INLINE_OCR_SYSTEM_PROMPT = """You are a precise OCR engine for INVOICES. Return ONLY valid JSON.

Rules:
- Extract numerical values as numbers (not strings)
- If field is not visible, use null
- Be conservative with reading blurry text
- Return ONLY the JSON object"""

INLINE_OCR_USER_PROMPT = """Extract these fields from the invoice image:
- seller_name
- seller_gstin (format: 2 digits + 5 alphanum + 3 state code + 3 alphanum + Z + 1 check digit)
- invoice_no
- invoice_date (in DD-MM-YYYY)
- taxable_amount
- cgst
- sgst
- igst
- total_amount

Return ONLY valid JSON, no other text."""


def process_image_background(image_url: str, user_phone: str):
    """Process invoice image and send result via WhatsApp."""
    from app.services.ocr_service import download_and_preprocess, parse_invoice_with_openrouter

    try:
        image_bytes = download_and_preprocess(image_url)
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        result = parse_invoice_with_openrouter(image_base64)

        if not result.get("success"):
            send_whatsapp(user_phone, f"❌ Error: {result.get('error', 'Unknown error')}")
            return

        fields = result.get("fields", {})
        conf = result.get("overall_confidence", 0)

        summary_lines = ["📄 *Extracted Invoice*\n"]
        for key, label in FIELD_LABELS.items():
            val = fields.get(key, {}).get("value")
            if val:
                if isinstance(val, float):
                    display_val = f"Rs.{val:,.2f}"
                else:
                    display_val = str(val)
                summary_lines.append(f"  {label}: {display_val}")

        summary_lines.append(f"\n  Confidence: {conf:.0%}")
        summary_lines.append(f"\n  *Reply to edit any field*")

        if conf < 0.85:
            summary_lines.append("\n  ⚠️ Some fields may be wrong — please verify")

        PENDING_CONFIRMATIONS[user_phone] = {
            "fields": fields,
            "image_base64": image_base64,
            "status": "pending_confirm",
        }

        send_whatsapp(user_phone, "\n".join(summary_lines))

    except Exception as e:
        logger.error(f"Background image processing error: {e}")
        error_msg = "❌ Image processing failed. Please try again with a clearer photo."
        send_whatsapp(user_phone, error_msg)


import base64
import re
from datetime import datetime
from app.services.invoice_service import save_invoice
from app.core.database import SessionLocal
from app.models.base import User, Invoice


def process_confirm(user_phone: str):
    """Finish saving after user confirms."""
    session = PENDING_CONFIRMATIONS.pop(user_phone, None)
    if not session:
        return

    fields = session["fields"]
    result = save_invoice(user_phone, fields)

    if result.get("success"):
        msg = "✅ Invoice saved successfully!\n"
        if result.get("itc_updated", 0) > 0:
            msg += f"💰 ITC claimed: Rs.{result['itc_updated']:,.2f}"
        send_whatsapp(user_phone, msg)
    else:
        send_whatsapp(user_phone, f"❌ Save failed: {result.get('error', 'Unknown')}")


def process_summary(user_phone: str):
    """Send filing summary for the month."""
    from app.services.compliance_engine import get_filing_deadlines, calculate_liability

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == user_phone).first()
        if not user:
            send_whatsapp(user_phone, "❌ No account found. Send an invoice photo first.")
            return

        period = datetime.now().strftime("%Y-%m")
        invoices = db.query(Invoice).filter(Invoice.user_id == user.id).all()
        total_purchases = sum(i.taxable_amt or 0 for i in invoices)
        total_itc = sum((i.cgst or 0) + (i.sgst or 0) + (i.igst or 0) for i in invoices)
        deadlines = get_filing_deadlines(period)

        msg = (
            f"📊 *Monthly Summary*\n\n"
            f"  Period: {period}\n"
            f"  Invoices: {len(invoices)}\n"
            f"  Purchases: Rs.{total_purchases:,.2f}\n"
            f"  ITC Available: Rs.{total_itc:,.2f}\n\n"
            f"📅 *Deadlines*\n"
            f"  GSTR-1: {deadlines.get('gstr1_deadline', '11th')} ({deadlines.get('days_to_gstr1', '?')} days)\n"
            f"  GSTR-3B: {deadlines.get('gstr3b_deadline', '20th')} ({deadlines.get('days_to_gstr3b', '?')} days)"
        )
        send_whatsapp(user_phone, msg)
    except Exception as e:
        logger.error(f"Summary error: {e}")
        send_whatsapp(user_phone, "❌ Could not generate summary")
    finally:
        db.close()


@router.post("/webhook")
@limiter.limit("30/minute")
async def whatsapp_webhook(
    request: Request,
    params: dict = Depends(verify_twilio_signature),
):
    From = params.get("From", "")
    Body = params.get("Body", "")
    NumMedia = params.get("NumMedia", "0")
    MediaUrl0 = params.get("MediaUrl0", "")
    MediaContentType0 = params.get("MediaContentType0", "")

    logger.info(f"Message from: {From} | Body: '{Body}' | Media: {NumMedia}")

    # Sanitize user input
    Body = sanitize_text(Body, strip_html=True, max_length=2000)

    if int(NumMedia) > 0 and "image" in MediaContentType0:
        threading.Thread(target=process_image_background, args=(MediaUrl0, From), daemon=True).start()
        response = MessagingResponse()
        response.message("Photo received! Processing... (10-20 seconds)")
        return PlainTextResponse(str(response), media_type="application/xml")

    user_phone = From.replace("whatsapp:", "")
    cmd = Body.strip().lower()

    if cmd == "summary":
        threading.Thread(target=process_summary, args=(user_phone,), daemon=True).start()
        response = MessagingResponse()
        response.message("Generating summary...")
        return PlainTextResponse(str(response), media_type="application/xml")

    if cmd == "status" or cmd == "ok" or cmd == "done":
        threading.Thread(target=process_confirm, args=(user_phone,), daemon=True).start()
        response = MessagingResponse()
        response.message("Saving invoice...")
        return PlainTextResponse(str(response), media_type="application/xml")

    # Check if user is editing a field
    session = PENDING_CONFIRMATIONS.get(user_phone)
    if session and session.get("status") == "pending_confirm" and cmd not in ("ok", "done", "status"):
        # Try to parse field edit: "FIELD: VALUE"
        match = re.match(r"(\w+)\s*[:\-]?\s*(.+)", cmd, re.IGNORECASE)
        if match:
            field_key = match.group(1).lower()
            new_value = match.group(2).strip()

            # Map alias to actual field key
            actual_key = FIELD_ALIASES.get(field_key, field_key)

            if actual_key in FIELD_LABELS:
                fields = session["fields"]
                fields.setdefault(actual_key, {})["value"] = new_value
                logger.info(f"Field edited: {actual_key} = {new_value}")

                send_whatsapp(user_phone, f"✅ {FIELD_LABELS[actual_key]} updated to '{new_value}'.\nReply OK to save or edit another field.")
                return PlainTextResponse("", media_type="application/xml")

    response = MessagingResponse()
    response.message(
        "Namaste! 🙏\n\n"
        "VyapaarBandhu mein aapka swagat hai!\n\n"
        "📸 *Invoice scan karein* — Photo bhejne par auto-extract hoga\n"
        "📊 *Summary* — This month ka GST summary\n"
        "✏️  *Edit* — Field: Value (e.g., GSTIN: 07AABCS1234R1Z5)\n"
        "✅ *OK / Status / Done* — Confirm aur save karein"
    )
    return PlainTextResponse(str(response), media_type="application/xml")
