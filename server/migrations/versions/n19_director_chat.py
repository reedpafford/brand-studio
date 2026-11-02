"""The director's chat (n19; director-chat.md §1 item 4): what people asked of the director on
a video (projects.director_chat), each {by, text, at, run}. Starts empty.

Revision ID: n19
Revises: n18
"""

import sqlalchemy as sa
from alembic import op

revision = "n19"
down_revision = "n20"  # after Freestyle (n20), which landed first
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("director_chat", sa.JSON(), nullable=False, server_default="[]")
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("director_chat")
