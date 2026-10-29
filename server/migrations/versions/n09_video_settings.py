"""Video settings (docs/next/data.md, n09; flows VS1): a video's video and picture models
(null: Auto), the Sung shots a no-lip-sync model turned to B-roll, what each still and take
was made with (so a switch outdates them and switching back makes them current), and a
script's language.

Stills and takes already made are filled in with the model and shape their own job asked for,
or failing that today's default model and the video's shape now, so a switch outdates them
too; their products and Sung shots are read from the frame or clip as it is now.

Revision ID: n09
Revises: n08
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "n09"
down_revision = "n08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.add_column(sa.Column("video_model", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("image_model", sa.String(40), nullable=True))
        batch_op.add_column(
            sa.Column("sung_flipped", sa.JSON(), nullable=False, server_default="[]")
        )
    for table in ("storyboard_frames", "clip_takes"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("made_with", sa.JSON(), nullable=False, server_default="{}")
            )
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("language", sa.String(10), nullable=False, server_default="en")
        )

    _backfill(op.get_bind())


VIDEO_MODEL, IMAGE_MODEL = "seedance-2.5", "nano-banana-2.1"  # today's defaults (Auto)


def _j(value):
    return json.loads(value) if isinstance(value, str) else (value or {})


def _products(conn, refs: list[str]) -> dict:
    screens = sa.table("brand_screens", sa.column("id"), sa.column("product"),
                       sa.column("variant"))  # fmt: skip
    found = {}
    for ref in refs:
        if ref.startswith("screen:"):
            row = conn.execute(sa.select(screens.c.product, screens.c.variant)
                               .where(screens.c.id == int(ref.split(":")[1]))).first()  # fmt: skip
            if row and row.product and row.variant:
                found[row.product] = row.variant
    return found


def _backfill(conn) -> None:
    jobs = sa.table("jobs", sa.column("id"), sa.column("kind"), sa.column("input", sa.JSON),
                    sa.column("output", sa.JSON))  # fmt: skip
    projects = sa.table("projects", sa.column("id"), sa.column("aspect_ratio"))
    takes = sa.table("clip_takes", sa.column("id"), sa.column("job_id"), sa.column("clip_id"),
                     sa.column("made_with", sa.JSON))  # fmt: skip
    clips = sa.table("project_clips", sa.column("id"), sa.column("project_id"),
                     sa.column("references", sa.JSON),
                     sa.column("song_slice", sa.JSON))  # fmt: skip
    frames = sa.table("storyboard_frames", sa.column("id"), sa.column("project_id"),
                      sa.column("file_id"), sa.column("reference_ids", sa.JSON),
                      sa.column("made_with", sa.JSON))  # fmt: skip
    shape_now = dict(conn.execute(sa.select(projects.c.id, projects.c.aspect_ratio)).all())
    for take in conn.execute(sa.select(takes.c.id, takes.c.job_id, takes.c.clip_id)).all():
        clip = conn.execute(sa.select(clips.c.project_id, clips.c.references, clips.c.song_slice)
                            .where(clips.c.id == take.clip_id)).first()  # fmt: skip
        if clip is None:
            continue
        asked = _j(conn.scalar(sa.select(jobs.c.input).where(jobs.c.id == take.job_id)))
        refs = [r["id"] for r in (_j(clip.references) or []) if r.get("kind") == "image"]
        made = {"model": asked.get("model") or VIDEO_MODEL,
                "aspect_ratio": (asked.get("input") or {}).get("aspect_ratio")
                or shape_now[clip.project_id],
                "products": _products(conn, refs),
                "sung_shots": sorted(_j(clip.song_slice).get("sung_shots", []))}  # fmt: skip
        conn.execute(takes.update().where(takes.c.id == take.id).values(made_with=made))
    asked_for = {}  # a still's file -> its job's input
    for job in conn.execute(sa.select(jobs.c.input, jobs.c.output).where(jobs.c.kind == "image")):
        asked, got = _j(job.input), _j(job.output)
        if asked.get("step") == "frame" and got.get("file_ids"):
            asked_for[got["file_ids"][0]] = asked
    stills = sa.select(frames.c.id, frames.c.project_id, frames.c.file_id, frames.c.reference_ids)
    for frame in conn.execute(stills.where(frames.c.file_id.is_not(None))).all():
        asked = asked_for.get(frame.file_id, {})
        made = {"model": asked.get("model") or IMAGE_MODEL,
                "aspect_ratio": (asked.get("input") or {}).get("aspect_ratio")
                or shape_now[frame.project_id],
                "products": _products(conn, _j(frame.reference_ids) or [])}  # fmt: skip
        conn.execute(frames.update().where(frames.c.id == frame.id).values(made_with=made))


def downgrade() -> None:
    with op.batch_alter_table("scripts", schema=None) as batch_op:
        batch_op.drop_column("language")
    for table in ("clip_takes", "storyboard_frames"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("made_with")
    with op.batch_alter_table("projects", schema=None) as batch_op:
        for name in ("sung_flipped", "image_model", "video_model"):
            batch_op.drop_column(name)
