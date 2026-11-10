"""Footage folders (Reed, 10 Nov): a brand's footage has folders of its own, nested as in his
Google Drive (`folders.footage`, kept apart from the video and script folders), and a clip sits
in at most one (`media_uploads.folder_id`, null: at the top). One live footage folder of a name
in its place, whatever the case (`uq_folders_footage_name`: two uploads at once make a folder
once). Every existing folder is a video and script folder; every existing clip is at the top.

Revision ID: n47
Revises: n46
"""

import sqlalchemy as sa
from alembic import op

revision = "n47"
down_revision = "n46"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("footage", sa.Boolean(), nullable=False,
                                      server_default=sa.false()))  # fmt: skip
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_media_uploads_folder_id", "folders", ["folder_id"], ["id"])
        batch_op.create_index("ix_media_uploads_folder_id", ["folder_id"])
    live = sa.text("footage AND deleted_at IS NULL")
    op.create_index("uq_folders_footage_name", "folders",
                    ["brand_id", sa.text("coalesce(parent_id, 0)"), sa.text("lower(name)")],
                    unique=True, sqlite_where=live, postgresql_where=live)  # fmt: skip


def downgrade() -> None:
    op.drop_index("uq_folders_footage_name", table_name="folders")
    with op.batch_alter_table("media_uploads", schema=None) as batch_op:
        batch_op.drop_index("ix_media_uploads_folder_id")
        batch_op.drop_constraint("fk_media_uploads_folder_id", type_="foreignkey")
        batch_op.drop_column("folder_id")
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.drop_column("footage")
