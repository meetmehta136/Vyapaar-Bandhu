from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger
from app.core.database import get_db
from app.models.base import Invoice, GSTLedger, User, CAPartner
from app.core.auth_utils import get_current_ca
from app.core.security import limiter
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

class ClientCreate(BaseModel):
    name: str
    phone: str
    gstin: str = ""
    state: str = ""

@router.get("/dashboard/stats")
def get_dashboard_stats(current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        period = datetime.now().strftime("%Y-%m")
        itc_row = db.query(func.sum(GSTLedger.itc_available)).filter(GSTLedger.period == period).scalar() or 0
        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
        pending_invoices = db.query(func.count(Invoice.id)).filter(Invoice.status == "pending").scalar() or 0
        total_users = db.query(func.count(User.id)).scalar() or 0
        return {
            "total_itc": round(float(itc_row), 2),
            "total_invoices": total_invoices,
            "pending_invoices": pending_invoices,
            "total_clients": total_users,
            "period": period
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/clients")
def get_clients(
    current_user: CAPartner = Depends(get_current_ca),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    try:
        period = datetime.now().strftime("%Y-%m")
        total = db.query(func.count(User.id)).scalar() or 0
        users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
        user_ids = [u.id for u in users]

        # Batch: one query for all ledgers
        ledgers = db.query(GSTLedger).filter(
            GSTLedger.user_id.in_(user_ids), GSTLedger.period == period
        ).all()
        ledger_map = {l.user_id: l for l in ledgers}

        # Batch: one query for all invoice counts
        invoice_counts = db.query(
            Invoice.user_id, func.count(Invoice.id)
        ).filter(Invoice.user_id.in_(user_ids)).group_by(Invoice.user_id).all()
        count_map = {row[0]: row[1] for row in invoice_counts}

        result = []
        for user in users:
            ledger = ledger_map.get(user.id)
            invoice_count = count_map.get(user.id, 0)
            itc = float(ledger.itc_available) if ledger else 0
            if itc > 1000:
                status = "compliant"
            elif itc > 0:
                status = "attention"
            else:
                status = "at-risk"
            risk_score = min(100, int((itc / 500) * 10 + invoice_count * 5))
            result.append({
                "id": str(user.id),
                "name": user.business_name or user.phone or "Unknown",
                "gstin": user.gstin or "",
                "state": user.state_code or "",
                "whatsapp": user.phone or "",
                "itcThisMonth": itc,
                "invoiceCount": invoice_count,
                "complianceStatus": status,
                "riskScore": min(risk_score, 100)
            })
        return {"data": result, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        return {"error": str(e)}

@router.post("/clients")
def create_client(client: ClientCreate, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        user = User(
            business_name=client.name,
            phone=client.phone,
            gstin=client.gstin,
            state_code=client.state
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Auto-send WhatsApp welcome message
        try:
            from twilio.rest import Client as TwilioClient
            twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
            phone = client.phone if client.phone.startswith("+") else f"+91{client.phone}"
            twilio.messages.create(
                from_="whatsapp:+14155238886",
                to=f"whatsapp:{phone}",
                body=f"Namaste! {client.name} 🙏\n\nAapke CA ne aapko VyapaarBandhu se connect kiya hai.\n\nAb aap apni invoices ki photo yahan bhej sakte hain aur hum automatically ITC calculate karenge.\n\nShuru karne ke liye 'hello' likhiye ya invoice ki photo bhejiye!\n\nVyapaarBandhu 🤝"
            )
        except Exception as wa_err:
            logger.warning(f"WhatsApp welcome skipped for {user.phone}: {wa_err}")

        return {"success": True, "id": str(user.id)}
    except Exception as e:
        return {"error": str(e)}

@router.post("/clients/{client_id}/remind")
@limiter.limit("5/minute")
def send_reminder(request: Request, client_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == client_id).first()
        if not user:
            return {"error": "Client not found"}
        from twilio.rest import Client as TwilioClient
        twilio = TwilioClient(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))
        phone = user.phone if user.phone.startswith("+") else f"+91{user.phone}"
        twilio.messages.create(
            from_="whatsapp:+14155238886",
            to=f"whatsapp:{phone}",
            body=f"Namaste {user.business_name or 'ji'} 🙏\n\nGSTR-3B filing ki deadline nazdeek aa rahi hai!\n\nKripya apni baaki invoices upload karein taaki ITC claim ho sake.\n\nVyapaarBandhu 📊"
        )
        return {"success": True, "message": f"Reminder sent to {user.phone}"}
    except Exception as e:
        return {"error": str(e)}

@router.get("/clients/{client_id}/gstr3b-json")
def get_gstr3b_json(client_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == client_id).first()
        if not user:
            return {"error": "Client not found"}

        period = datetime.now().strftime("%Y-%m")
        invoices = db.query(Invoice).filter(
            Invoice.user_id == client_id,
            Invoice.status == "confirmed"
        ).all()

        # Separate intra-state (CGST+SGST) vs inter-state (IGST)
        intra_taxable = 0.0
        intra_cgst = 0.0
        intra_sgst = 0.0
        inter_taxable = 0.0
        inter_igst = 0.0
        total_itc = 0.0

        for inv in invoices:
            cgst = float(inv.cgst or 0)
            sgst = float(inv.sgst or 0)
            igst = float(inv.igst or 0)
            taxable = float(inv.taxable_amt or 0)

            if igst > 0:
                inter_taxable += taxable
                inter_igst += igst
            else:
                intra_taxable += taxable
                intra_cgst += cgst
                intra_sgst += sgst

            total_itc += cgst + sgst + igst

        net_liability = max(0, 0 - total_itc)  # simplified: no outward supplies yet

        # GSTN GSTR-3B format
        gstr3b = {
            "gstin": user.gstin or "",
            "ret_period": datetime.now().strftime("%m%Y"),
            "filing_period": period,
            "generated_by": "VyapaarBandhu",
            "generated_at": datetime.now().isoformat(),
            "sup_details": {
                "osup_det": {
                    "txval": 0,
                    "iamt": 0,
                    "camt": 0,
                    "samt": 0,
                    "csamt": 0
                },
                "osup_zero": {
                    "txval": 0,
                    "iamt": 0,
                    "csamt": 0
                },
                "osup_nil_exmp": {
                    "txval": 0
                },
                "isup_rev": {
                    "txval": 0,
                    "iamt": 0,
                    "camt": 0,
                    "samt": 0,
                    "csamt": 0
                },
                "osup_nongst": {
                    "txval": 0
                }
            },
            "inter_sup": {
                "unreg_details": [],
                "comp_details": [],
                "uin_details": []
            },
            "itc_elg": {
                "itc_avl": [
                    {
                        "ty": "IMPG",
                        "iamt": round(inter_igst, 2),
                        "camt": round(intra_cgst, 2),
                        "samt": round(intra_sgst, 2),
                        "csamt": 0
                    }
                ],
                "itc_rev": [],
                "itc_net": {
                    "iamt": round(inter_igst, 2),
                    "camt": round(intra_cgst, 2),
                    "samt": round(intra_sgst, 2),
                    "csamt": 0
                },
                "itc_inelg": [
                    {"ty": "RUL", "iamt": 0, "camt": 0, "samt": 0, "csamt": 0}
                ]
            },
            "inward_sup": {
                "isup_details": [
                    {
                        "ty": "GST",
                        "inter": round(inter_taxable, 2),
                        "intra": round(intra_taxable, 2)
                    }
                ]
            },
            "tax_liability": {
                "net_itc": round(total_itc, 2),
                "net_liability": round(net_liability, 2),
                "summary": {
                    "total_invoices": len(invoices),
                    "intra_state_invoices": len([i for i in invoices if (i.igst or 0) == 0]),
                    "inter_state_invoices": len([i for i in invoices if (i.igst or 0) > 0]),
                    "total_taxable_value": round(intra_taxable + inter_taxable, 2),
                    "total_cgst": round(intra_cgst, 2),
                    "total_sgst": round(intra_sgst, 2),
                    "total_igst": round(inter_igst, 2),
                    "total_itc_eligible": round(total_itc, 2)
                }
            }
        }

        json_bytes = json.dumps(gstr3b, indent=2).encode("utf-8")
        filename = f"GSTR3B_{user.gstin or client_id}_{datetime.now().strftime('%m%Y')}.json"

        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        return {"error": str(e)}

@router.get("/clients/{client_id}/filing-pdf")
def get_filing_pdf(client_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    if not REPORTLAB:
        return {"error": "reportlab not installed"}
    user = db.query(User).filter(User.id == client_id).first()
    if not user:
        return {"error": "Client not found"}
    invoices = db.query(Invoice).filter(Invoice.user_id == client_id).all()
    buf = io.BytesIO()
    p = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, h-50, "VyapaarBandhu — Filing Summary")
    p.setFont("Helvetica", 11)
    p.drawString(50, h-80, f"Client: {user.business_name or user.phone or 'Unknown'}")
    p.drawString(50, h-100, f"GSTIN: {user.gstin or 'Not set'}")
    p.drawString(50, h-120, f"Period: {datetime.now().strftime('%B %Y')}")
    p.setFont("Helvetica-Bold", 11)
    p.drawString(50, h-160, "Invoice No")
    p.drawString(200, h-160, "Date")
    p.drawString(320, h-160, "Total")
    p.drawString(420, h-160, "ITC")
    p.drawString(490, h-160, "Status")
    y = h - 180
    total_itc = 0
    p.setFont("Helvetica", 10)
    for inv in invoices:
        itc = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
        total = float((inv.taxable_amt or 0) + itc)
        total_itc += itc
        p.drawString(50, y, inv.invoice_no or "—")
        p.drawString(200, y, str(inv.date or "")[:10])
        p.drawString(320, y, f"Rs {total:.2f}")
        p.drawString(420, y, f"Rs {itc:.2f}")
        p.drawString(490, y, inv.status or "confirmed")
        y -= 20
        if y < 100:
            p.showPage()
            y = h - 50
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y - 20, f"Total ITC Eligible: Rs {total_itc:.2f}")
    p.save()
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=filing_{client_id}_{datetime.now().strftime('%Y%m')}.pdf"})

@router.get("/clients/{client_id}")
def get_client_detail(client_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == client_id).first()
        if not user:
            return {"error": "Client not found"}
        invoices = db.query(Invoice).filter(Invoice.user_id == client_id).all()
        period = datetime.now().strftime("%Y-%m")
        ledger = db.query(GSTLedger).filter(GSTLedger.user_id == client_id, GSTLedger.period == period).first()
        invoice_list = []
        for inv in invoices:
            itc = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            invoice_list.append({
                "id": str(inv.id),
                "invoiceNo": inv.invoice_no or "",
                "date": str(inv.date or ""),
                "supplierGstin": inv.seller_gstin or "",
                "taxableAmt": float(inv.taxable_amt or 0),
                "total": total,
                "cgst": float(inv.cgst or 0),
                "sgst": float(inv.sgst or 0),
                "igst": float(inv.igst or 0),
                "itc": itc,
                "status": inv.status or "confirmed",
                "aiCategory": "General"
            })
        return {
            "id": str(user.id),
            "name": user.business_name or user.phone or "Unknown",
            "gstin": user.gstin or "",
            "state": user.state_code or "",
            "whatsapp": user.phone or "",
            "itcThisMonth": float(ledger.itc_available) if ledger else 0,
            "invoiceCount": len(invoice_list),
            "invoices": invoice_list
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/invoices")
def get_invoices(
    current_user: CAPartner = Depends(get_current_ca),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    try:
        total = db.query(func.count(Invoice.id)).scalar() or 0
        invoices = db.query(Invoice).order_by(Invoice.id.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()

        # Batch: one query for all users
        user_ids = list({inv.user_id for inv in invoices})
        users = db.query(User).filter(User.id.in_(user_ids)).all() if user_ids else []
        user_map = {u.id: u for u in users}

        result = []
        for inv in invoices:
            user = user_map.get(inv.user_id)
            itc = float((inv.cgst or 0) + (inv.sgst or 0) + (inv.igst or 0))
            total = float((inv.taxable_amt or 0) + itc)
            result.append({
                "id": str(inv.id),
                "clientId": str(inv.user_id),
                "clientName": (user.business_name or user.phone or "Unknown") if user else "Unknown",
                "invoiceNo": inv.invoice_no or "",
                "date": str(inv.date or ""),
                "supplierGstin": inv.seller_gstin or "",
                "taxableAmt": float(inv.taxable_amt or 0),
                "total": total,
                "cgst": float(inv.cgst or 0),
                "sgst": float(inv.sgst or 0),
                "igst": float(inv.igst or 0),
                "itc": itc,
                "status": inv.status or "confirmed",
                "aiCategory": "General"
            })
        return {"data": result, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        return {"error": str(e)}

@router.post("/invoices/{invoice_id}/approve")
def approve_invoice(invoice_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not inv:
            return {"error": "Invoice not found"}
        inv.status = "confirmed"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "confirmed"}
    except Exception as e:
        return {"error": str(e)}

@router.post("/invoices/{invoice_id}/reject")
def reject_invoice(invoice_id: int, current_user: CAPartner = Depends(get_current_ca), db: Session = Depends(get_db)):
    try:
        inv = db.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not inv:
            return {"error": "Invoice not found"}
        inv.status = "rejected"
        db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": "rejected"}
    except Exception as e:
        return {"error": str(e)}

@router.get("/alerts")
def get_alerts(
    current_user: CAPartner = Depends(get_current_ca),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    try:
        total = db.query(func.count(User.id)).scalar() or 0
        users = db.query(User).offset((page - 1) * per_page).limit(per_page).all()
        user_ids = [u.id for u in users]

        # Batch: one query for all invoice counts
        invoice_counts = db.query(
            Invoice.user_id, func.count(Invoice.id)
        ).filter(Invoice.user_id.in_(user_ids)).group_by(Invoice.user_id).all()
        count_map = {row[0]: row[1] for row in invoice_counts}

        period = datetime.now().strftime("%Y-%m")
        alerts = []
        for user in users:
            invoice_count = count_map.get(user.id, 0)
            if invoice_count == 0:
                alerts.append({
                    "id": f"alert-{user.id}",
                    "clientName": user.business_name or user.phone or "Unknown",
                    "type": "No Invoices",
                    "message": "No invoices uploaded this month. ITC at risk.",
                    "priority": "high",
                    "dueDate": f"{period}-20",
                    "daysRemaining": 11,
                    "resolved": False
                })
            elif invoice_count < 3:
                alerts.append({
                    "id": f"alert-low-{user.id}",
                    "clientName": user.business_name or user.phone or "Unknown",
                    "type": "Low Invoice Count",
                    "message": f"Only {invoice_count} invoice(s) uploaded. More expected.",
                    "priority": "medium",
                    "dueDate": f"{period}-25",
                    "daysRemaining": 16,
                    "resolved": False
                })
        return {"data": alerts, "total": total, "page": page, "per_page": per_page}
    except Exception as e:
        return {"error": str(e)}

@router.get("/admin/stats")
def get_admin_stats(
    current_user: CAPartner = Depends(get_current_ca),
    db: Session = Depends(get_db),
    page: int = 1,
    per_page: int = 50,
):
    try:
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_invoices = db.query(func.count(Invoice.id)).scalar() or 0
        total_itc = db.query(func.sum(GSTLedger.itc_available)).scalar() or 0
        confirmed = db.query(func.count(Invoice.id)).filter(Invoice.status == "confirmed").scalar() or 0
        pending = db.query(func.count(Invoice.id)).filter(Invoice.status == "pending").scalar() or 0
        users = db.query(User).order_by(User.id.desc()).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        user_ids = [u.id for u in users]

        # Batch: one query for invoice counts
        invoice_counts = db.query(
            Invoice.user_id, func.count(Invoice.id)
        ).filter(Invoice.user_id.in_(user_ids)).group_by(Invoice.user_id).all()
        count_map = {row[0]: row[1] for row in invoice_counts}

        user_list = []
        for u in users:
            inv_count = count_map.get(u.id, 0)
            user_list.append({
                "id": str(u.id),
                "name": u.business_name or "Unknown",
                "phone": u.phone or "",
                "gstin": u.gstin or "",
                "state": u.state_code or "",
                "invoiceCount": inv_count,
                "joinedAt": str(u.created_at or "")[:10]
            })
        return {
            "total_users": total_users,
            "total_invoices": total_invoices,
            "total_itc": round(float(total_itc), 2),
            "confirmed_invoices": confirmed,
            "pending_invoices": pending,
            "mrr": total_users * 299,
            "users": user_list
        }
    except Exception as e:
        return {"error": str(e)}