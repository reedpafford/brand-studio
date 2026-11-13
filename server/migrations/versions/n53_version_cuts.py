"""Hooks as versions (Reed, 13 Nov): the cut of each further version of a video (opening 2,
3, … over the same body). The first version's stays the video's own cut (final_videos).

Revision ID: n53
Revises: n52
"""

import sqlalchemy as sa
from alembic import op

revision = "n53"
down_revision = "n52"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "version_cuts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("opening", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("take_ids", sa.JSON(), nullable=False),
        sa.Column("edit_ids", sa.JSON(), nullable=False),
        sa.Column("seconds", sa.Double(), nullable=True),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_version_cuts_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_version_cuts_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_version_cuts")),
    )
    with op.batch_alter_table("version_cuts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_version_cuts_project_id"), ["project_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("version_cuts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_version_cuts_project_id"))
    op.drop_table("version_cuts")
