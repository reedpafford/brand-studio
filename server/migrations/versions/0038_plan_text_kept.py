"""script_drafts: the words a version's plan was made from (to say it's out of date) and its
advice kept anyway

Revision ID: 0038
Revises: 0037
"""

import sqlalchemy as sa
from alembic import op

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("breakdown_text", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("breakdown_kept", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("breakdown_kept")
        batch_op.drop_column("breakdown_text")
