"""A final cut taken off Media (n23, v5 G boards): the owner's Delete on a Media item leaves
the video's own copy, so the cut is only marked off Media.

Revision ID: n23
Revises: n22
"""

import sqlalchemy as sa
from alembic import op

revision = "n23"
down_revision = "n22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("off_media_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.drop_column("off_media_at")
