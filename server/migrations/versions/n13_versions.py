"""Versions on storyboards and clip prompts (docs/next/flows.md OR3; n13): the storyboards and
clip prompts a video had before the one in hand, newest first, at most 10 each, so "Go back to
this" brings one back (free, with Undo). n12 is held for OR2: if it lands first, this points
at it before merging.

Revision ID: n13
Revises: n11
"""

import sqlalchemy as sa
from alembic import op

revision = "n13"
down_revision = "n11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("storyboard_history", sa.JSON(), nullable=False, server_default="[]")
        )
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("prompt_history", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("prompt_history")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("storyboard_history")
