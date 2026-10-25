"""editor_allowance_145: Reed, 2026-10-25: one weekly editor allowance of $15 (145 credits)
covers Quick clips and editors' own scripts, down from 150 for Quick clips alone. Saved limits
still on the old default move to the new one; any other value the owner chose stays.

Revision ID: 0024
Revises: 0023
"""

from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET weekly_quick_clip_credits = 145 "
        "WHERE weekly_quick_clip_credits = 150"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET weekly_quick_clip_credits = 150 "
        "WHERE weekly_quick_clip_credits = 145"
    )
