"""brands

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("logo_file_id", sa.Integer(), nullable=True),
        sa.Column("style_board_file_id", sa.Integer(), nullable=True),
        sa.Column("end_card_file_id", sa.Integer(), nullable=True),
        sa.Column("colours", sa.JSON(), nullable=False),
        sa.Column("fonts", sa.JSON(), nullable=False),
        sa.Column("tone_notes", sa.Text(), nullable=False),
        sa.Column("never_say", sa.JSON(), nullable=False),
        sa.Column("legal_line", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["end_card_file_id"], ["files.id"], name=op.f("fk_brands_end_card_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["logo_file_id"], ["files.id"], name=op.f("fk_brands_logo_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["style_board_file_id"], ["files.id"], name=op.f("fk_brands_style_board_file_id_files")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_brands_workspace_id_workspaces")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brands")),
        sa.UniqueConstraint("workspace_id", "slug", name=op.f("uq_brands_workspace_id")),
    )
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_brands_workspace_id"), ["workspace_id"], unique=False)

    op.create_table(
        "brand_screens",
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("default_for", sa.JSON(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_brand_screens_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["file_id"], ["files.id"], name=op.f("fk_brand_screens_file_id_files")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_brand_screens")),
        sa.UniqueConstraint("brand_id", "name", name=op.f("uq_brand_screens_brand_id")),
    )
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_brand_screens_brand_id"), ["brand_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_brand_screens_brand_id"))

    op.drop_table("brand_screens")
    with op.batch_alter_table("brands", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_brands_workspace_id"))

    op.drop_table("brands")
