"""Voices (v6 S8-04): a brand's saved, cloned and described voices, a style's own voice
(brand_id null, e.g. Dr. Pickle's clone, added to each workspace by app/voices.py the first
time it's read), and a character's voice (`library_items.voice_id`, S8-03).

Revision ID: n31
Revises: n30
"""

import sqlalchemy as sa
from alembic import op

revision = "n31"
down_revision = "n30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("look", sa.String(length=40), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_voice_id", sa.String(length=120), nullable=True),
        sa.Column("speech_model", sa.String(length=60), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sample_file_id", sa.Integer(), nullable=True),
        sa.Column("preview_file_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("cloned_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("lost_at", sa.DateTime(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["preview_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["sample_file_id"], ["files.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_voices_workspace_id", "voices", ["workspace_id"])
    op.create_index("ix_voices_brand_id", "voices", ["brand_id"])
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("voice_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_library_items_voice_id", "voices", ["voice_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_constraint("fk_library_items_voice_id", type_="foreignkey")
        batch_op.drop_column("voice_id")
    op.drop_index("ix_voices_brand_id", table_name="voices")
    op.drop_index("ix_voices_workspace_id", table_name="voices")
    op.drop_table("voices")
