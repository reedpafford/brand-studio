"""One allowance (n16): Reed, 30 Oct: one weekly editor allowance of $10 (97 credits), Quick
clips only; scripts and videos are a brand's work and run on their budgets. Saved limits still
on an old default (145, or 150 from before 0024) move to 97; any other figure stays.

Revision ID: n16
Revises: n15
"""

from alembic import op

revision = "n16"
down_revision = "n15"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET weekly_quick_clip_credits = 97 "
        "WHERE weekly_quick_clip_credits IN (145, 150)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET weekly_quick_clip_credits = 145 "
        "WHERE weekly_quick_clip_credits = 97"
    )
