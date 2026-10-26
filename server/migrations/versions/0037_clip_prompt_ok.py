"""project_clips.prompt_ok: the editor read the clip's prompt and marked it Looks good

Revision ID: 0037
Revises: 0036
"""

import sqlalchemy as sa
from alembic import op

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("prompt_ok", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("prompt_ok")
