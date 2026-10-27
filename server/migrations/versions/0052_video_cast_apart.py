"""They're different on a video's Assets only (merge-roles.md §2): the role pairs kept apart
on the video, while the script's Cast stays as it is

Revision ID: 0052
Revises: 0051
"""

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cast_apart", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("cast_apart")
