"""A brand screen's printed balance ("$348,920.15"), so the payoff uses the number the picture
shows (Reed, decision C); seeded from screens.json

Revision ID: 0044
Revises: 0043
"""

import sqlalchemy as sa
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("balance", sa.String(40), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_column("balance")
