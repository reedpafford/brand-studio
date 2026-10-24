"""project_created_by

Revision ID: 0021
Revises: 0020
"""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("created_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_projects_created_by_id_users"), "users", ["created_by_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_projects_created_by_id_users"), type_="foreignkey")
        batch_op.drop_column("created_by_id")
