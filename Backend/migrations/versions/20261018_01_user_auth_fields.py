"""Add username and password hash fields to users.

Revision ID: 20261018_01
Revises:
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261018_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        # On a new local database, create_all() creates the complete current schema.
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "username" not in columns:
        op.add_column("users", sa.Column("username", sa.String(length=50), nullable=True))
    if "password_hash" not in columns:
        op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))

    indexes = {index["name"] for index in inspect(bind).get_indexes("users")}
    if "ix_users_username" not in indexes:
        op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if "users" not in inspect(bind).get_table_names():
        return
    indexes = {index["name"] for index in inspect(bind).get_indexes("users")}
    if "ix_users_username" in indexes:
        op.drop_index("ix_users_username", table_name="users")
    columns = {column["name"] for column in inspect(bind).get_columns("users")}
    if "password_hash" in columns:
        op.drop_column("users", "password_hash")
    if "username" in columns:
        op.drop_column("users", "username")
