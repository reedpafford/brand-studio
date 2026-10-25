"""reel import: a script's own reel breakdown, the reel itself, its job, the new-lines switch

Revision ID: 0031
Revises: 0030
"""

import sqlalchemy as sa
from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reference_breakdown", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("reel", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("reel_job_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("new_lines", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_scripts_reel_job_id_jobs"), "jobs", ["reel_job_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_scripts_reel_job_id_jobs"), type_="foreignkey")
        batch_op.drop_column("new_lines")
        batch_op.drop_column("reel_job_id")
        batch_op.drop_column("reel")
        batch_op.drop_column("reference_breakdown")
