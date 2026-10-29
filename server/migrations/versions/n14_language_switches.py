"""Languages (flows VS1, n14): the owner's switch for each language and its newest sample
test, in place of the fixed on/off list

Revision ID: n14
Revises: n11
"""

import sqlalchemy as sa
from alembic import op

revision = "n14"
down_revision = "n11"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "language_switches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("language_id", sa.String(8), nullable=False),
        sa.Column("on", sa.Boolean(), nullable=False),
        sa.Column("sample_job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("rejected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("switched_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("switched_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("workspace_id", "language_id"),
    )
    op.create_index("ix_language_switches_workspace_id", "language_switches", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_language_switches_workspace_id", table_name="language_switches")
    op.drop_table("language_switches")
