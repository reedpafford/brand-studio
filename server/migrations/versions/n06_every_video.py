"""Every video (docs/next/data.md 1b, n06): the scene plan on a video and on a version, the
one automatic retry of a take and the wording fixed for you on a clip prompt (P3), and the
advisory check on stills and takes (P4). A video made before this has no plan stored: it's
read from its breakdown when asked (app code), so nothing is blocked.

Revision ID: n06
Revises: n01
"""

import sqlalchemy as sa
from alembic import op

revision = "n06"
down_revision = "n01"  # the head on `next` when the PR opens (data.md's merge order)
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("plan", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("plan_history", sa.JSON(), nullable=False, server_default="[]")
        )
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("plan", sa.JSON(), nullable=True))
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retry_of_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("auto", sa.Boolean(), nullable=False, server_default="0"))
        batch_op.create_foreign_key("fk_jobs_retry_of_id", "jobs", ["retry_of_id"], ["id"])
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("auto_fix", sa.JSON(), nullable=True))
    op.create_table(
        "item_checks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("target", sa.String(10), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="checking"),
        sa.Column("findings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("dismissed", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_index("ix_item_checks_project_id", "item_checks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_item_checks_project_id", table_name="item_checks")
    op.drop_table("item_checks")
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("auto_fix")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint("fk_jobs_retry_of_id", type_="foreignkey")
        batch_op.drop_column("auto")
        batch_op.drop_column("retry_of_id")
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("plan")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("plan_history")
        batch_op.drop_column("plan")
