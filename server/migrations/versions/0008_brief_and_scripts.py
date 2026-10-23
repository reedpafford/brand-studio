"""brief_and_scripts

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_versions",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_script_versions_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_script_versions_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_versions")),
        sa.UniqueConstraint("project_id", "version", name=op.f("uq_script_versions_project_id")),
    )
    with op.batch_alter_table("script_versions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_script_versions_project_id"), ["project_id"], unique=False
        )

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("goal", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(
            sa.Column("platform", sa.String(length=40), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("aspect_ratio", sa.String(length=20), nullable=False, server_default="9:16")
        )
        batch_op.add_column(
            sa.Column("format", sa.String(length=120), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("cast_ids", sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("reference_file_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_projects_reference_file_id_files"),
            "files",
            ["reference_file_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_projects_reference_file_id_files"), type_="foreignkey"
        )
        batch_op.drop_column("reference_file_id")
        batch_op.drop_column("cast_ids")
        batch_op.drop_column("format")
        batch_op.drop_column("aspect_ratio")
        batch_op.drop_column("platform")
        batch_op.drop_column("goal")

    with op.batch_alter_table("script_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_script_versions_project_id"))

    op.drop_table("script_versions")
