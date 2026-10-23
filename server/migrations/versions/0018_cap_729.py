"""cap_729: Reed, 2026-10-23: the per-video cap is 729 credits ($75), up from 340 ($35).
Saved limits still on the old default move to the new one; any other value the owner chose
stays.

Revision ID: 0018
Revises: 0017
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET per_video_max_credits = 729 WHERE per_video_max_credits = 340"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE credit_limits SET per_video_max_credits = 340 WHERE per_video_max_credits = 729"
    )
