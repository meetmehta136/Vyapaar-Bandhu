from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.core.auth_utils import get_current_ca
from app.models.base import Invoice, GSTLedger, User, CAPartner
from datetime import datetime
from pydantic import BaseModel
import io
import json
import os

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    REPORTLAB = True
except ImportError:
    REPORTLAB = False

router = APIRouter(prefix="/api", tags=["Dashboard API"])

BLOCKED_CATEGORIES = {"Food & Beverages", "Food (Blocked)", "Personal Vehicle", "Blocked"}


class ClientCreate(BaseModel):
    name:  str
    phone: str
    gstin: str = ""
    state: str = ""


# ── helpers ──────────────────────────────────────────────────────────────────

def ca_user_ids(ca_id: int, db: Session):
    """Return list of user IDs belonging to this CA."""
    return [u.id for u in db.query(User.id).filter(User.ca_id == ca_id).all()]


# ── Dashboard stats ───────────────────────────────────────────────────────────

@router.get("/dashboard/stats")
def get_dashboard_stats(
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        period  = datetime.now().strftime("%Y-%m")
        uid_list = ca_user_ids(ca.id, db)

        itc_row = (
            db.query(func.sum(GSTLedger.itc_available))
            .filter(GSTLedger.period == period, GSTLedger.user_id.in_(uid_list))
            .scalar() or 0
        )
        total_invoices = (
            db.query(func.count(Invoice.id))
            .filter(Invoice.user_id.in_(uid_list))
            .scalar() or 0
        )
        pending_invoices = (
            db.query(func.count(Invoice.id))
            .filter(Invoice.user_id.in_(uid_list), Invoice.status == "pending")
            .scalar() or 0
        )
        return {
            "total_itc":        round(float(itc_row), 2),
            "total_invoices":   total_invoices,
            "pending_invoices": pending_invoices,
            "total_clients":    len(uid_list),
            "period":           period,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Clients ───────────────────────────────────────────────────────────────────

@router.get("/clients")
def get_clients(
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        period = datetime.now().strftime("%Y-%m")
        users  = db.query(User).filter(User.ca_id == ca.id).all()
        result = []
        for user in users:
            ledger = (
                db.query(GSTLedger)
                .filter(GSTLedger.user_id == user.id, GSTLedger.period == period)
                .first()
            )
            invoice_count = (
                db.query(func.count(Invoice.id))
                .filter(Invoice.user_id == user.id)
                .scalar() or 0
            )
            itc = float(ledger.itc_available) if ledger else 0
            status = "compliant" if itc > 1000 else "attention" if itc > 0 else "at-risk"
            risk_score = min(100, int((itc / 500) * 10 + invoice_count * 5))
            result.append({
                "id":               str(user.id),
                "name":             user.business_name or user.phone or "Unknown",
                "gstin":            user.gstin or "",
                "state":            user.state_code or "",
                "whatsapp":         user.phone or "",
                "itcThisMonth":     itc,
                "invoiceCount":     invoice_count,
                "complianceStatus": status,
                "riskScore":        min(risk_score, 100),
            })
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/clients")
def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        user = User(
            business_name=client.name,
            phone=client.phone,
            gstin=client.gstin.upper().strip() if client.gstin else "",
            state_code=client.state,
            ca_id=ca.id,           # ← link client to this CA
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            phone  = client.phone if client.phone.startswith("+") else f"+91{client.phone}"
            twilio.messages.create(
                from_="whatsapp:+14155238886",
                to=f"whatsapp:{phone}",
                body=(
                    f"Namaste! {client.name} 🙏\n\n"
                    f"Aapke CA ne aapko VyapaarBandhu se connect kiya hai.\n\n"
                    f"Invoice ki photo bhejiye — hum ITC calculate kar denge!\n\n"
                    f"VyapaarBandhu 🤝"
                ),
            )
        except Exception as wa_err:
            print(f"WhatsApp welcome skipped: {wa_err}")

        return {"success": True, "id": str(user.id)}
    except Exception as e:
        return {"error": str(e)}


@router.post("/clients/{client_id}/remind")
def send_reminder(
    client_id: int,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        user = db.query(User).filter(User.id == client_id, User.ca_id == ca.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Client not found")
        from twilio.rest import Client as TwilioClient
        twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        phone  = user.phone if user.phone.startswith("+") else f"+91{user.phone}"
        twilio.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{phone}",
            body=(
                f"Namaste {user.business_name or 'ji'} 🙏\n\n"
                f"GSTR-3B filing ki deadline nazdeek aa rahi hai!\n\n"
                f"Kripya baaki invoices upload karein taaki ITC claim ho sake.\n\n"
                f"VyapaarBandhu 📊"
            ),
        )
        return {"success": True, "message": f"Reminder sent to {user.phone}"}
    except Exception as e:
        return {"error": str(e)}


@router.get("/clients/{client_id}")
def get_client_detail(
    client_id: int,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        user = db.query(User).filter(User.id == client_id, User.ca_id == ca.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Client not found")

        invoices = db.query(Invoice).filter(Invoice.user_id == client_id).all()
        period   = datetime.now().strftime("%Y-%m")
        ledger   = (
            db.query(GSTLedger)
            .filter(GSTLedger.user_id == client_id, GSTLedger.period == period)
            .first()
        )

        invoice_list = []
        for inv in invoices:
            itc   = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            invoice_list.append({
                "id":             str(inv.id),
                "invoiceNo":      inv.invoice_no or "",
                "date":           str(inv.date or ""),
                "supplierGstin":  inv.seller_gstin or "",
                "taxableAmt":     float(inv.taxable_amt or 0),
                "total":          total,
                "cgst":           float(inv.cgst or 0),
                "sgst":           float(inv.sgst or 0),
                "igst":           float(inv.igst or 0),
                "itc":            itc,
                "status":         inv.status or "confirmed",
                "aiCategory":     inv.ai_category or "General",     # ← FIXED: was hardcoded
                "aiConfidence":   round(float(inv.ai_confidence or 0), 2),
                "aiKeywords":     inv.ai_keywords or "",
                "itcEligible":    (inv.ai_category or "General") not in BLOCKED_CATEGORIES,
                "userCorrected":  bool(inv.user_corrected),
            })

        return {
            "id":           str(user.id),
            "name":         user.business_name or user.phone or "Unknown",
            "gstin":        user.gstin or "",
            "state":        user.state_code or "",
            "whatsapp":     user.phone or "",
            "itcThisMonth": float(ledger.itc_available) if ledger else 0,
            "invoiceCount": len(invoice_list),
            "invoices":     invoice_list,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/clients/{client_id}/gstr3b-json")
def get_gstr3b_json(
    client_id: int,
    period: str = "",
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        user = db.query(User).filter(User.id == client_id, User.ca_id == ca.id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Client not found")

        if not user.gstin:
            raise HTTPException(status_code=400, detail="Client GSTIN not set. Update client profile first.")

        # Period defaults to current month
        if not period:
            period = datetime.now().strftime("%Y-%m")

        try:
            year, month   = period.split("-")
            month_start   = datetime(int(year), int(month), 1)
            month_end     = datetime(int(year) + 1, 1, 1) if int(month) == 12 else datetime(int(year), int(month) + 1, 1)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid period format. Use YYYY-MM")

        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.user_id == client_id,
                Invoice.status  == "confirmed",
                Invoice.date    >= month_start,
                Invoice.date    <  month_end,
            )
            .all()
        )

        # Aggregate — split blocked vs eligible per Section 17(5)
        el_cgst = el_sgst = el_igst = 0.0
        bl_cgst = bl_sgst = bl_igst = 0.0
        total_taxable = 0.0
        inward_supplies = []

        for inv in invoices:
            cgst    = float(inv.cgst or 0)
            sgst    = float(inv.sgst or 0)
            igst    = float(inv.igst or 0)
            taxable = float(inv.taxable_amt or 0)
            cat     = inv.ai_category or "General"
            total_taxable += taxable

            if cat in BLOCKED_CATEGORIES:
                bl_cgst += cgst; bl_sgst += sgst; bl_igst += igst
            else:
                el_cgst += cgst; el_sgst += sgst; el_igst += igst

            inward_supplies.append({
                "invoice_no":      inv.invoice_no,
                "supplier_gstin":  inv.seller_gstin,
                "invoice_date":    inv.date.strftime("%d-%m-%Y") if inv.date else "",
                "taxable_value":   round(taxable, 2),
                "igst":            round(igst, 2),
                "cgst":            round(cgst, 2),
                "sgst":            round(sgst, 2),
                "ai_category":     cat,
                "ai_confidence":   round(float(inv.ai_confidence or 0), 2),
                "itc_eligible":    cat not in BLOCKED_CATEGORIES,
            })

        ret_period = f"{str(month).zfill(2)}{year}"   # MMYYYY as required by GST portal

        # Official GSTR-3B JSON format (GST portal spec)
        gstr3b = {
            "gstin":      user.gstin,              # ← FIXED: real GSTIN from DB
            "ret_period": ret_period,
            "inward_dtls": {
                "isup_details": [{
                    "ty":    "OTH",
                    "inter": round(el_igst, 2),
                    "intra": round(el_cgst + el_sgst, 2),
                    "exmt":  0,
                    "ngsup": 0,
                }]
            },
            "itc_elg": {
                "itc_avl": [
                    {"ty": "IMPG", "igst": 0,                    "cgst": 0,                    "sgst": 0,                    "cess": 0},
                    {"ty": "IMPS", "igst": 0,                    "cgst": 0,                    "sgst": 0,                    "cess": 0},
                    {"ty": "ISRC", "igst": 0,                    "cgst": 0,                    "sgst": 0,                    "cess": 0},
                    {"ty": "ITC",  "igst": round(el_igst, 2),    "cgst": round(el_cgst, 2),    "sgst": round(el_sgst, 2),    "cess": 0},
                    {"ty": "OTH",  "igst": 0,                    "cgst": 0,                    "sgst": 0,                    "cess": 0},
                ],
                "itc_rev": [
                    {"ty": "RUL", "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},
                    {"ty": "OTH", "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},
                ],
                "itc_net": {
                    "igst": round(el_igst, 2),
                    "cgst": round(el_cgst, 2),
                    "sgst": round(el_sgst, 2),
                    "cess": 0,
                },
                "itc_inelg": [
                    {"ty": "RUL", "igst": round(bl_igst, 2), "cgst": round(bl_cgst, 2), "sgst": round(bl_sgst, 2), "cess": 0},
                    {"ty": "OTH", "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},
                ],
            },
            "sup_details": {
                "osup_det":      {"txval": 0, "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},   # FIXED: was csgst
                "osup_zero":     {"txval": 0, "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},
                "osup_nil_exmp": {"txval": 0},
                "isup_rev":      {"txval": 0, "igst": 0, "cgst": 0, "sgst": 0, "cess": 0},
                "osup_nongst":   {"txval": 0},
            },
            "inter_sup": {"unreg_details": [], "comp_details": [], "uin_details": []},
            "intr_ltfee": {
                "intr_details": {"cgst": 0, "sgst": 0, "igst": 0},
                "fee_details":  {"cgst": 0, "sgst": 0, "igst": 0},
            },
            "_vyapaarbandhu_meta": {
                "generated_by":    "VyapaarBandhu AI",
                "generated_at":    datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "period":          period,
                "client_name":     user.business_name or "",
                "total_invoices":  len(invoices),
                "total_taxable":   round(total_taxable, 2),
                "eligible_itc":    round(el_cgst + el_sgst + el_igst, 2),
                "blocked_itc":     round(bl_cgst + bl_sgst + bl_igst, 2),
                "inward_supplies": inward_supplies,
            },
        }

        json_bytes = json.dumps(gstr3b, indent=2).encode("utf-8")
        filename   = f"GSTR3B_{user.gstin}_{ret_period}.json"

        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        return {"error": str(e)}


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/invoices")
def get_invoices(
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        uid_list = ca_user_ids(ca.id, db)
        invoices = (
            db.query(Invoice)
            .filter(Invoice.user_id.in_(uid_list))
            .order_by(Invoice.id.desc())
            .all()
        )
        users_map = {u.id: u for u in db.query(User).filter(User.ca_id == ca.id).all()}

        result = []
        for inv in invoices:
            user  = users_map.get(inv.user_id)
            itc   = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            cat   = inv.ai_category or "General"
            result.append({
                "id":            str(inv.id),
                "clientId":      str(inv.user_id),
                "clientName":    (user.business_name or user.phone or "Unknown") if user else "Unknown",
                "invoiceNo":     inv.invoice_no or "",
                "date":          str(inv.date or ""),
                "supplierGstin": inv.seller_gstin or "",
                "taxableAmt":    float(inv.taxable_amt or 0),
                "total":         total,
                "cgst":          float(inv.cgst or 0),
                "sgst":          float(inv.sgst or 0),
                "igst":          float(inv.igst or 0),
                "itc":           itc,
                "status":        inv.status or "confirmed",
                "aiCategory":    cat,                              # ← FIXED: real value
                "aiConfidence":  round(float(inv.ai_confidence or 0), 2),
                "aiKeywords":    inv.ai_keywords or "",
                "itcEligible":   cat not in BLOCKED_CATEGORIES,
                "userCorrected": bool(inv.user_corrected),
            })
        return result
    except Exception as e:
        return {"error": str(e)}


@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        uid_list = ca_user_ids(ca.id, db)
        inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id.in_(uid_list)).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        inv.status = "confirmed"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "confirmed"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        uid_list = ca_user_ids(ca.id, db)
        inv = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.user_id.in_(uid_list)).first()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        inv.status = "rejected"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "rejected"}
    except Exception as e:
        return {"error": str(e)}


# ── Alerts ────────────────────────────────────────────────────────────────────

@router.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        users  = db.query(User).filter(User.ca_id == ca.id).all()
        alerts = []
        period = datetime.now().strftime("%Y-%m")
        for user in users:
            invoice_count = (
                db.query(func.count(Invoice.id))
                .filter(Invoice.user_id == user.id)
                .scalar() or 0
            )
            if invoice_count == 0:
                alerts.append({
                    "id":             f"alert-{user.id}",
                    "clientName":     user.business_name or user.phone or "Unknown",
                    "type":           "No Invoices",
                    "message":        "No invoices uploaded this month. ITC at risk.",
                    "priority":       "high",
                    "dueDate":        f"{period}-20",
                    "daysRemaining":  11,
                    "resolved":       False,
                })
            elif invoice_count < 3:
                alerts.append({
                    "id":             f"alert-low-{user.id}",
                    "clientName":     user.business_name or user.phone or "Unknown",
                    "type":           "Low Invoice Count",
                    "message":        f"Only {invoice_count} invoice(s) uploaded. More expected.",
                    "priority":       "medium",
                    "dueDate":        f"{period}-25",
                    "daysRemaining":  16,
                    "resolved":       False,
                })
        return alerts
    except Exception as e:
        return {"error": str(e)}


# ── Admin ─────────────────────────────────────────────────────────────────────

@router.get("/admin/stats")
def get_admin_stats(
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    try:
        uid_list = ca_user_ids(ca.id, db)
        total_invoices = db.query(func.count(Invoice.id)).filter(Invoice.user_id.in_(uid_list)).scalar() or 0
        total_itc      = db.query(func.sum(GSTLedger.itc_available)).filter(GSTLedger.user_id.in_(uid_list)).scalar() or 0
        confirmed      = db.query(func.count(Invoice.id)).filter(Invoice.user_id.in_(uid_list), Invoice.status == "confirmed").scalar() or 0
        pending        = db.query(func.count(Invoice.id)).filter(Invoice.user_id.in_(uid_list), Invoice.status == "pending").scalar() or 0
        users          = db.query(User).filter(User.ca_id == ca.id).order_by(User.id.desc()).all()

        user_list = []
        for u in users:
            inv_count = db.query(func.count(Invoice.id)).filter(Invoice.user_id == u.id).scalar() or 0
            user_list.append({
                "id":           str(u.id),
                "name":         u.business_name or "Unknown",
                "phone":        u.phone or "",
                "gstin":        u.gstin or "",
                "state":        u.state_code or "",
                "invoiceCount": inv_count,
                "joinedAt":     str(u.created_at or "")[:10],
            })

        return {
            "total_users":         len(uid_list),
            "total_invoices":      total_invoices,
            "total_itc":           round(float(total_itc), 2),
            "confirmed_invoices":  confirmed,
            "pending_invoices":    pending,
            "mrr":                 len(uid_list) * 299,
            "users":               user_list,
        }
    except Exception as e:
        return {"error": str(e)}


# ── Filing PDF ────────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/filing-pdf")
def get_filing_pdf(
    client_id: int,
    db: Session = Depends(get_db),
    ca: CAPartner = Depends(get_current_ca),
):
    if not REPORTLAB:
        return {"error": "reportlab not installed"}
    user = db.query(User).filter(User.id == client_id, User.ca_id == ca.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")

    invoices = db.query(Invoice).filter(Invoice.user_id == client_id).all()
    buf = io.BytesIO()
    p   = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, h - 50, "VyapaarBandhu — Filing Summary")
    p.setFont("Helvetica", 11)
    p.drawString(50, h - 80,  f"Client: {user.business_name or user.phone or 'Unknown'}")
    p.drawString(50, h - 100, f"GSTIN:  {user.gstin or 'Not set'}")
    p.drawString(50, h - 120, f"Period: {datetime.now().strftime('%B %Y')}")

    p.setFont("Helvetica-Bold", 11)
    p.drawString(50,  h - 160, "Invoice No")
    p.drawString(200, h - 160, "Date")
    p.drawString(310, h - 160, "Taxable")
    p.drawString(390, h - 160, "ITC")
    p.drawString(460, h - 160, "Category")
    p.drawString(560, h - 160, "Status")

    y         = h - 180
    total_itc = 0.0
    p.setFont("Helvetica", 10)

    for inv in invoices:
        itc   = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
        total_itc += itc
        p.drawString(50,  y, inv.invoice_no or "—")
        p.drawString(200, y, str(inv.date or "")[:10])
        p.drawString(310, y, f"Rs {float(inv.taxable_amt or 0):.2f}")
        p.drawString(390, y, f"Rs {itc:.2f}")
        p.drawString(460, y, (inv.ai_category or "General")[:12])
        p.drawString(560, y, inv.status or "confirmed")
        y -= 20
        if y < 100:
            p.showPage()
            y = h - 50

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y - 20, f"Total ITC Eligible: Rs {total_itc:.2f}")
    p.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=filing_{client_id}_{datetime.now().strftime('%Y%m')}.pdf"},
    )
