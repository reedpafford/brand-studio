"""character_sheets

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_photo_file_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("sheet_file_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("sheet_approved", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_library_items_source_photo_file_id_files"),
            "files",
            ["source_photo_file_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_library_items_sheet_file_id_files"), "files", ["sheet_file_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_library_items_sheet_file_id_files"), type_="foreignkey"
        )
        batch_op.drop_constraint(
            batch_op.f("fk_library_items_source_photo_file_id_files"), type_="foreignkey"
        )
        batch_op.drop_column("sheet_approved")
        batch_op.drop_column("sheet_file_id")
        batch_op.drop_column("source_photo_file_id")
