import json
import logging
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, MetaData, Table, create_engine, text

from app.db import Base


def test_migrations_match_models(tmp_path):
    """Upgrading to head must produce exactly the tables the models declare."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    command.check(cfg)  # raises if models and migrations differ
    engine = create_engine(url)
    with engine.connect() as conn:
        tables = set(engine.dialect.get_table_names(conn)) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)


def test_existing_workspaces_get_the_launch_rate(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0005")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO workspaces (id, name, created_at) VALUES (1, 'S', '2026-01-01')")
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT workspace_id, kind FROM credit_rates")).all()
    assert (1, "video-480p") in rows and len(rows) == 6


def test_saved_caps_on_the_old_default_move_to_729(tmp_path):
    """Reed raised the per-video cap from 340 to 729; an owner's own value is kept."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "0017")
    engine = create_engine(url)
    with engine.begin() as conn:
        for ws, cap in ((1, 340), (2, 500)):
            conn.execute(
                text(
                    "INSERT INTO workspaces (id, name, created_at) VALUES (:id, 'S', '2026-01-01')"
                ),
                {"id": ws},
            )
            conn.execute(
                text(
                    "INSERT INTO credit_limits (workspace_id, max_planned_seconds, "
                    "weekly_quick_clip_credits, per_video_max_credits, created_at) "
                    "VALUES (:ws, 170, 150, :cap, '2026-01-01')"
                ),
                {"ws": ws, "cap": cap},
            )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        caps = dict(
            conn.execute(
                text("SELECT workspace_id, per_video_max_credits FROM credit_limits")
            ).all()
        )
        weekly = conn.execute(text("SELECT weekly_quick_clip_credits FROM credit_limits")).all()
    assert caps == {1: 729, 2: 500}
    assert {float(w) for (w,) in weekly} == {145}  # the old 150 default became $15 (0024)


def test_n08_copies_never_say_and_end_line_and_keeps_them(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n05")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO workspaces (id, name, created_at) VALUES (1, 'S', '2026-01-01')")
        )
        conn.execute(text(
            "INSERT INTO brands (id, workspace_id, name, slug, archived, colours, fonts,"
            " tone_notes, never_say, legal_line, end_line, created_at) VALUES (1, 1, 'B', 'b',"
            " 0, '[]', '[]', '', :never, '', 'Link in bio', '2026-01-01')"
        ), {"never": json.dumps(["cure", "cure", " guaranteed "])})  # fmt: skip
    command.upgrade(cfg, "n08")
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT dont_list, cta_lines, never_say, end_line FROM brands")
        ).one()
    assert json.loads(row.dont_list) == ["cure", "guaranteed"]
    lines = json.loads(row.cta_lines)
    assert [(x["text"], x["default"]) for x in lines] == [("Link in bio", True)]
    assert row.end_line == "Link in bio" and json.loads(row.never_say)[0] == "cure"  # kept
    command.downgrade(cfg, "n05")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT never_say, end_line FROM brands")).one()
    assert json.loads(row.never_say) == ["cure", "guaranteed"] and row.end_line == "Link in bio"


def _row(conn, table: str, **values) -> None:
    """Insert with every other required column given a stand-in."""
    rows = Table(table, MetaData(), autoload_with=conn)
    for col in rows.columns:
        if not col.nullable and col.server_default is None and col.name not in values:
            kind = list if isinstance(col.type, JSON) else col.type.python_type
            values[col.name] = datetime(2026, 1, 1) if kind is datetime else kind()
    conn.execute(rows.insert().values(**values))


