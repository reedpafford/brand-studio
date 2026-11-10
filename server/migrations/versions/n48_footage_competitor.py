"""A competitor's clip (Reed, 10 Nov): footage of another company's product, uploaded "labelled
as competitor" (`media_uploads.competitor`), is never shown as the brand's own. Every existing
clip is the brand's.

Revision ID: n48
Revises: n47
"""

import sqlalchemy as sa
from alembic import op

revision = "n48"
down_revision = "n47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("competitor", sa.Boolean(), nullable=False,
                                      server_default=sa.false()))  # fmt: skip


def downgrade() -> None:
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.drop_column("competitor")
