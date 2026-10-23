"""clip_takes

Revision ID: 0015
Revises: 0014
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clip_takes",
        sa.Column("clip_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["clip_id"], ["project_clips.id"], name=op.f("fk_clip_takes_clip_id_project_clips")
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_clip_takes_file_id_files")
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_clip_takes_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clip_takes")),
    )
    with op.batch_alter_table("clip_takes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_clip_takes_clip_id"), ["clip_id"], unique=False)
    op.create_table(
        "final_videos",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("take_ids", sa.JSON(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_final_videos_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_final_videos_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_final_videos_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_final_videos")),
    )
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_final_videos_project_id"), ["project_id"], unique=False
        )
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("picked_take_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_project_clips_picked_take_id_clip_takes"),
            "clip_takes",
            ["picked_take_id"],
            ["id"],
            use_alter=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_project_clips_picked_take_id_clip_takes"), type_="foreignkey"
        )
        batch_op.drop_column("approved")
        batch_op.drop_column("picked_take_id")
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_final_videos_project_id"))
    op.drop_table("final_videos")
    with op.batch_alter_table("clip_takes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clip_takes_clip_id"))
    op.drop_table("clip_takes")
