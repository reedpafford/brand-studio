"""Video settings (docs/next/data.md, n09; flows VS1): a video's video and picture models
(null: Auto), the Sung shots a no-lip-sync model turned to B-roll, what each still and take
was made with (so a switch outdates them and switching back makes them current), and a
script's language.

Revision ID: n09
Revises: n08
"""

import sqlalchemy as sa
from alembic import op

revision = "n09"
down_revision = "n08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("video_model", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("image_model", sa.String(40), nullable=True))
        batch_op.add_column(
            sa.Column("sung_flipped", sa.JSON(), nullable=False, server_default="[]")
        )
    for table in ("storyboard_frames", "clip_takes"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("made_with", sa.JSON(), nullable=False, server_default="{}")
            )
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("language", sa.String(10), nullable=False, server_default="en")
        )


def downgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("language")
    for table in ("clip_takes", "storyboard_frames"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("made_with")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        for name in ("sung_flipped", "image_model", "video_model"):
            batch_op.drop_column(name)
