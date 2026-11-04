"""A hosted video's B-roll look: its B-roll drawn in another style's look, the host, voice
and cast kept in the video's own (New video's "Change B-roll look…", v6 S-gaps-01). Null:
the style's own.

Revision ID: n31
Revises: n30
"""

import sqlalchemy as sa
from alembic import op

revision = "n31"
down_revision = "n30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("broll_look", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("broll_look")
