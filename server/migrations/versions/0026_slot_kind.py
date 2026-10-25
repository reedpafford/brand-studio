"""slot kind and appears_in: a cast slot's kind (Main, Helper, Rival, Family) and the versions
it's in (Designer's Cast spec)

Revision ID: 0026
Revises: 0025
"""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="Main"))
        batch_op.add_column(sa.Column("appears_in", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.drop_column("appears_in")
        batch_op.drop_column("kind")
