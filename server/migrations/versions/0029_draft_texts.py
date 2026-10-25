"""draft texts: a library version's earlier texts, kept when its words are replaced

Revision ID: 0029
Revises: 0028
"""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "script_draft_texts",
        sa.Column("draft_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_script_draft_texts_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["draft_id"],
            ["script_drafts.id"],
            name=op.f("fk_script_draft_texts_draft_id_script_drafts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_script_draft_texts")),
    )
    with op.batch_alter_table("script_draft_texts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_script_draft_texts_draft_id"), ["draft_id"])


def downgrade() -> None:
    with op.batch_alter_table("script_draft_texts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_script_draft_texts_draft_id"))
    op.drop_table("script_draft_texts")
