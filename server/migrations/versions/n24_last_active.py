"""When each member was last active (n24, v5 audit: Team shows it).

Revision ID: n24
Revises: n23
"""

import sqlalchemy as sa
from alembic import op

revision = "n24"
down_revision = "n23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_active_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("last_active_at")
