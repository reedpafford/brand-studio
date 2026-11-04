"""What Make forecast for a video, and Reed's 1-5 score and note on it (app/scorecard.py).

Revision ID: n25
Revises: n24
"""

import sqlalchemy as sa
from alembic import op

revision = "n25"
down_revision = "n24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("forecast_credits", sa.Numeric(12, 3), nullable=True))
        batch_op.add_column(sa.Column("forecast_basis", sa.String(60), nullable=True))
        batch_op.add_column(sa.Column("score", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("score_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        for name in ("score_note", "score", "forecast_basis", "forecast_credits"):
            batch_op.drop_column(name)
