"""A Cast & places item's main sheet says which style it is in (Reed, 15 Nov: "it should only
get/expect animation when the style is animated"): `library_items.sheet_look`, kept until now
only for a video's own look. Nothing new is stored; the rows made before this are put right:
a PERSON's main sheet Seedream drew (the real-looking people of the Movie ads made by hand) is
Movie's, and an item with no sheet yet has no style until one is asked, never House by
assumption. Every other main sheet stays House, as it was drawn: a place Seedream drew with no
style named was drawn with House's words.

Revision ID: n55
Revises: n54
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "n55"
down_revision = "n54"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(  # Cast & places only: a video's or script's own look keeps its own
        "UPDATE library_items SET sheet_look = '' WHERE sheet_file_id IS NULL "
        "AND owner_project_id IS NULL AND owner_script_id IS NULL"))  # fmt: skip
    drawn = conn.execute(sa.text(
        "SELECT input, output FROM jobs WHERE CAST(input AS TEXT) LIKE :model"),
        {"model": "%seedream-5.5%"})  # fmt: skip
    for row in drawn.all():
        said, out = (json.loads(x) if isinstance(x, str) else x or {} for x in row)
        if said.get("step") != "sheet" or said.get("sheet_look_id"):
            continue  # an owner's sheet in another look already says its look
        for file_id in out.get("file_ids") or []:
            conn.execute(sa.text(
                "UPDATE library_items SET sheet_look = 'movie' WHERE id = :item "
                "AND kind = 'character' AND sheet_file_id = :file AND owner_project_id IS NULL "
                "AND owner_script_id IS NULL"),
                {"item": said.get("library_item_id"), "file": file_id})  # fmt: skip


def downgrade() -> None:
    op.execute("UPDATE library_items SET sheet_look = 'house' WHERE sheet_look = ''")
