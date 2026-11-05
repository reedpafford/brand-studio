"""The cut editor (v6 S7-01 to S7-07): numbered cuts and the edits each was made with.

`final_videos` gains `number` (Cut 1, Cut 2, … within a video; existing cuts numbered in the
order they were made), `edit_ids` (JSON list, default []) and `timeline` (JSON, nullable).
New table `cut_edits`: one edit to a video's cut, replayed in order (app/cut.py).

Revision ID: n40
Revises: n37
"""

import sqlalchemy as sa
from alembic import op

revision = "n40"
down_revision = "n37"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("number", sa.Integer(), nullable=False,
                                      server_default="1"))  # fmt: skip
        batch_op.add_column(sa.Column("edit_ids", sa.JSON(), nullable=False,
                                      server_default="[]"))  # fmt: skip
        batch_op.add_column(sa.Column("timeline", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE final_videos SET number = (SELECT COUNT(*) FROM final_videos AS f "
        "WHERE f.project_id = final_videos.project_id AND f.id <= final_videos.id)"
    )
    op.create_table(
        "cut_edits",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("by_id", sa.Integer(), nullable=True),
        sa.Column("director", sa.Boolean(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("said", sa.Text(), nullable=False),
        sa.Column("at", sa.Double(), nullable=False),
        sa.Column("undone_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["by_id"], ["users.id"], name=op.f("fk_cut_edits_by_id_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"],
                                name=op.f("fk_cut_edits_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cut_edits")),
    )  # fmt: skip
    with op.batch_alter_table("cut_edits", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_cut_edits_project_id"), ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("cut_edits", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_cut_edits_project_id"))
    op.drop_table("cut_edits")
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.drop_column("timeline")
        batch_op.drop_column("edit_ids")
        batch_op.drop_column("number")
