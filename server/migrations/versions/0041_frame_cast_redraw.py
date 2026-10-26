"""Stills after a cast change: frames keep earlier stills and say when a still shows the old
cast or was redrawn for the new one; a video keeps its last redraw result

Revision ID: 0041
Revises: 0040
"""

import sqlalchemy as sa
from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("still_stale", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(
            sa.Column("redrawn", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("earlier", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cast_redraw", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("cast_redraw")
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.drop_column("earlier")
        batch_op.drop_column("redrawn")
        batch_op.drop_column("still_stale")
