"""Hooks follow the script (Reed, 13 Nov: "If i have 3 hooks, i want 3 hooks. If its one, its
one"): every opening a script has is a version, so the video keeps no choice (`projects.hooks`).

Revision ID: n54
Revises: n53
"""

import sqlalchemy as sa
from alembic import op

revision = "n54"
down_revision = "n53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("hooks")


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("hooks", sa.String(length=10), nullable=True))
