"""changed_lines: a library version's lines rewritten for the brand swap (reel import, #271)

Revision ID: 0032
Revises: 0031
"""

import sqlalchemy as sa
from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("changed_lines", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("changed_lines")
