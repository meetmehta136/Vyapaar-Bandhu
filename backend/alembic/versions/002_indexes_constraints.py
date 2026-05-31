"""add indexes and constraints for performance

Revision ID: 002
Revises: 001
Create Date: 2026-05-31
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Indexes on foreign key columns
    op.create_index("ix_users_ca_id", "users", ["ca_id"])
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_invoices_user_id", "invoices", ["user_id"])
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])
    op.create_index("ix_gst_ledger_user_id", "gst_ledger", ["user_id"])
    op.create_index("ix_filing_history_user_id", "filing_history", ["user_id"])
    op.create_index("ix_gstr2b_cache_user_id", "gstr2b_cache", ["user_id"])

    # Composite indexes for common query patterns
    op.create_index("ix_invoices_user_id_created_at", "invoices", ["user_id", "created_at"])
    op.create_index("ix_gst_ledger_user_id_period", "gst_ledger", ["user_id", "period"])

    # NOT NULL constraint on invoices.status with default
    op.alter_column("invoices", "status",
                     existing_type=sa.String(20),
                     nullable=False,
                     server_default="pending")


def downgrade() -> None:
    op.drop_index("ix_gst_ledger_user_id_period", table_name="gst_ledger")
    op.drop_index("ix_invoices_user_id_created_at", table_name="invoices")
    op.drop_index("ix_gstr2b_cache_user_id", table_name="gstr2b_cache")
    op.drop_index("ix_filing_history_user_id", table_name="filing_history")
    op.drop_index("ix_gst_ledger_user_id", table_name="gst_ledger")
    op.drop_index("ix_alerts_user_id", table_name="alerts")
    op.drop_index("ix_invoices_user_id", table_name="invoices")
    op.drop_index("ix_transactions_user_id", table_name="transactions")
    op.drop_index("ix_users_ca_id", table_name="users")
    op.alter_column("invoices", "status",
                     existing_type=sa.String(20),
                     nullable=True,
                     server_default="extracted")
