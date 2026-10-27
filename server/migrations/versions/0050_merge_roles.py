"""Merge roles and "These may be the same person" (merge-roles.md): the cast read's flag on a
role, the pairs kept apart for good, and each merge's record for its Undo

Revision ID: 0050
Revises: 0049
"""

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("may_be_same_as", sa.String(120), nullable=False, server_default="")
        )
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cast_apart", sa.JSON(), nullable=False, server_default="[]"))
    op.create_table(
        "cast_merges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index("ix_cast_merges_workspace_id", "cast_merges", ["workspace_id"])
    op.create_index("ix_cast_merges_script_id", "cast_merges", ["script_id"])


def downgrade() -> None:
    op.drop_table("cast_merges")
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("cast_apart")
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.drop_column("may_be_same_as")
