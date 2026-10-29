"""Song ads: a version's study of a song ad (docs/next/data.md, n04; flows S3a)

Revision ID: n04
Revises: n02
"""

import sqlalchemy as sa
from alembic import op

revision = "n04"
down_revision = "n02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("song_study", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("song_study")
