"""brand_screens.deleted_at: a deleted screen is kept, so Undo can bring it back

Revision ID: 0039
Revises: 0038
"""

import sqlalchemy as sa
from alembic import op

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.execute("DELETE FROM brand_screens WHERE deleted_at IS NOT NULL")
    with op.batch_alter_table("brand_screens", schema=None) as batch_op:
        batch_op.drop_column("deleted_at")
