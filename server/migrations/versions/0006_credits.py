"""credits

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_limits",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("max_planned_seconds", sa.Integer(), nullable=False),
        sa.Column("weekly_quick_clip_credits", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_credit_limits_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_limits")),
        sa.UniqueConstraint("workspace_id", name=op.f("uq_credit_limits_workspace_id")),
    )
    op.create_table(
        "credit_rates",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("credits_per_unit", sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_credit_rates_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_credit_rates")),
    )
    with op.batch_alter_table("credit_rates", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_credit_rates_workspace_id"), ["workspace_id"], unique=False
        )

    op.create_table(
        "projects",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("planned_seconds", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["approved_by_id"], ["users.id"], name=op.f("fk_projects_approved_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_projects_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], name=op.f("fk_projects_workspace_id_workspaces")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_projects_brand_id"), ["brand_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_projects_workspace_id"), ["workspace_id"], unique=False
        )

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "credits", sa.Numeric(precision=12, scale=3), nullable=False, server_default="0"
            )
        )
        batch_op.add_column(sa.Column("approved_by_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_jobs_project_id"), ["project_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_jobs_approved_by_id_users"), "users", ["approved_by_id"], ["id"]
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_jobs_project_id_projects"), "projects", ["project_id"], ["id"]
        )

    # Workspaces set up before this migration get the launch rates.
    for kind, unit, rate in [
        ("video-480p", "second", 1),
        ("video-720p", "second", 2.25),
        ("image-nano-banana-2.1", "image", 0.3333),
        ("image-nano-banana-pro", "image", 1.5),
        ("write-claude", "call", 0.5),
        ("watch-gemini", "call", 0.1),
    ]:
        op.execute(
            sa.text(
                "INSERT INTO credit_rates (workspace_id, kind, unit, credits_per_unit, created_at)"
                " SELECT id, :kind, :unit, :rate, CURRENT_TIMESTAMP FROM workspaces"
            ).bindparams(kind=kind, unit=unit, rate=rate)
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_jobs_project_id_projects"), type_="foreignkey")
        batch_op.drop_constraint(batch_op.f("fk_jobs_approved_by_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_jobs_project_id"))
        batch_op.drop_column("approved_by_id")
        batch_op.drop_column("credits")
        batch_op.drop_column("project_id")

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_projects_workspace_id"))
        batch_op.drop_index(batch_op.f("ix_projects_brand_id"))

    op.drop_table("projects")
    with op.batch_alter_table("credit_rates", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_credit_rates_workspace_id"))

    op.drop_table("credit_rates")
    op.drop_table("credit_limits")
