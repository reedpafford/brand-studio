"""Song in any look (n15): Song is a video's type (its script's kind), never its look. A row
still on look "song" moves to its brand's default look (House if that was Song too); kind
stays. No new column.

Revision ID: n15
Revises: n14
"""

from alembic import op

revision = "n15"
down_revision = "n14"  # tracks next's head for CI; re-pointed to the head just before merge
branch_labels = None
depends_on = None

BRAND_LOOK = "(SELECT b.default_look FROM brands b WHERE b.id = {}.brand_id)"


def upgrade() -> None:
    op.execute("UPDATE brands SET default_look = 'house' WHERE default_look = 'song'")
    for table in ("projects", "scripts"):
        brand = BRAND_LOOK.format(table)
        op.execute(f"UPDATE {table} SET look = COALESCE({brand}, 'house') WHERE look = 'song'")  # noqa: S608
    op.execute("DELETE FROM look_switches WHERE look_id = 'song'")


def downgrade() -> None:
    pass  # which rows were on Song isn't kept; they stay on their brand's look