def test_n09_fills_in_what_stills_and_takes_were_made_with(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n08")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "brand_screens", id=2, product="Soda", variant="Lime")
        _row(conn, "projects", id=1, aspect_ratio="1:1")
        _row(conn, "project_clips", id=1, project_id=1, song_slice={"sung_shots": ["s2", "s1"]},
             references=[{"kind": "image", "id": "screen:2"}])  # fmt: skip
        _row(conn, "jobs", id=1, kind="video",
             input={"model": "seedance-2.0", "input": {"aspect_ratio": "16:9"}})  # fmt: skip
        _row(conn, "jobs", id=2, kind="video", input={})  # nothing recorded
        _row(conn, "clip_takes", id=1, clip_id=1, job_id=1)
        _row(conn, "clip_takes", id=2, clip_id=1, job_id=2)
        _row(conn, "jobs", id=3, kind="image", output={"file_ids": [7]},
             input={"step": "frame", "model": "nano-banana-pro",
                    "input": {"aspect_ratio": "9:16"}})  # fmt: skip
        _row(conn, "storyboard_frames", id=1, project_id=1, file_id=7, reference_ids=["screen:2"])
        _row(conn, "storyboard_frames", id=2, project_id=1, file_id=8, reference_ids=[])
        _row(conn, "storyboard_frames", id=3, project_id=1, reference_ids=[])  # no still yet
    command.upgrade(cfg, "n09")
    with engine.connect() as conn:
        takes, stills = (
            [json.loads(r[0]) for r in conn.execute(text(f"SELECT made_with FROM {t}"))]  # noqa: S608
            for t in ("clip_takes", "storyboard_frames")
        )
    soda, sung = {"Soda": "Lime"}, ["s1", "s2"]
    assert takes == [
        {"model": "seedance-2.0", "aspect_ratio": "16:9", "products": soda, "sung_shots": sung},
        {"model": "seedance-2.5", "aspect_ratio": "1:1", "products": soda, "sung_shots": sung},
    ]
    assert stills == [
        {"model": "nano-banana-pro", "aspect_ratio": "9:16", "products": soda},
        {"model": "nano-banana-2.1", "aspect_ratio": "1:1", "products": {}},
        {},
    ]


def test_n12_keeps_each_roles_own_look_under_the_look_it_was_drawn_in(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n03")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "library_items", id=4, kind="character", sheet_look="disney-pixar")
        _row(conn, "projects", id=1, slot_looks={"7": 4, "8": None, "9": 99})  # 99: gone
        _row(conn, "projects", id=2)
    command.upgrade(cfg, "n12")
    with engine.connect() as conn:
        rows = [json.loads(r[0]) for r in conn.execute(text("SELECT own_looks FROM projects"))]
    assert rows == [{"7": {"disney-pixar": 4}}, {}]
    command.downgrade(cfg, "n03")


def test_n15_moves_what_was_on_the_song_look_to_its_brands_look(tmp_path):
    """Song in any look: Song is a type, never a look. Kind stays."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n14")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "brands", id=1, slug="a", default_look="claymation")
        _row(conn, "brands", id=2, slug="b", default_look="song")
        _row(conn, "projects", id=1, brand_id=1, look="song")
        _row(conn, "projects", id=2, brand_id=2, look="song")
        _row(conn, "projects", id=3, brand_id=1, look="paper")  # never Song: kept
        _row(conn, "scripts", id=1, brand_id=1, look="song", kind="song")
        _row(conn, "look_switches", id=1, workspace_id=1, look_id="song", on=True)
        _row(conn, "look_switches", id=2, workspace_id=1, look_id="paper", on=True)
    command.upgrade(cfg, "n15")
    with engine.connect() as conn:

        def got(sql):
            return [tuple(r) for r in conn.execute(text(sql))]

        assert got("SELECT default_look FROM brands") == [("claymation",), ("house",)]
        assert got("SELECT look FROM projects") == [("claymation",), ("house",), ("paper",)]
        assert got("SELECT look, kind FROM scripts") == [("claymation", "song")]
        assert got("SELECT look_id FROM look_switches") == [("paper",)]


def test_a_migration_run_leaves_the_app_loggers_on(tmp_path):
    """fileConfig in env.py must not switch off loggers made before it. It did by default, so
    test_clip_prompts_finish's log check failed whenever it ran after this file."""
    log = logging.getLogger("app.clip_prompts")  # made at import, before the migration runs
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_path}/m.db")
    command.upgrade(cfg, "head")
    assert not log.disabled
