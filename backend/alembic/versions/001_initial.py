"""initial schema — all tables

Revision ID: 001
Revises:
Create Date: 2026-05-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ca_partners",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("ca_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(15), nullable=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("plan", sa.String(20), server_default="starter"),
        sa.Column("white_label_name", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(15), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("business_name", sa.String(200), nullable=True),
        sa.Column("state_code", sa.String(2), nullable=True),
        sa.Column("turnover_ytd", sa.Float(), server_default="0"),
        sa.Column("ca_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone"),
        sa.ForeignKeyConstraint(["ca_id"], ["ca_partners.id"],),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("type", sa.String(10), nullable=True),
        sa.Column("gst_rate", sa.Float(), nullable=True),
        sa.Column("itc_eligible", sa.Boolean(), server_default="false"),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("seller_gstin", sa.String(15), nullable=True),
        sa.Column("invoice_no", sa.String(100), nullable=True),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("taxable_amt", sa.Float(), nullable=True),
        sa.Column("cgst", sa.Float(), server_default="0"),
        sa.Column("sgst", sa.Float(), server_default="0"),
        sa.Column("igst", sa.Float(), server_default="0"),
        sa.Column("s3_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="extracted"),
        sa.Column("ai_category", sa.String(100), server_default="General"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )
    op.create_table(
        "gst_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("total_sales", sa.Float(), server_default="0"),
        sa.Column("total_purchases", sa.Float(), server_default="0"),
        sa.Column("itc_available", sa.Float(), server_default="0"),
        sa.Column("net_liability", sa.Float(), server_default="0"),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )
    op.create_table(
        "filing_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("return_type", sa.String(20), nullable=True),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("filed_on", sa.DateTime(), nullable=True),
        sa.Column("liability_paid", sa.Float(), nullable=True),
        sa.Column("penalty", sa.Float(), server_default="0"),
        sa.Column("json_s3_url", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(50), nullable=True),
        sa.Column("trigger_date", sa.DateTime(), nullable=True),
        sa.Column("message_hi", sa.Text(), nullable=True),
        sa.Column("message_en", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )
    op.create_table(
        "gstr2b_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(7), nullable=True),
        sa.Column("supplier_gstin", sa.String(15), nullable=True),
        sa.Column("invoice_no", sa.String(100), nullable=True),
        sa.Column("itc_amount", sa.Float(), nullable=True),
        sa.Column("filing_status", sa.String(20), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],),
    )


def downgrade() -> None:
    op.drop_table("gstr2b_cache")
    op.drop_table("alerts")
    op.drop_table("filing_history")
    op.drop_table("gst_ledger")
    op.drop_table("invoices")
    op.drop_table("transactions")
    op.drop_table("users")
    op.drop_table("ca_partners")
