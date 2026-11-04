"""Who has watched which take (v6 piece C, S3-09): new table `take_seen` (take_id, user_id,
created_at; one row a person a take). A clip the director changed stays outlined for a person
until they've watched its new take. Downgrade drops the table.

Revision ID: n33
Revises: n32
"""

import sqlalchemy as sa
from alembic import op

revision = "n33"
down_revision = "n32"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "take_seen",
        sa.Column("take_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["take_id"], ["clip_takes.id"],
                                name=op.f("fk_take_seen_take_id_clip_takes")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_take_seen_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_take_seen")),
        sa.UniqueConstraint("take_id", "user_id", name=op.f("uq_take_seen_take_id")),
    )  # fmt: skip
    with op.batch_alter_table("take_seen", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_take_seen_take_id"), ["take_id"])


def downgrade() -> None:
    with op.batch_alter_table("take_seen", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_take_seen_take_id"))
    op.drop_table("take_seen")
