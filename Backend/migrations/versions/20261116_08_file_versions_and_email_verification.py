"""Versiones de archivos de los assets y confirmación de correo.

- asset_file_versions: una fila por cada archivo subido. Los assets que ya tenían
  archivo quedan con su versión 1 apuntando al archivo actual.
- users.email_verified_at: los usuarios que ya existían se marcan como confirmados
  para no pedirles nada nuevo.
- email_verification_tokens: enlaces de confirmación (solo el SHA-256).

Revision ID: 20261116_08
Revises: 20261112_07
Create Date: 2026-11-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261116_08"
down_revision = "20261112_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "email_verified_at" not in user_columns:
        with op.batch_alter_table("users") as batch_op:
            batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(), nullable=True))
        op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP")

    if "email_verification_tokens" not in tables:
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", name="fk_email_verification_tokens_user_id_users", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
        op.create_index(
            "ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"], unique=True
        )

    if "asset_file_versions" not in tables:
        op.create_table(
            "asset_file_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("storage_key", sa.String(length=500), nullable=False),
            sa.Column("storage_provider", sa.String(length=20), nullable=False),
            sa.Column("file_name", sa.String(length=255), nullable=False),
            sa.Column("file_size", sa.BigInteger(), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False),
            sa.Column(
                "uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("restored_from_version", sa.Integer(), nullable=True),
            sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("asset_id", "version"),
        )
        op.create_index("ix_asset_file_versions_tenant_id", "asset_file_versions", ["tenant_id"])
        op.create_index("ix_asset_file_versions_asset_id", "asset_file_versions", ["asset_id"])
        op.create_index("ix_asset_file_versions_uploaded_by_user_id", "asset_file_versions", ["uploaded_by_user_id"])
        # Los archivos que ya existían pasan a ser la versión 1. Se copia desde Python
        # porque assets.storage_provider es un Enum que cada base guarda distinto.
        assets = sa.Table("assets", sa.MetaData(), autoload_with=bind)
        versions = sa.Table("asset_file_versions", sa.MetaData(), autoload_with=bind)
        rows = bind.execute(
            sa.select(
                assets.c.id, assets.c.tenant_id, assets.c.storage_key, assets.c.storage_provider,
                assets.c.original_name, assets.c.file_size, assets.c.content_type, assets.c.file_uploaded_at,
            ).where(assets.c.file_uploaded_at.is_not(None), assets.c.file_size.is_not(None))
        ).all()
        if rows:
            op.bulk_insert(versions, [
                {
                    "tenant_id": row.tenant_id,
                    "asset_id": row.id,
                    "version": 1,
                    "storage_key": row.storage_key,
                    "storage_provider": str(getattr(row.storage_provider, "value", row.storage_provider)).lower(),
                    "file_name": row.original_name,
                    "file_size": row.file_size,
                    "content_type": row.content_type or "application/octet-stream",
                    "uploaded_by_user_id": None,
                    "restored_from_version": None,
                    "uploaded_at": row.file_uploaded_at,
                }
                for row in rows
            ])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "asset_file_versions" in tables:
        op.drop_table("asset_file_versions")
    if "email_verification_tokens" in tables:
        op.drop_table("email_verification_tokens")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "email_verified_at" in user_columns:
        if op.get_bind().dialect.name == "sqlite":
            op.execute("ALTER TABLE users DROP COLUMN email_verified_at")
        else:
            op.drop_column("users", "email_verified_at")
