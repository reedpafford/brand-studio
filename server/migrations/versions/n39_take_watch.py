"""The director's watch of each take and each host piece (rule 11, Reed 2026-11-03):
`clip_takes.watch` and `host_pieces.watch`, JSON, nullable: what it found looking at
it and what it did ({state, found, faults, did, action, note, at, job_id, remake_job_id,
remake_credits}); null before it shipped or while watches are off.

Revision ID: n39
Revises: n38
"""

import sqlalchemy as sa
from alembic import op

revision = "n39"
down_revision = "n38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("clip_takes", "host_pieces"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("watch", sa.JSON(), nullable=True))


def downgrade() -> None:
    for table in ("host_pieces", "clip_takes"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("watch")
