"""New video's front door (Reed, 10 Nov): a video may start from a story card
(`projects.card`, a guides/cards id) and name the brand's products it is about
(`projects.product_ids`). Every existing video has neither.

Revision ID: n49
Revises: n48
"""

import sqlalchemy as sa
from alembic import op

revision = "n49"
down_revision = "n48"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("card", sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column("product_ids", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("product_ids")
        batch_op.drop_column("card")
