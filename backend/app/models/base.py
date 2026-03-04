from sqlalchemy import (
    Column, Integer, String, Float,
    Boolean, DateTime, ForeignKey, Text
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class CAPartner(Base):
    __tablename__ = "ca_partners"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    ca_number = Column(String(50))
    email = Column(String(200))
    plan = Column(String(20), default="starter")
    white_label_name = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    phone = Column(String(15), unique=True, nullable=False)
    gstin = Column(String(15))
    business_name = Column(String(200))
    state_code = Column(String(2))
    turnover_ytd = Column(Float, default=0)
    ca_id = Column(Integer, ForeignKey("ca_partners.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(10))
    gst_rate = Column(Float)
    itc_eligible = Column(Boolean, default=False)
    category = Column(String(100))
    source = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_gstin = Column(String(15))
    invoice_no = Column(String(100))
    date = Column(DateTime)
    taxable_amt = Column(Float)
    cgst = Column(Float, default=0)
    sgst = Column(Float, default=0)
    igst = Column(Float, default=0)
    s3_url = Column(String(500))
    status = Column(String(20), default="extracted")
    created_at = Column(DateTime, default=datetime.utcnow)


class GSTLedger(Base):
    __tablename__ = "gst_ledger"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(7))
    total_sales = Column(Float, default=0)
    total_purchases = Column(Float, default=0)
    itc_available = Column(Float, default=0)
    net_liability = Column(Float, default=0)
    status = Column(String(20), default="open")


class FilingHistory(Base):
    __tablename__ = "filing_history"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    return_type = Column(String(20))
    period = Column(String(7))
    filed_on = Column(DateTime)
    liability_paid = Column(Float)
    penalty = Column(Float, default=0)
    json_s3_url = Column(String(500))


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50))
    trigger_date = Column(DateTime)
    message_hi = Column(Text)
    message_en = Column(Text)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending")


class GSTR2BCache(Base):
    __tablename__ = "gstr2b_cache"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(7))
    supplier_gstin = Column(String(15))
    invoice_no = Column(String(100))
    itc_amount = Column(Float)
    filing_status = Column(String(20))