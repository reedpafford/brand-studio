"""product_variants

Revision ID: 0017
Revises: 0016
"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.add_column(sa.Column("end_line", sa.Text(), nullable=False, server_default=""))
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("product", sa.String(length=60), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("variant", sa.String(length=60), nullable=False, server_default="")
        )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("product_variants", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("product_variants")
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_column("variant")
        batch_op.drop_column("product")
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.drop_column("end_line")
