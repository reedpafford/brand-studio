"""scripts.deleted_at: when a script was removed (it's purged for good 30 days on, later)

Revision ID: 0035
Revises: 0034
"""

import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
