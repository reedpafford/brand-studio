"""A shot's spoken line never keeps a note in brackets (#1490): saved plans, songs' and
narrations' included, have their notes taken out of each shot's `line` ("I bought [quietly]
the dip." is "I bought the dip."), as `Shot.line` reads them now, so the clip-prompt writer,
its check and the take word check see the same line. Data only, in `breakdowns.data` and
`script_drafts.breakdown`; a row that isn't a plan is left as it is, and running it again
changes nothing. Downgrade leaves the lines as they are (the notes were direction).

Revision ID: n45
Revises: n44
"""

import json
import re

import sqlalchemy as sa
from alembic import op

revision = "n45"
down_revision = "n44"
branch_labels = None
depends_on = None

NOTE = re.compile(r"\s*\[[^\[\]]*\]")  # as app.prompts.NOTE, fixed here for this migration


def cleaned(data):
    """The plan with its shots' lines without notes, or None when nothing changes."""
    data = json.loads(data) if isinstance(data, str) else data
    scenes = data.get("scenes") if isinstance(data, dict) else None
    changed = False
    for scene in scenes if isinstance(scenes, list) else []:
        shots = scene.get("shots") if isinstance(scene, dict) else None
        for shot in shots if isinstance(shots, list) else []:
            line = shot.get("line") if isinstance(shot, dict) else None
            if isinstance(line, str) and NOTE.search(line):
                shot["line"], changed = NOTE.sub("", line).strip(), True
    return data if changed else None


def upgrade() -> None:
    conn = op.get_bind()
    for name, column in (("breakdowns", "data"), ("script_drafts", "breakdown")):
        table = sa.table(name, sa.column("id"), sa.column(column, sa.JSON))
        for row in conn.execute(sa.select(table.c.id, table.c[column])).all():
            try:
                data = cleaned(row[1])
            except ValueError:  # not JSON: not a plan
                continue
            if data is not None:
                conn.execute(table.update().where(table.c.id == row[0]).values({column: data}))


def downgrade() -> None:
    pass
