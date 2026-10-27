"""Fix this clip's prompt: its free Claude rewrite was used for this prompt (Reed, 2026-10-27,
spec one-click-fixes.md §5: once per clip per prompt version)

Revision ID: 0048
Revises: 0047
"""

import sqlalchemy as sa
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("free_fix_used", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("free_fix_used")
