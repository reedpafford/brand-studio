"""More than one video from a version (n22, the Producer on P1): "Make another" makes a new
video from the same frozen version, so a version's link to its videos is no longer unique.

Revision ID: n22
Revises: n21
"""

from alembic import op

revision = "n22"
down_revision = "n21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint("uq_projects_script_draft_id", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_projects_script_draft_id", ["script_draft_id"])
