"""Every video (docs/next/data.md 1b, n05): the one automatic retry of a take (P3) and the
wording fixed for you on a clip prompt, with its Undo.

Revision ID: n05
Revises: n01
"""

import sqlalchemy as sa
from alembic import op

revision = "n05"
down_revision = "n01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retry_of_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("auto", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.create_foreign_key("fk_jobs_retry_of_id", "jobs", ["retry_of_id"], ["id"])
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("auto_fix", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("auto_fix")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jobs_retry_of_id", type_="foreignkey")
        batch_op.drop_column("auto")
        batch_op.drop_column("retry_of_id")
