"""Add asset file upload metadata.

Revision ID: 20261024_04
Revises: 20261018_03
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261024_04"
down_revision = "20261018_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "assets" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "file_size" not in columns:
        op.add_column("assets", sa.Column("file_size", sa.BigInteger(), nullable=True))
    if "content_type" not in columns:
        op.add_column("assets", sa.Column("content_type", sa.String(length=120), nullable=True))
    if "file_uploaded_at" not in columns:
        op.add_column(
            "assets",
            sa.Column("file_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("assets")}
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("assets", recreate="always") as batch_op:
            if "file_uploaded_at" in columns:
                batch_op.drop_column("file_uploaded_at")
            if "content_type" in columns:
                batch_op.drop_column("content_type")
            if "file_size" in columns:
                batch_op.drop_column("file_size")
        return

    for column_name in ("file_uploaded_at", "content_type", "file_size"):
        if column_name in columns:
            op.drop_column("assets", column_name)
