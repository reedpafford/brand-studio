"""project_clips

Revision ID: 0014
Revises: 0013
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_clips",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("breakdown_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("clip_id", sa.String(length=20), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["breakdown_id"],
            ["breakdowns.id"],
            name=op.f("fk_project_clips_breakdown_id_breakdowns"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_project_clips_file_id_files")
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_project_clips_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_project_clips_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_clips")),
    )
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_project_clips_project_id"), ["project_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_project_clips_project_id"))
    op.drop_table("project_clips")
