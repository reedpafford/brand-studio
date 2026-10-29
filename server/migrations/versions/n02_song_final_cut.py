"""Song ads (docs/next/data.md, n02): the piece of the song each clip covers, and the song a
final video was laid over

Revision ID: n02
Revises: n01
"""

import sqlalchemy as sa
from alembic import op

revision = "n02"
down_revision = "n01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("song_slice", sa.JSON(), nullable=True))
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("song_take_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_final_videos_song_take_id", "song_takes", ["song_take_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.drop_constraint("fk_final_videos_song_take_id", type_="foreignkey")
        batch_op.drop_column("song_take_id")
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("song_slice")
