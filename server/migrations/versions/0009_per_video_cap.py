"""per_video_cap

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("per_video_max_credits", sa.Integer(), nullable=False, server_default="340")
        )


def downgrade() -> None:
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.drop_column("per_video_max_credits")
