"""frame_approved

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.drop_column("approved")
