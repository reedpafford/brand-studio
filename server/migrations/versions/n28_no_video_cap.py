"""No per-video cap (Reed, 2026-11-03: "Just remove the cap entirely").

Drops `credit_limits.per_video_max_credits` and `song_takes.trim_to` ("Use the first 0:55",
which only existed to fit a song video under the cap).

Revision ID: n28
Revises: n27
"""

import sqlalchemy as sa
from alembic import op

revision = "n28"
down_revision = "n27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.drop_column("per_video_max_credits")
    with op.batch_alter_table("song_takes", schema=None) as batch_op:
        batch_op.drop_column("trim_to")


def downgrade() -> None:
    with op.batch_alter_table("song_takes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("trim_to", sa.Double(), nullable=True))
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("per_video_max_credits", sa.Integer(), nullable=False, server_default="729")
        )
