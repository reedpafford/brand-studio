"""seeded_scripts: script draft files from the repo already imported into a workspace

Revision ID: 0033
Revises: 0032
"""

import sqlalchemy as sa
from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seeded_scripts",
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=300), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["brands.id"], name=op.f("fk_seeded_scripts_brand_id_brands")
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name=op.f("fk_seeded_scripts_workspace_id_workspaces"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seeded_scripts")),
        sa.UniqueConstraint("workspace_id", "key", name=op.f("uq_seeded_scripts_workspace_id")),
    )
    with op.batch_alter_table("seeded_scripts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_seeded_scripts_workspace_id"), ["workspace_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("seeded_scripts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_seeded_scripts_workspace_id"))
    op.drop_table("seeded_scripts")
