"""Freestyle (n20, Reed's v4): one row per freestyle, its settings and its thread.

Revision ID: n20
Revises: n18
"""

import sqlalchemy as sa
from alembic import op

revision = "n20"
down_revision = "n18"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "freestyles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(120), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("look", sa.String(40), nullable=False),
        sa.Column("shape", sa.String(10), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("chat", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("stopped_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_freestyles_workspace_id", "freestyles", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_freestyles_workspace_id", table_name="freestyles")
    op.drop_table("freestyles")
