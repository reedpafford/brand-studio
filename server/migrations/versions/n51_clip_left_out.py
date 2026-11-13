"""A clip the one-pass director couldn't make (Reed, 13 Nov: "MINIMAL dead ends"): why, kept
on the clip (`project_clips.left_out`). The cut is made without it and delivery lists it.

Revision ID: n51
Revises: n50
"""

import sqlalchemy as sa
from alembic import op

revision = "n51"
down_revision = "n50"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("left_out", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("left_out")
