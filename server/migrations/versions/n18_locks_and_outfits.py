"""Locks and the per-video outfit (n18; director-chat.md §1, §6 item 6): the choices fixed
for the director on a video (projects.locks) and its own outfit per character
(projects.outfits), which its stills and Keep lines use over the sheet's. Both start empty.

Revision ID: n18
Revises: n17
"""

import sqlalchemy as sa
from alembic import op

revision = "n18"
down_revision = "n17"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("locks", sa.JSON(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("outfits", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("outfits")
        batch_op.drop_column("locks")
