"""Merge roles on a video's Assets only (merge-roles.md §1): the roles merged on the video,
and which video a merge's Undo record belongs to

Revision ID: 0051
Revises: 0050
"""

import sqlalchemy as sa
from alembic import op

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("slot_merged", sa.JSON(), nullable=False, server_default="{}")
        )
    with op.batch_alter_table("cast_merges", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_cast_merges_project_id", "projects", ["project_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("cast_merges", schema=None) as batch_op:
        batch_op.drop_constraint("fk_cast_merges_project_id", type_="foreignkey")
        batch_op.drop_column("project_id")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("slot_merged")
