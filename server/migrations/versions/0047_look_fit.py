"""A look's fit advice (Reed, 2026-10-26: looks must fit the role): who its sheet reads as and
what to change, when the check still finds it doesn't fit its description

Revision ID: 0047
Revises: 0046
"""

import sqlalchemy as sa
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("look_fit", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_column("look_fit")
