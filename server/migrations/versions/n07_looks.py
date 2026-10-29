"""Format and Look (docs/next/data.md, n07): a script's and a video's look, and the owner's
switch for each look

Revision ID: n07
Revises: n01
"""

import sqlalchemy as sa
from alembic import op

revision = "n07"
down_revision = "n01"  # a placeholder: moved to the head on next at its turn (n02…n06 first)
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("scripts", "projects"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("look", sa.String(40), nullable=False, server_default="house")
            )
    op.create_table(
        "look_switches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("look_id", sa.String(40), nullable=False),
        sa.Column("on", sa.Boolean(), nullable=False),
        sa.Column("sample_still_id", sa.Integer(), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("sample_clip_id", sa.Integer(), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("switched_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("switched_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("workspace_id", "look_id"),
    )
    op.create_index("ix_look_switches_workspace_id", "look_switches", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_look_switches_workspace_id", table_name="look_switches")
    op.drop_table("look_switches")
    for table in ("projects", "scripts"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("look")
