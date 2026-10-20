"""Add asset categories, workflow status, assignment, and history.

Revision ID: 20261018_02
Revises: 20261018_01
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261018_02"
down_revision = "20261018_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    # A new database gets the complete schema from Base.metadata.create_all().
    if "assets" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "category" not in columns:
        op.add_column(
            "assets",
            sa.Column("category", sa.String(length=20), nullable=False, server_default="art"),
        )
    if "status" not in columns:
        op.add_column(
            "assets",
            sa.Column("status", sa.String(length=20), nullable=False, server_default="backlog"),
        )
    if "created_by_user_id" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "created_by_user_id",
                        sa.Integer(),
                        sa.ForeignKey("users.id", name="fk_assets_created_by_user_id_users"),
                        nullable=True,
                    )
                )
        else:
            op.add_column("assets", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_created_by_user_id_users", "assets", "users", ["created_by_user_id"], ["id"]
            )
    if "assigned_to_user_id" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "assigned_to_user_id",
                        sa.Integer(),
                        sa.ForeignKey("users.id", name="fk_assets_assigned_to_user_id_users"),
                        nullable=True,
                    )
                )
        else:
            op.add_column("assets", sa.Column("assigned_to_user_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_assigned_to_user_id_users", "assets", "users", ["assigned_to_user_id"], ["id"]
            )

    if "asset_history" not in tables:
        op.create_table(
            "asset_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("actor_username", sa.String(length=50), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("previous_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_asset_history_tenant_id", "asset_history", ["tenant_id"])
        op.create_index("ix_asset_history_asset_id", "asset_history", ["asset_id"])
        op.create_index("ix_asset_history_user_id", "asset_history", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "asset_history" in tables:
        indexes = {index["name"] for index in inspector.get_indexes("asset_history")}
        for name in ("ix_asset_history_user_id", "ix_asset_history_asset_id", "ix_asset_history_tenant_id"):
            if name in indexes:
                op.drop_index(name, table_name="asset_history")
        op.drop_table("asset_history")

    if "assets" not in tables:
        return
    columns = {column["name"] for column in inspect(bind).get_columns("assets")}
    foreign_keys = {fk.get("name") for fk in inspect(bind).get_foreign_keys("assets")}
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("assets", recreate="always") as batch_op:
            for column, constraint in (
                ("assigned_to_user_id", "fk_assets_assigned_to_user_id_users"),
                ("created_by_user_id", "fk_assets_created_by_user_id_users"),
            ):
                if column in columns:
                    batch_op.drop_column(column)
            for column in ("status", "category"):
                if column in columns:
                    batch_op.drop_column(column)
        return
    for column, constraint in (
        ("assigned_to_user_id", "fk_assets_assigned_to_user_id_users"),
        ("created_by_user_id", "fk_assets_created_by_user_id_users"),
    ):
        if column in columns:
            if constraint in foreign_keys:
                op.drop_constraint(constraint, "assets", type_="foreignkey")
            op.drop_column("assets", column)
    for column in ("status", "category"):
        if column in columns:
            op.drop_column("assets", column)
