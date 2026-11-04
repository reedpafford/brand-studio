"""Pictures and clips added to a brand's Media, and each final cut's length (n29, v5 C_Media).

Revision ID: n29
Revises: n28
"""

import sqlalchemy as sa
from alembic import op

revision = "n29"
down_revision = "n28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("seconds", sa.Double(), nullable=True),
        sa.Column("removed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_uploads_workspace_id", "media_uploads", ["workspace_id"])
    op.create_index("ix_media_uploads_brand_id", "media_uploads", ["brand_id"])
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("seconds", sa.Double(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("final_videos", schema=None) as batch_op:
        batch_op.drop_column("seconds")
    op.drop_index("ix_media_uploads_brand_id", table_name="media_uploads")
    op.drop_index("ix_media_uploads_workspace_id", table_name="media_uploads")
    op.drop_table("media_uploads")
