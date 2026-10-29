"""Own looks per look (flows VS1 "U", ST1: the earlier looks come back, kept per look): each
role's own looks made for this video, {slot_id: {look: item_id}}, so switching the video's
look back re-casts the role to the one it already has in that look, free. Filled for videos
made before this from each role's own look and the look it was drawn in.

Revision ID: n12
Revises: n03
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "n12"
down_revision = "n03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("own_looks", sa.JSON(), nullable=False, server_default="{}"))
    conn = op.get_bind()
    looks = dict(conn.execute(sa.text("SELECT id, sheet_look FROM library_items")).all())
    for pid, raw in conn.execute(sa.text("SELECT id, slot_looks FROM projects")).all():
        slots = json.loads(raw) if isinstance(raw, str) else raw or {}
        filled = {slot: {looks[item] or "house": item} for slot, item in slots.items()
                  if item in looks}  # fmt: skip
        if filled:
            conn.execute(sa.text("UPDATE projects SET own_looks = :v WHERE id = :id"),
                         {"v": json.dumps(filled), "id": pid})  # fmt: skip


def downgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("own_looks")
