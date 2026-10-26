"""jobs.removed_at: a Quick clip taken off the history, kept so Undo can bring it back (its
credits still count)

Revision ID: 0040
Revises: 0039
"""

import sqlalchemy as sa
from alembic import op

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("removed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("removed_at")
