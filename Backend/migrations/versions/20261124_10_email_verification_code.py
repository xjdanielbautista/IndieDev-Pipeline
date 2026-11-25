"""Código de 6 dígitos para confirmar el correo.

Agrega a email_verification_tokens el SHA-256 del código, su vencimiento y el
contador de intentos fallidos. Los enlaces que ya existían siguen funcionando.

Revision ID: 20261124_10
Revises: 20261121_09
Create Date: 2026-11-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261124_10"
down_revision = "20261121_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    if "email_verification_tokens" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("email_verification_tokens")}
    if "code_hash" not in columns:
        op.add_column("email_verification_tokens", sa.Column("code_hash", sa.String(length=64), nullable=True))
    if "code_expires_at" not in columns:
        op.add_column("email_verification_tokens", sa.Column("code_expires_at", sa.DateTime(), nullable=True))
    if "failed_attempts" not in columns:
        op.add_column(
            "email_verification_tokens",
            sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "email_verification_tokens" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("email_verification_tokens")}
    with op.batch_alter_table("email_verification_tokens") as batch_op:
        for name in ("failed_attempts", "code_expires_at", "code_hash"):
            if name in columns:
                batch_op.drop_column(name)
