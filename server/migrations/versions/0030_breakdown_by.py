"""breakdown_by: who planned a library version's saved breakdown (the version panel, #243)

Revision ID: 0030
Revises: 0029
"""

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("breakdown_by_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_script_drafts_breakdown_by_id_users"),
            "users",
            ["breakdown_by_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("script_drafts", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_script_drafts_breakdown_by_id_users"), type_="foreignkey"
        )
        batch_op.drop_column("breakdown_by_id")
