"""A reel-made version's "Was:" marks (reel-import.md §6): each rewritten line's index and the
reel's original words, kept through edits until the version is approved

Revision ID: 0045
Revises: 0044
"""

import sqlalchemy as sa
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("rewritten", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("rewritten")
