"""library

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "library_items",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("image_file_ids", sa.JSON(), nullable=False),
        sa.Column("outfits", sa.JSON(), nullable=False),
        sa.Column("voice_file_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["voice_file_id"], ["files.id"], name=op.f("fk_library_items_voice_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_library_items_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_items")),
    )
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_library_items_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "library_item_brands",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"],
            ["brands.id"],
            name=op.f("fk_library_item_brands_brand_id_brands"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["library_items.id"],
            name=op.f("fk_library_item_brands_item_id_library_items"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("item_id", "brand_id", name=op.f("pk_library_item_brands")),
    )
    op.create_table(
        "library_item_versions",
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("saved_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["library_items.id"],
            name=op.f("fk_library_item_versions_item_id_library_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["saved_by_id"], ["users.id"], name=op.f("fk_library_item_versions_saved_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_library_item_versions")),
    )
    with op.batch_alter_table("library_item_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_library_item_versions_item_id"), ["item_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("library_item_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_library_item_versions_item_id"))

    op.drop_table("library_item_versions")
    op.drop_table("library_item_brands")
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_library_items_workspace_id"))

    op.drop_table("library_items")
