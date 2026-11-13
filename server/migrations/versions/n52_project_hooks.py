"""Hooks as versions (Reed, 13 Nov): a video keeps whether every opening of its script is made
as a version of its own (`projects.hooks` = "all") or only the first (null, "first").

Revision ID: n52
Revises: n51
"""

import sqlalchemy as sa
from alembic import op

revision = "n52"
down_revision = "n51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hooks", sa.String(length=10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("hooks")
