"""usage_estimated

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usage", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("estimated", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("usage", schema=None) as batch_op:
        batch_op.drop_column("estimated")
