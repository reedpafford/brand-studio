"""Brand setup (docs/next/data.md, n08; flows BR1): a brand's audience, Do and Don't lists,
CTA lines, default cast, music style, language and look, and a product's short description
and main claim. `never_say` and `end_line` stay (main still reads them) and are copied into
`dont_list` and `cta_lines`; next writes them through until the move to main drops them.

Revision ID: n08
Revises: n07
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = "n08"
down_revision = "n07"  # tracks next's head for CI; moves to n05 before merge (Next-Lead)
branch_labels = None
depends_on = None

BRAND_TEXT = ("audience", "music_style")
BRAND_LISTS = ("do_list", "dont_list", "cta_lines", "default_cast")


def _list(value) -> list:
    found = json.loads(value) if isinstance(value, str) else value
    return found if isinstance(found, list) else []


def upgrade() -> None:
    with op.batch_alter_table("brands", schema=None) as batch_op:
        for name in BRAND_TEXT:
            batch_op.add_column(sa.Column(name, sa.Text(), nullable=False, server_default=""))
        for name in BRAND_LISTS:
            batch_op.add_column(sa.Column(name, sa.JSON(), nullable=False, server_default="[]"))
        batch_op.add_column(
            sa.Column("default_language", sa.String(10), nullable=False, server_default="en")
        )
        batch_op.add_column(
            sa.Column("default_look", sa.String(40), nullable=False, server_default="house")
        )
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        for name in ("short_description", "main_claim"):
            batch_op.add_column(sa.Column(name, sa.Text(), nullable=False, server_default=""))
    brands = sa.table("brands", sa.column("id"), sa.column("never_say", sa.JSON),
                      sa.column("end_line"), sa.column("dont_list", sa.JSON),
                      sa.column("cta_lines", sa.JSON))  # fmt: skip
    conn = op.get_bind()
    for row in conn.execute(sa.select(brands.c.id, brands.c.never_say, brands.c.end_line)):
        dont = list(dict.fromkeys(x.strip() for x in _list(row.never_say) if str(x).strip()))
        line = (row.end_line or "").strip()
        cta = [{"id": uuid.uuid4().hex[:12], "text": line, "default": True,
                "deleted_at": None}] if line else []  # fmt: skip
        conn.execute(brands.update().where(brands.c.id == row.id)
                     .values(dont_list=dont, cta_lines=cta))  # fmt: skip


def downgrade() -> None:
    brands = sa.table("brands", sa.column("id"), sa.column("never_say", sa.JSON),
                      sa.column("end_line"), sa.column("dont_list", sa.JSON),
                      sa.column("cta_lines", sa.JSON))  # fmt: skip
    conn = op.get_bind()
    for row in conn.execute(sa.select(brands.c.id, brands.c.dont_list, brands.c.cta_lines)):
        live = [x for x in _list(row.cta_lines) if not x.get("deleted_at")]
        default = next((x["text"] for x in live if x.get("default")), "")
        conn.execute(brands.update().where(brands.c.id == row.id)
                     .values(never_say=_list(row.dont_list), end_line=default))  # fmt: skip
    with op.batch_alter_table("library_items", schema=None) as batch_op:
        for name in ("short_description", "main_claim"):
            batch_op.drop_column(name)
    with op.batch_alter_table("brands", schema=None) as batch_op:
        for name in (*BRAND_TEXT, *BRAND_LISTS, "default_language", "default_look"):
            batch_op.drop_column(name)
