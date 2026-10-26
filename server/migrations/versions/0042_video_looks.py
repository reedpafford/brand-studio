"""Looks for one video or one script (gaps #19): a look made on Assets or in a script's Cast
step belongs there, never in the brand's library; a saved copy remembers its look for Undo;
the owner can let editors save looks to Cast & places

Revision ID: 0042
Revises: 0041
"""

import sqlalchemy as sa
from alembic import op

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("owner_script_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("copied_from_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_library_items_owner_project", "projects", ["owner_project_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_library_items_owner_script", "scripts", ["owner_script_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_library_items_copied_from", "library_items", ["copied_from_id"], ["id"]
        )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("slot_looks", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "editors_can_save_looks", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("credit_limits", schema=None) as batch_op:
        batch_op.drop_column("editors_can_save_looks")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("slot_looks")
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_library_items_copied_from", type_="foreignkey")
        batch_op.drop_constraint("fk_library_items_owner_script", type_="foreignkey")
        batch_op.drop_constraint("fk_library_items_owner_project", type_="foreignkey")
        batch_op.drop_column("copied_from_id")
        batch_op.drop_column("owner_script_id")
        batch_op.drop_column("owner_project_id")
