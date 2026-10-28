"""A look's role text check (Reed, 2026-10-28: Biscuit's sheet is a French bulldog but his
role still says golden retriever): the role text it was compared with, and that text
rewritten to match the sheet when the sheet contradicts it

Revision ID: 0053
Revises: 0052
"""

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("text_fit", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        batch_op.drop_column("text_fit")
