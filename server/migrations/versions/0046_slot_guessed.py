"""A cast slot's guessed facts (Reed, 2026-10-26: looks fit the role): which of its age,
gender and occupation the cast read inferred rather than read in the script

Revision ID: 0046
Revises: 0045
"""

import sqlalchemy as sa
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.add_column(sa.Column("guessed", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("script_cast_slots", schema=None) as batch_op:
        batch_op.drop_column("guessed")
