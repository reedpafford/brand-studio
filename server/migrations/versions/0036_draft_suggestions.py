"""script_suggestions.script_draft_id: Enhance marks on a library script version

Revision ID: 0036
Revises: 0035
"""

import sqlalchemy as sa
from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_suggestions", schema=None) as batch_op:
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("script_draft_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_script_suggestions_script_draft_id"), ["script_draft_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_script_suggestions_script_draft_id_script_drafts"),
            "script_drafts",
            ["script_draft_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    op.execute("DELETE FROM script_suggestions WHERE project_id IS NULL")
    with op.batch_alter_table("script_suggestions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_script_suggestions_script_draft_id_script_drafts"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_script_suggestions_script_draft_id"))
        batch_op.drop_column("script_draft_id")
        batch_op.alter_column("project_id", existing_type=sa.Integer(), nullable=False)
