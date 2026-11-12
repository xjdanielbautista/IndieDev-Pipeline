"""Add password reset tokens and users.password_changed_at.

Revision ID: 20261112_07
Revises: 20261112_06
Create Date: 2026-11-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261112_07"
down_revision = "20261112_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_changed_at" not in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(), nullable=True))

    if "password_reset_tokens" not in tables:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", name="fk_password_reset_tokens_user_id_users", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
        op.create_index(
            "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "password_reset_tokens" in set(inspector.get_table_names()):
        op.drop_table("password_reset_tokens")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_changed_at" in user_columns:
        if op.get_bind().dialect.name == "sqlite":
            # batch_alter_table recrearía "users", y las llaves foráneas que apuntan a ella
            # lo impiden. SQLite 3.35+ ya permite quitar la columna directamente.
            op.execute("ALTER TABLE users DROP COLUMN password_changed_at")
        else:
            op.drop_column("users", "password_changed_at")
