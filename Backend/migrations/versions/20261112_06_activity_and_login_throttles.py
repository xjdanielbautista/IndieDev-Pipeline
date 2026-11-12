"""Add tenant activity log and login throttling tables.

Revision ID: 20261112_06
Revises: 20261024_05
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261112_06"
down_revision = "20261024_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())

    if "tenant_activity" not in tables:
        op.create_table(
            "tenant_activity",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "tenant_id",
                sa.Integer(),
                sa.ForeignKey("tenants.id", name="fk_tenant_activity_tenant_id_tenants", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", name="fk_tenant_activity_user_id_users", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("actor_username", sa.String(length=50), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("summary", sa.String(length=300), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_tenant_activity_tenant_id", "tenant_activity", ["tenant_id"])
        op.create_index("ix_tenant_activity_user_id", "tenant_activity", ["user_id"])
        op.create_index("ix_tenant_activity_created_at", "tenant_activity", ["created_at"])

    if "login_throttles" not in tables:
        op.create_table(
            "login_throttles",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("identifier", sa.String(length=255), nullable=False),
            sa.Column("failed_count", sa.Integer(), nullable=False),
            sa.Column("first_failed_at", sa.DateTime(), nullable=False),
            sa.Column("locked_until", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_login_throttles_identifier", "login_throttles", ["identifier"], unique=True)


def downgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "login_throttles" in tables:
        op.drop_table("login_throttles")
    if "tenant_activity" in tables:
        op.drop_table("tenant_activity")
