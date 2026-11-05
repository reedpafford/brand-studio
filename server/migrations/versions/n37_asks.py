"""The director's questions and money OKs (v6 piece B): new `asks`, one row per card.

Revision ID: n37
Revises: n36
"""

import sqlalchemy as sa
from alembic import op

revision = "n37"
down_revision = "n36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "asks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run", sa.String(40), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("topic", sa.String(80), nullable=False, server_default=""),
        sa.Column("subject", sa.String(120), nullable=False, server_default=""),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("why", sa.Text(), nullable=False, server_default=""),
        sa.Column("describe", sa.Text(), nullable=False, server_default=""),
        sa.Column("choices", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("pick", sa.String(120), nullable=True),
        sa.Column("decide_at", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="open"),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("answered_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.Column("rounds", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("job_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("closed", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_asks_workspace_id", "asks", ["workspace_id"])
    op.create_index("ix_asks_project_id", "asks", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_asks_project_id", table_name="asks")
    op.drop_index("ix_asks_workspace_id", table_name="asks")
    op.drop_table("asks")
