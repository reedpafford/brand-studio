"""The one-pass director (Reed, 10 Nov): a video keeps how its director works
(`projects.engine`), stamped at its first run. Every existing video has none: it stays on the
step-by-step director it was started with.

Revision ID: n50
Revises: n49
"""

import sqlalchemy as sa
from alembic import op

revision = "n50"
down_revision = "n49"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("engine", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("engine")
