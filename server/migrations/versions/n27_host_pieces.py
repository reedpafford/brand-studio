"""A presenter video's host: its still on green and the pieces that lip-sync its narration.

Revision ID: n27
Revises: n26
"""

import sqlalchemy as sa
from alembic import op

revision = "n27"
down_revision = "n26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host_pieces",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("take_id", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("start", sa.Double(), nullable=False),
        sa.Column("end", sa.Double(), nullable=False),
        sa.Column("audio_file_id", sa.Integer(), nullable=True),
        sa.Column("file_id", sa.Integer(), nullable=True),
        sa.Column("earlier", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["audio_file_id"], ["files.id"],
                                name=op.f("fk_host_pieces_audio_file_id_files")),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"],
                                name=op.f("fk_host_pieces_file_id_files")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name=op.f("fk_host_pieces_project_id_projects")),
        sa.ForeignKeyConstraint(["take_id"], ["song_takes.id"],
                                name=op.f("fk_host_pieces_take_id_song_takes")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_host_pieces")),
    )  # fmt: skip
    with op.batch_alter_table("host_pieces", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_host_pieces_project_id"), ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("host_pieces", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_host_pieces_project_id"))
    op.drop_table("host_pieces")
