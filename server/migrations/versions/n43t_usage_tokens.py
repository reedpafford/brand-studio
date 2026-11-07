"""Usage keeps a Claude call's token counts (cost analysis A8): input, output, cache read and
cache write tokens and the pictures sent, so a turn's context size and its cache hits can be
seen. Nullable: other providers' rows and the rows from before have none.

Revision ID: n43t
Revises: n42
"""

import sqlalchemy as sa
from alembic import op

revision = "n43t"
down_revision = "n42"
branch_labels = None
depends_on = None

COLUMNS = ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "images")


def upgrade() -> None:
    with op.batch_alter_table("usage", schema=None) as batch_op:
        for name in COLUMNS:
            batch_op.add_column(sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("usage", schema=None) as batch_op:
        for name in reversed(COLUMNS):
            batch_op.drop_column(name)
