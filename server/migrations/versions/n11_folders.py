"""Projects (docs/next/data.md, n11; flows OR1): a brand's folders of scripts, videos and
quick clips ("Project" on screen; "folders" here, as a video is already a project), and the
folder_id link on each (null: No project). A deleted folder is kept for Undo.

Revision ID: n11
Revises: n10
"""

import sqlalchemy as sa
from alembic import op

revision = "n11"
down_revision = "n10"
branch_labels = None
depends_on = None

FILED = ("scripts", "projects", "jobs")


def upgrade() -> None:
    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("deleted_at", sa.DateTime()),
    )
    op.create_index("ix_folders_workspace_id", "folders", ["workspace_id"])
    op.create_index("ix_folders_brand_id", "folders", ["brand_id"])
    for table in FILED:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("folder_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(f"fk_{table}_folder_id", "folders", ["folder_id"], ["id"])
            batch_op.create_index(f"ix_{table}_folder_id", ["folder_id"])


def downgrade() -> None:
    for table in FILED:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f"ix_{table}_folder_id")
            batch_op.drop_constraint(f"fk_{table}_folder_id", type_="foreignkey")
            batch_op.drop_column("folder_id")
    op.drop_index("ix_folders_brand_id", "folders")
    op.drop_index("ix_folders_workspace_id", "folders")
    op.drop_table("folders")
