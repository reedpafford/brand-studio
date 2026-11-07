"""Omni 1.2 replaces 1.1 (Reed, 6 Nov): stored `gemini-omni-1.1` ids become `gemini-omni-1.2`,
so an older video's clips and takes still name a model in the catalogue. Data only: a clip's
own model (`project_clips.model.id`), a take's (`clip_takes.made_with.model`) and a video's
(`projects.video_model`). Downgrade leaves them on 1.2 (1.1 is gone from the catalogue).

Revision ID: n43
Revises: n42
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "n43"
down_revision = "n42"
branch_labels = None
depends_on = None

OLD, NEW = "gemini-omni-1.1", "gemini-omni-1.2"


def _j(value):
    return json.loads(value) if isinstance(value, str) else value


def upgrade() -> None:
    conn = op.get_bind()
    for name, column, key in (("project_clips", "model", "id"),
                              ("clip_takes", "made_with", "model")):  # fmt: skip
        table = sa.table(name, sa.column("id"), sa.column(column, sa.JSON))
        for row in conn.execute(sa.select(table.c.id, table.c[column])).all():
            data = _j(row[1])
            if isinstance(data, dict) and data.get(key) == OLD:
                conn.execute(table.update().where(table.c.id == row[0])
                             .values({column: {**data, key: NEW}}))  # fmt: skip
    projects = sa.table("projects", sa.column("video_model"))
    conn.execute(projects.update().where(projects.c.video_model == OLD).values(video_model=NEW))


def downgrade() -> None:
    pass
