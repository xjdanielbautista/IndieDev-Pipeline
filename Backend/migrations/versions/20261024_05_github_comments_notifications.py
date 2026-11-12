"""Add GitHub commits, asset comments, and notifications.

Revision ID: 20261024_05
Revises: 20261024_04
Create Date: 2026-10-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261024_05"
down_down_revision = None
down_revision = "20261024_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    if "projects" in inspector.get_table_names():
        project_columns = {column["name"] for column in inspector.get_columns("projects")}
        if "github_repo" not in project_columns:
            op.add_column("projects", sa.Column("github_repo", sa.String(length=200), nullable=True))
        if "github_webhook_secret" not in project_columns:
            op.add_column("projects", sa.Column("github_webhook_secret", sa.String(length=64), nullable=True))

    if "asset_commits" not in inspector.get_table_names():
        op.create_table(
            "asset_commits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("sha", sa.String(length=40), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("author_name", sa.String(length=120), nullable=False),
            sa.Column("url", sa.String(length=500), nullable=False),
            sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("asset_id", "sha", name="uq_asset_commits_asset_sha"),
        )
        op.create_index("ix_asset_commits_tenant_id", "asset_commits", ["tenant_id"])
        op.create_index("ix_asset_commits_asset_id", "asset_commits", ["asset_id"])

    if "asset_comments" not in inspector.get_table_names():
        op.create_table(
            "asset_comments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("asset_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_asset_comments_tenant_id", "asset_comments", ["tenant_id"])
        op.create_index("ix_asset_comments_asset_id", "asset_comments", ["asset_id"])
        op.create_index("ix_asset_comments_user_id", "asset_comments", ["user_id"])

    if "notifications" not in inspector.get_table_names():
        op.create_table(
            "notifications",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("asset_id", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("message", sa.String(length=300), nullable=False),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
        op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "notifications" in tables:
        op.drop_table("notifications")
    if "asset_comments" in tables:
        op.drop_table("asset_comments")
    if "asset_commits" in tables:
        op.drop_table("asset_commits")

    if "projects" in tables:
        columns = {column["name"] for column in inspector.get_columns("projects")}
        for name in ("github_webhook_secret", "github_repo"):
            if name in columns:
                if op.get_bind().dialect.name == "sqlite":
                    with op.batch_alter_table("projects", recreate="always") as batch_op:
                        batch_op.drop_column(name)
                else:
                    op.drop_column("projects", name)
