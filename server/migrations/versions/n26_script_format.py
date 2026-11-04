"""A script's own format: the guides format id (app/guides/formats), null for its kind's default.

Revision ID: n26
Revises: n25
"""

import sqlalchemy as sa
from alembic import op

revision = "n26"
down_revision = "n25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("format", sa.String(40), nullable=True))
    with op.batch_alter_table("freestyles", schema=None) as batch_op:
        batch_op.alter_column("type", existing_type=sa.String(20), type_=sa.String(40))


def downgrade() -> None:
    with op.batch_alter_table("freestyles", schema=None) as batch_op:
        batch_op.alter_column("type", existing_type=sa.String(40), type_=sa.String(20))
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("format")
