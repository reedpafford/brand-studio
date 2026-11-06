"""Approve cast & places (Reed, 4 Nov, S-gaps-07): `projects.cast_ok`, nullable JSON, what the
person making the video approved: each character and place as its stills and takes are made
with, who and when, and the director's card asking for it (app/cast_gate.py). A video with
nothing approved yet waits for the OK before its next still or take. Data step: a look made
for one video is no longer approved card by card, so every drawn one is marked usable (its
video's OK covers it); downgrade leaves them so.

Revision ID: n40
Revises: n39
"""

import sqlalchemy as sa
from alembic import op

revision = "n40"
down_revision = "n39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("cast_ok", sa.JSON(), nullable=True))
    items = sa.table("library_items", sa.column("owner_project_id"),
                     sa.column("sheet_file_id"), sa.column("sheet_approved"))  # fmt: skip
    op.execute(items.update().where(items.c.owner_project_id.is_not(None),
                                    items.c.sheet_file_id.is_not(None))
               .values(sheet_approved=sa.true()))  # fmt: skip


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("cast_ok")
