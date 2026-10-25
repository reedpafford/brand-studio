"""project finished_at: when a video became "Video done" (Usage, DECISIONS #237), backfilled
from its first final video

Revision ID: 0028
Revises: 0027
"""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("finished_at", sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE projects SET finished_at = (SELECT MIN(created_at) FROM final_videos "
        "WHERE final_videos.project_id = projects.id)"
    )


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("finished_at")
