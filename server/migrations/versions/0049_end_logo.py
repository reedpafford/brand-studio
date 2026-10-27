"""End on the logo (Reed, 2026-10-27): per brand off | overlay | end_card, on for fomo
(end card); each final video remembers how it ended, so a changed setting marks it out of date.

Revision ID: 0049
Revises: 0048
"""

import sqlalchemy as sa
from alembic import op

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("brands", "final_videos"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("end_logo", sa.String(20), nullable=False, server_default="off")
            )
    op.execute("UPDATE brands SET end_logo = 'end_card' WHERE slug = 'fomo'")


def downgrade() -> None:
    for table in ("final_videos", "brands"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("end_logo")
