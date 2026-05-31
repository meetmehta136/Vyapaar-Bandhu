"""Invoice service — save, deduplicate, and update ITC."""
import re
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.base import User, Invoice, GSTLedger
from app.core.database import SessionLocal
from loguru import logger


def save_invoice(phone: str, ocr_fields: dict) -> dict:
    """Save or update an invoice from OCR fields. Returns invoice data."""
    db = SessionLocal()
    try:
        phone_clean = re.sub(r"\D", "", phone)[-10:]
        if len(phone_clean) != 10:
            return {"success": False, "error": "Invalid phone"}

        user = db.query(User).filter(User.phone == phone_clean).first()
        if not user:
            user = User(phone=phone_clean)
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"New user created: {phone_clean}")

        def _v(key):
            val = ocr_fields.get(key, {}).get("value")
            try:
                return float(val) if val else 0.0
            except (ValueError, TypeError):
                return 0.0

        invoice_no = ocr_fields.get("invoice_no", {}).get("value")
        taxable_amt = _v("taxable_amount")
        cgst = _v("cgst")
        sgst = _v("sgst")
        igst = _v("igst")
        total_amount = _v("total_amount") or taxable_amt + cgst + sgst + igst

        date_str = ocr_fields.get("invoice_date", {}).get("value")
        invoice_date = None
        if date_str:
            for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    invoice_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue

        if invoice_no:
            existing = db.query(Invoice).filter(
                Invoice.user_id == user.id,
                Invoice.invoice_no == invoice_no,
            ).first()
            if existing:
                logger.info(f"Duplicate detected: Invoice #{invoice_no} already saved as ID={existing.id}")
                db.close()
                return {
                    "success": True,
                    "invoice_id": existing.id,
                    "duplicate": True,
                    "message": "Invoice already exists"
                }

        invoice = Invoice(
            user_id=user.id,
            seller_gstin=ocr_fields.get("seller_gstin", {}).get("value"),
            invoice_no=invoice_no,
            date=invoice_date,
            taxable_amt=taxable_amt,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            status="extracted",
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        logger.info(f"Invoice saved: ID={invoice.id}")

        # Update GSTLedger
        period = invoice_date.strftime("%Y-%m") if invoice_date else datetime.now().strftime("%Y-%m")
        ledger = db.query(GSTLedger).filter(
            GSTLedger.user_id == user.id,
            GSTLedger.period == period,
        ).first()

        if not ledger:
            ledger = GSTLedger(user_id=user.id, period=period)
            db.add(ledger)

        itc_amount = cgst + sgst + igst
        ledger.total_purchases = (ledger.total_purchases or 0) + taxable_amt
        ledger.itc_available = (ledger.itc_available or 0) + itc_amount
        ledger.net_liability = (ledger.net_liability or 0) - itc_amount
        db.commit()

        logger.info(f"ITC updated: +Rs.{itc_amount} | Total ITC: Rs.{ledger.itc_available}")

        db.close()
        return {
            "success": True,
            "invoice_id": invoice.id,
            "user_id": user.id,
            "period": period,
            "itc_updated": itc_amount,
        }

    except Exception as e:
        logger.error(f"DB Error saving invoice: {e}")
        db.close()
        return {"success": False, "error": str(e)}
