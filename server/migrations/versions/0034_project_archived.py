"""projects.archived_at: a video put away (or its version released), undoable

Revision ID: 0034
Revises: 0033
"""

import sqlalchemy as sa
from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("released_draft_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_projects_released_draft_id_script_drafts"),
            "script_drafts",
            ["released_draft_id"],
            ["id"],
            use_alter=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_projects_released_draft_id_script_drafts"), type_="foreignkey"
        )
        batch_op.drop_column("released_draft_id")
        batch_op.drop_column("archived_at")
