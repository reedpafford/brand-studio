"""Folders inside folders (v6 S0-01): `folders.parent_id`, null for a folder at the top.

Revision ID: n30
Revises: n29
"""

import sqlalchemy as sa
from alembic import op

revision = "n30"
down_revision = "n29"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_folders_parent_id", "folders", ["parent_id"], ["id"])
        batch_op.create_index("ix_folders_parent_id", ["parent_id"])


def downgrade() -> None:
    with op.batch_alter_table("folders", schema=None) as batch_op:
        batch_op.drop_index("ix_folders_parent_id")
        batch_op.drop_constraint("fk_folders_parent_id", type_="foreignkey")
        batch_op.drop_column("parent_id")
