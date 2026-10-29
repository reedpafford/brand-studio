"""Song ads (docs/next/data.md, n01): a script's kind; a version's music style line, song
directions, singer and spoken end line; song takes; and each video's own song

Next's migrations are n01, n02, … so they never collide with main's numbers.

Revision ID: n01
Revises: 0053
"""

import sqlalchemy as sa
from alembic import op

revision = "n01"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("kind", sa.String(20), nullable=False, server_default="story")
        )
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("style_line", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("song_directions", sa.JSON(), nullable=False, server_default="[]")
        )
        batch_op.add_column(sa.Column("singer", sa.String(120), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("spoken_end_line", sa.Text(), nullable=False, server_default="")
        )
    op.create_table(
        "song_takes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column(
            "draft_id",
            sa.Integer(),
            sa.ForeignKey("script_drafts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("track", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("lyrics", sa.Text(), nullable=False),
        sa.Column("style_line", sa.Text(), nullable=False),
        sa.Column("timing_job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("timing", sa.JSON(), nullable=True),
        sa.Column("seconds", sa.Double(), nullable=True),
        sa.Column("trim_to", sa.Double(), nullable=True),
        sa.Column("timing_guessed", sa.Boolean(), nullable=False),
        sa.Column("advice", sa.JSON(), nullable=False),
        sa.Column("preferred", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_song_takes_draft_id", "song_takes", ["draft_id"])
    op.create_index("ix_song_takes_project_id", "song_takes", ["project_id"])
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("song_take_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("singer", sa.String(120), nullable=True))
        batch_op.create_foreign_key(
            "fk_projects_song_take_id", "song_takes", ["song_take_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("fk_projects_song_take_id", type_="foreignkey")
        batch_op.drop_column("singer")
        batch_op.drop_column("song_take_id")
    op.drop_table("song_takes")
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_column("spoken_end_line")
        batch_op.drop_column("singer")
        batch_op.drop_column("song_directions")
        batch_op.drop_column("style_line")
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("kind")
