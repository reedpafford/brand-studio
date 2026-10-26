"""Change it in plain English (change-notes.md): a still or clip remembers what its last note
changed; each take keeps the prompt it was made from, so picking it back restores it; the
owner can give one charge's credits back (who, why, how many), once per job

Revision ID: 0043
Revises: 0042
"""

import sqlalchemy as sa
from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.add_column(sa.Column("change", sa.JSON(), nullable=True))
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.add_column(sa.Column("change", sa.JSON(), nullable=True))
    with op.batch_alter_table("clip_takes", schema=None) as batch_op:
        batch_op.add_column(sa.Column("prompt", sa.Text(), nullable=True))
    op.create_table(
        "charge_refunds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("credits", sa.Numeric(12, 3), nullable=False),
        sa.Column("by_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_charge_refunds_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["by_id"], ["users.id"], name=op.f("fk_charge_refunds_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_charge_refunds")),
        sa.UniqueConstraint("job_id", name=op.f("uq_charge_refunds_job_id")),
    )


def downgrade() -> None:
    op.drop_table("charge_refunds")
    with op.batch_alter_table("clip_takes", schema=None) as batch_op:
        batch_op.drop_column("prompt")
    with op.batch_alter_table("project_clips", schema=None) as batch_op:
        batch_op.drop_column("change")
    with op.batch_alter_table("storyboard_frames", schema=None) as batch_op:
        batch_op.drop_column("change")
