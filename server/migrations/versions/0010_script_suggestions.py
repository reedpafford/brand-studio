"""script_suggestions

Revision ID: 0010
Revises: 0009
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_suggestions",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("script_version", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("start", sa.Integer(), nullable=False),
        sa.Column("end", sa.Integer(), nullable=False),
        sa.Column("placement", sa.String(length=10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("screen_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_script_suggestions_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_script_suggestions_project_id_projects")
        ),
        sa.ForeignKeyConstraint(
            ["screen_id"],
            ["brand_screens.id"],
            name=op.f("fk_script_suggestions_screen_id_brand_screens"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_suggestions")),
    )
    with op.batch_alter_table("script_suggestions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_script_suggestions_project_id"), ["project_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("script_suggestions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_script_suggestions_project_id"))

    op.drop_table("script_suggestions")
