"""Narrated ads (docs/next/data.md, n05): a song take can be a narration, read in a voice,
with a music bed under it, and whether its pauses were trimmed

Revision ID: n05
Revises: n01
"""

import sqlalchemy as sa
from alembic import op

revision = "n05"
down_revision = "n01"  # the newest Next migration on next when written; move up on merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("song_takes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("kind", sa.String(20), nullable=False, server_default="song"))
        batch_op.add_column(sa.Column("voice", sa.String(60), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("trimmed", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("music_file_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("music_job_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_song_takes_music_file_id", "files", ["music_file_id"], ["id"]
        )
        batch_op.create_foreign_key("fk_song_takes_music_job_id", "jobs", ["music_job_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("song_takes", schema=None) as batch_op:
        batch_op.drop_constraint("fk_song_takes_music_job_id", type_="foreignkey")
        batch_op.drop_constraint("fk_song_takes_music_file_id", type_="foreignkey")
        batch_op.drop_column("music_job_id")
        batch_op.drop_column("music_file_id")
        batch_op.drop_column("trimmed")
        batch_op.drop_column("voice")
        batch_op.drop_column("kind")
