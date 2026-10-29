"""Per-look sheets (docs/next/data.md, n10; flows ST2): the owner's sheets of a Cast & places
character or place in other looks (House stays in sheet_file_id), the look a video's own look
was drawn in, and a video's own copies of library characters drawn in its look.

Revision ID: n10
Revises: n08 (n09 once #925 is merged: re-pointed just before merge)
"""

import sqlalchemy as sa
from alembic import op

revision = "n10"
down_revision = "n08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("look_sheets", sa.JSON(), nullable=False, server_default="{}")
        )
        batch_op.add_column(
            sa.Column("sheet_look", sa.String(40), nullable=False, server_default="house")
        )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("look_copies", sa.JSON(), nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("look_copies")
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_column("sheet_look")
        batch_op.drop_column("look_sheets")
