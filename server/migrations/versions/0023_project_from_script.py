"""project_from_script: a project made from a library version; length set by the breakdown

Revision ID: 0023
Revises: 0022
"""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column("planned_seconds", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("breakdown_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("script_draft_id", sa.Integer(), nullable=True))
        batch_op.create_unique_constraint("uq_projects_script_draft_id", ["script_draft_id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_projects_script_draft_id_script_drafts"),
            "script_drafts",
            ["script_draft_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_projects_script_draft_id_script_drafts"), type_="foreignkey"
        )
        batch_op.drop_constraint("uq_projects_script_draft_id", type_="unique")
        batch_op.drop_column("script_draft_id")
        batch_op.drop_column("breakdown_seconds")
        batch_op.alter_column("planned_seconds", existing_type=sa.Integer(), nullable=False)
