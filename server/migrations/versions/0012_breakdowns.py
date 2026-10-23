"""breakdowns

Revision ID: 0012
Revises: 0011
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "breakdowns",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("script_version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_breakdowns_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_breakdowns_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_breakdowns_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_breakdowns")),
    )
    with op.batch_alter_table("breakdowns", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_breakdowns_project_id"), ["project_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("breakdowns", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_breakdowns_project_id"))
    op.drop_table("breakdowns")
