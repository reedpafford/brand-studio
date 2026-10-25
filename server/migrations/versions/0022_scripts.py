"""scripts: the Script Library (scripts, versions, cast slots) and kept advice

Revision ID: 0022
Revises: 0021
"""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

KEPT_TABLES = ("breakdowns", "storyboard_frames", "project_clips")


def _entity() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "scripts",
        *_entity(),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("reference_id", sa.String(80), nullable=True),
        sa.Column("reference_replace", sa.Text(), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_scripts_workspace_id", "scripts", ["workspace_id"])
    op.create_index("ix_scripts_brand_id", "scripts", ["brand_id"])
    op.create_table(
        "script_drafts",
        *_entity(),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_seconds", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("premise", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("problems", sa.JSON(), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("breakdown", sa.JSON(), nullable=True),
        sa.Column("breakdown_problems", sa.JSON(), nullable=False),
        sa.Column("reserved_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("script_id", "slot"),
    )
    op.create_index("ix_script_drafts_script_id", "script_drafts", ["script_id"])
    op.create_table(
        "script_cast_slots",
        *_entity(),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id"), nullable=False),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "library_item_id", sa.Integer(), sa.ForeignKey("library_items.id"), nullable=True
        ),
        sa.Column("sheet_file_id", sa.Integer(), sa.ForeignKey("files.id"), nullable=True),
        sa.Column("locked_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("script_id", "role"),
    )
    op.create_index("ix_script_cast_slots_script_id", "script_cast_slots", ["script_id"])
    for table in KEPT_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("kept", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    for table in KEPT_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("kept")
    op.drop_table("script_cast_slots")
    op.drop_table("script_drafts")
    op.drop_table("scripts")
