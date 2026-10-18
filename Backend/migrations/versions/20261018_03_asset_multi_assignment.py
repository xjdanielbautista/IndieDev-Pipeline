"""Support open and multi-user asset assignments.

Revision ID: 20261018_03
Revises: 20261018_02
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision = "20261018_03"
down_revision = "20261018_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "assets" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "assignment_mode" not in columns:
        op.add_column(
            "assets",
            sa.Column("assignment_mode", sa.String(length=20), nullable=False, server_default="open"),
        )

    if "asset_assignments" not in tables:
        op.create_table(
            "asset_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("assigned_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("asset_id", "user_id"),
        )
        op.create_index("ix_asset_assignments_asset_id", "asset_assignments", ["asset_id"])
        op.create_index("ix_asset_assignments_user_id", "asset_assignments", ["user_id"])

    # Preserve the previous single assignee in the new relation table.
    if "assigned_to_user_id" in columns:
        op.execute(
            text(
                "INSERT INTO asset_assignments (asset_id, user_id) "
                "SELECT id, assigned_to_user_id FROM assets "
                "WHERE assigned_to_user_id IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM asset_assignments aa "
                "WHERE aa.asset_id = assets.id AND aa.user_id = assets.assigned_to_user_id)"
            )
        )

        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                batch_op.drop_column("assigned_to_user_id")
        else:
            foreign_keys = inspect(bind).get_foreign_keys("assets")
            for foreign_key in foreign_keys:
                if foreign_key.get("constrained_columns") == ["assigned_to_user_id"]:
                    if foreign_key.get("name"):
                        op.drop_constraint(foreign_key["name"], "assets", type_="foreignkey")
            op.drop_column("assets", "assigned_to_user_id")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "assets" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("assets")}
    if "assigned_to_user_id" not in columns:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("assets", recreate="always") as batch_op:
                batch_op.add_column(sa.Column("assigned_to_user_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_assets_assigned_to_user_id_users", "users", ["assigned_to_user_id"], ["id"]
                )
        else:
            op.add_column("assets", sa.Column("assigned_to_user_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_assets_assigned_to_user_id_users", "assets", "users", ["assigned_to_user_id"], ["id"]
            )

    if "asset_assignments" in tables:
        op.execute(
            text(
                "UPDATE assets SET assigned_to_user_id = ("
                "SELECT user_id FROM asset_assignments "
                "WHERE asset_assignments.asset_id = assets.id ORDER BY id LIMIT 1)"
            )
        )
        indexes = {index["name"] for index in inspect(bind).get_indexes("asset_assignments")}
        for name in ("ix_asset_assignments_user_id", "ix_asset_assignments_asset_id"):
            if name in indexes:
                op.drop_index(name, table_name="asset_assignments")
        op.drop_table("asset_assignments")

    columns = {column["name"] for column in inspect(bind).get_columns("assets")}
    if "assignment_mode" in columns:
        op.drop_column("assets", "assignment_mode")
