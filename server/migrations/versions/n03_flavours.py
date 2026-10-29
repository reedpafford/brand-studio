"""Flavour from the script (docs/next/data.md, n03; flows "Flavour from the script"): each
version's default flavour per product, {product: variant}, copied to a video at Make this
version (the video's own pick stays in projects.product_variants).

Revision ID: n03
Revises: n11
"""

import sqlalchemy as sa
from alembic import op

revision = "n03"
down_revision = "n11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("flavours", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("flavours")
