"""storyboard_frames

Revision ID: 0013
Revises: 0012
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storyboard_frames",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("breakdown_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("clip_id", sa.String(length=20), nullable=False),
        sa.Column("shot_id", sa.String(length=20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("reference_ids", sa.JSON(), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["breakdown_id"],
            ["breakdowns.id"],
            name=op.f("fk_storyboard_frames_breakdown_id_breakdowns"),
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_storyboard_frames_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_storyboard_frames_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_storyboard_frames_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storyboard_frames")),
    )
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_storyboard_frames_project_id"), ["project_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_storyboard_frames_project_id"))
    op.drop_table("storyboard_frames")
