from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.base import Base
from app.core.database import engine
from app.routes.gstin import router as gstin_router
from app.routes.compliance import router as compliance_router
from app.routes.whatsapp import router as whatsapp_router
from app.routes.dashboard import router as dashboard_router
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os

app = FastAPI(
    title="VyapaarBandhu",
    description="AI GST Compliance Assistant for Indian Small Businesses",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gstin_router)
app.include_router(compliance_router)
app.include_router(whatsapp_router)
app.include_router(dashboard_router)


# ── APScheduler Deadline Alert Job ───────────────────────────────────────────

def send_deadline_alerts():
    """
    Runs daily at 9:00 AM IST.
    Checks GSTR-1 (11th) and GSTR-3B (20th) deadlines.
    Sends WhatsApp reminders at 7, 3, and 1 day before deadline.
    """
    from app.core.database import SessionLocal
    from app.models.base import User, GSTLedger
    from app.services.compliance_engine import get_filing_deadlines
    from twilio.rest import Client

    print(f"⏰ Running deadline alert job — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_FROM  = "whatsapp:+14155238886"

    if not TWILIO_SID or not TWILIO_TOKEN:
        print("❌ Twilio credentials not found — skipping alerts")
        return

    period    = datetime.utcnow().strftime("%Y-%m")
    deadlines = get_filing_deadlines(period)

    days_to_gstr1 = deadlines.get("days_to_gstr1", 999)
    days_to_gstr3b = deadlines.get("days_to_gstr3b", 999)
    gstr1_date  = deadlines.get("gstr1_deadline", "11th")
    gstr3b_date = deadlines.get("gstr3b_deadline", "20th")

    # Only send on 7, 3, 1 days before deadline
    alert_days = {7, 3, 1}
    should_alert_gstr1  = days_to_gstr1  in alert_days
    should_alert_gstr3b = days_to_gstr3b in alert_days

    if not should_alert_gstr1 and not should_alert_gstr3b:
        print(f"📅 No alerts today — GSTR-1: {days_to_gstr1}d, GSTR-3B: {days_to_gstr3b}d")
        return

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.phone.isnot(None)).all()
        print(f"📋 Sending alerts to {len(users)} users...")

        twilio_client = Client(TWILIO_SID, TWILIO_TOKEN)
        sent_count = 0

        for user in users:
            phone = user.phone
            if not phone:
                continue

            # Format phone for WhatsApp
            if not phone.startswith("+"):
                phone = f"+91{phone}"
            wa_to = f"whatsapp:{phone}"

            # Get their ITC balance for this month
            ledger = db.query(GSTLedger).filter(
                GSTLedger.user_id == user.id,
                GSTLedger.period  == period
            ).first()
            itc_balance = round(ledger.itc_available if ledger else 0, 2)

            # Build message
            messages = []

            if should_alert_gstr1:
                urgency = "🚨 URGENT!" if days_to_gstr1 == 1 else "⚠️" if days_to_gstr1 == 3 else "📅"
                messages.append(
                    f"{urgency} GSTR-1 Filing Reminder\n\n"
                    f"Deadline: {gstr1_date}\n"
                    f"Sirf {days_to_gstr1} din bacha hai!\n\n"
                    f"💰 Aapka ITC this month: Rs.{itc_balance:,.2f}\n\n"
                    f"Apne CA se abhi contact karein.\n"
                    f"VyapaarBandhu 🤝"
                )

            if should_alert_gstr3b:
                urgency = "🚨 URGENT!" if days_to_gstr3b == 1 else "⚠️" if days_to_gstr3b == 3 else "📅"
                messages.append(
                    f"{urgency} GSTR-3B Filing Reminder\n\n"
                    f"Deadline: {gstr3b_date}\n"
                    f"Sirf {days_to_gstr3b} din bacha hai!\n\n"
                    f"💰 ITC Available: Rs.{itc_balance:,.2f}\n\n"
                    f"{'Ab der mat karein! Penalty shuru hogi!' if days_to_gstr3b == 1 else 'Invoice upload karna baaki hai to abhi bhejiye!'}\n"
                    f"VyapaarBandhu 🤝"
                )

            for msg_body in messages:
                try:
                    twilio_client.messages.create(
                        from_=TWILIO_FROM,
                        to=wa_to,
                        body=msg_body
                    )
                    sent_count += 1
                    print(f"📤 Alert sent to {phone}")
                except Exception as e:
                    print(f"❌ Failed to send to {phone}: {e}")

        print(f"✅ Deadline alerts done — {sent_count} messages sent")

    except Exception as e:
        print(f"❌ Alert job error: {e}")
    finally:
        db.close()


# ── Scheduler setup ───────────────────────────────────────────────────────────

scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(
    send_deadline_alerts,
    trigger="cron",
    hour=9,
    minute=0,
    id="deadline_alerts",
    name="Daily GST Deadline Alerts",
    replace_existing=True,
)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    print("✅ All 8 tables created")
    scheduler.start()
    print("⏰ APScheduler started — deadline alerts at 9:00 AM IST daily")


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown()
    print("⏰ APScheduler stopped")


@app.get("/health")
def health_check():
    job = scheduler.get_job("deadline_alerts")
    next_run = str(job.next_run_time) if job else "unknown"
    return {
        "status":        "alive",
        "product":       "VyapaarBandhu",
        "version":       "0.1.0",
        "scheduler":     "running" if scheduler.running else "stopped",
        "next_alert_run": next_run,
    }


@app.get("/api/alerts/trigger-test")
def trigger_test_alerts():
    """
    Manual trigger for testing alerts — call this to test without waiting for 9 AM.
    GET https://vyapaar-bandhu.onrender.com/api/alerts/trigger-test
    """
    import threading
    threading.Thread(target=send_deadline_alerts, daemon=True).start()
    return {"status": "triggered", "message": "Alert job running in background — check Render logs"}