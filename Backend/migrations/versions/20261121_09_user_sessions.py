"""Sesiones de usuario para poder cerrarlas una por una.

Revision ID: 20261121_09
Revises: 20261116_08
Create Date: 2026-11-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261121_09"
down_revision = "20261116_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "user_sessions" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", name="fk_user_sessions_user_id_users", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_session_key", "user_sessions", ["session_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_sessions_session_key", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
