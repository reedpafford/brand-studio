"""Hidden rows (n21, Freestyle 3a): a freestyle's own script, video and brand, left out of
every list (app/hidden.py); a freestyle's link to its video.

Revision ID: n21
Revises: n19
"""

import sqlalchemy as sa
from alembic import op

revision = "n21"
down_revision = "n19"  # next's head (n19 follows n20)
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("projects", "scripts", "brands"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false())
            )
    with op.batch_alter_table("freestyles", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("up_to", sa.Numeric(12, 3), nullable=True))
        batch_op.create_foreign_key("fk_freestyles_project_id", "projects", ["project_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("freestyles", schema=None) as batch_op:
        batch_op.drop_constraint("fk_freestyles_project_id", type_="foreignkey")
        batch_op.drop_column("up_to")
        batch_op.drop_column("project_id")
    for table in ("brands", "scripts", "projects"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("hidden")
