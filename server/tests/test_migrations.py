import json
import logging
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import JSON, MetaData, Table, create_engine, text
from sqlalchemy import inspect as sa_inspect

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


def test_n16_moves_the_old_weekly_defaults_to_97_and_keeps_a_custom_one(tmp_path):
    """One allowance (Reed, 30 Oct): $10 a week, Quick clips only."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n15")
    engine = create_engine(url)
    with engine.begin() as conn:
        for ws, weekly in ((1, 145), (2, 150), (3, 200)):
            _row(conn, "workspaces", id=ws)
            _row(conn, "credit_limits", id=ws, workspace_id=ws, weekly_quick_clip_credits=weekly)
    command.upgrade(cfg, "n16")
    with engine.connect() as conn:
        sql = "SELECT workspace_id, weekly_quick_clip_credits FROM credit_limits"
        got = dict(conn.execute(text(sql)).all())
    assert {k: float(v) for k, v in got.items()} == {1: 97, 2: 97, 3: 200}


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


def test_n17_gives_fomos_money_screens_their_figure_spot(tmp_path):
    """Screen figures: fomo's three money screens get where their figure goes; others none."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n15")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "brands", id=1, slug="fomo")
        _row(conn, "brands", id=2, slug="ironpaws")
        _row(conn, "files", id=1)
        _row(conn, "brand_screens", id=1, brand_id=1, name="Token chart up", file_id=1)
        _row(conn, "brand_screens", id=2, brand_id=1, name="Desktop trading", file_id=1)
        _row(conn, "brand_screens", id=3, brand_id=2, name="Token chart up", file_id=1)
    command.upgrade(cfg, "n17")
    with engine.connect() as conn:
        spots = [r[0] for r in conn.execute(text("SELECT figure_spot FROM brand_screens"))]
    assert json.loads(spots[0])["at"] == [24, 104] and spots[1:] == [None, None]


def test_n18_gives_every_video_no_locks_and_no_outfits_of_its_own(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n17")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "projects", id=1, brand_id=1, workspace_id=1, name="V")
    command.upgrade(cfg, "n18")
    with engine.connect() as conn:
        row = conn.execute(text("SELECT locks, outfits FROM projects")).one()
    assert [json.loads(v) for v in row] == [{}, {}]
    command.downgrade(cfg, "n17")


def test_n20_makes_the_freestyles_table_and_takes_it_away(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n20")
    with create_engine(url).connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM freestyles")).scalar() == 0
    command.downgrade(cfg, "n18")
    with create_engine(url).connect() as conn:
        assert (
            "freestyles"
            not in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")
            .scalars()
            .all()
        )


def test_n19_gives_every_video_an_empty_director_chat(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n20")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "projects", id=1, brand_id=1, workspace_id=1, name="V")
    command.upgrade(cfg, "n19")
    with engine.connect() as conn:
        assert json.loads(conn.execute(text("SELECT director_chat FROM projects")).scalar()) == []
    command.downgrade(cfg, "n20")


def test_n21_hides_nothing_already_there_and_links_a_freestyle_to_its_video(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n19")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "projects", id=1, brand_id=1, workspace_id=1, name="V")
    command.upgrade(cfg, "n21")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT hidden FROM projects")).scalar() in (0, False)
        conn.execute(text("SELECT project_id, up_to FROM freestyles")).all()
    command.downgrade(cfg, "n19")


def test_n35_links_each_product_picture_to_its_library_product(tmp_path):
    """A brand's product word matches its product by name (any case); a word with no product
    makes one in that brand. Items archived before it keep no archive date."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n34")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "workspaces", id=1, name="S")
        for b in (1, 2):
            _row(conn, "brands", id=b, workspace_id=1, name=f"B{b}", slug=f"b{b}")
        _row(conn, "library_items", id=5, workspace_id=1, kind="prop", name="Bag ", archived=False)
        _row(conn, "library_items", id=6, workspace_id=1, kind="prop", name="old", archived=True)
        _row(conn, "library_item_brands", item_id=5, brand_id=1)
        for sid, brand, product in ((1, 1, "bag"), (2, 1, "BAG"), (3, 2, "bag"), (4, 1, "")):
            _row(conn, "brand_screens", id=sid, brand_id=brand, name=f"s{sid}", product=product)
    command.upgrade(cfg, "n35")
    with engine.connect() as conn:
        linked = dict(conn.execute(text("SELECT id, product_id FROM brand_screens")).all())
        made = conn.execute(text("SELECT i.name, ib.brand_id FROM library_items i JOIN "
                                 "library_item_brands ib ON ib.item_id = i.id WHERE i.id = :i"),
                            {"i": linked[3]}).one()  # fmt: skip
        gone = conn.execute(text("SELECT archived_at FROM library_items WHERE id = 6")).scalar()
        # an item archived before n35 has no date: the card says "Archived" (no made-up date)
        app = conn.execute(text("SELECT name, product_type FROM library_items WHERE id = :i"),
                           {"i": linked[4]}).one()  # fmt: skip
        bag = conn.execute(text("SELECT product_type FROM library_items WHERE id = 5")).scalar()
    assert linked[1] == linked[2] == 5 and bag == "physical"  # B1's "Bag", any case
    assert linked[3] not in (5, None) and tuple(made) == ("bag", 2)  # made for B2
    assert tuple(app) == ("B1 app", "app")  # an app screen goes to the brand's app
    assert gone is None
    command.downgrade(cfg, "n34")
    with engine.connect() as conn:
        back = dict(conn.execute(text("SELECT id, product FROM brand_screens")).all())
    assert back == {1: "Bag ", 2: "Bag ", 3: "bag", 4: ""}


def test_n36_keeps_a_short_brand_kit_and_drops_the_end_line_lock(tmp_path):
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n35")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "workspaces", id=1, name="S")
        _row(conn, "brands", id=1, workspace_id=1, name="B", slug="b", tone_notes="Calm",
             end_line="Link in bio", colours=["#000000"])  # fmt: skip
        _row(conn, "projects", id=1, locks={"cast": True, "end_line": True})
    command.upgrade(cfg, "n36")
    with engine.connect() as conn:
        cols = {c["name"] for c in sa_inspect(conn).get_columns("brands")}
        locks = json.loads(conn.execute(text("SELECT locks FROM projects")).scalar())
        kit = conn.execute(text("SELECT tone_notes, colours FROM brands")).one()
    assert "end_line" not in cols and "cta_lines" not in cols and "logo_file_id" in cols
    assert locks == {"cast": True} and kit[0] == "Calm" and json.loads(kit[1]) == ["#000000"]
    command.downgrade(cfg, "n35")


def test_n38_marks_each_host_made_so_far_and_every_video_starts_with_no_switches(tmp_path):
    """A host made before n38 is a UGC talker's or a corner host's: its video's way of
    appearing, so a switch makes a fresh one (QA on #1327)."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n37")
    engine = create_engine(url)
    with engine.begin() as conn:
        _row(conn, "workspaces", id=1, name="S")
        _row(conn, "brands", id=1, workspace_id=1, name="B", slug="b")
        for pid, look in ((1, "ugc"), (2, "dr-pickle")):
            _row(conn, "projects", id=pid, workspace_id=1, brand_id=1, name=f"V{pid}", look=look)
            _row(conn, "host_pieces", id=pid, project_id=pid, take_id=1, number=0)
    command.upgrade(cfg, "n38")
    with engine.connect() as conn:
        how = dict(conn.execute(text("SELECT project_id, how FROM host_pieces")).all())
        log = conn.execute(text("SELECT settings_log, presenter, voice FROM projects")).all()
    assert how == {1: "talks", 2: "corner"}
    assert [tuple(r) for r in log] == [("[]", None, None)] * 2
    command.downgrade(cfg, "n37")
    with engine.connect() as conn:
        cols = [c[1] for c in conn.execute(text("PRAGMA table_info(host_pieces)")).all()]
    assert "how" not in cols


def test_n40_drops_the_omni_voice_and_narration_only(tmp_path):
    """Reed, 5 Nov: a narrated video keeps its narration throughout, so nothing describes an
    Omni voice or turns its speech off; the columns go, and come back on a downgrade."""
    url = f"sqlite:///{tmp_path}/m.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "n40")
    engine = create_engine(url)

    def cols() -> set[str]:
        with engine.connect() as conn:
            return {c[1] for c in conn.execute(text("PRAGMA table_info(projects)")).all()}

    assert not {"omni_voice", "narration_only"} & cols() and "voice" in cols()
    command.downgrade(cfg, "n39")
    assert {"omni_voice", "narration_only"} <= cols()
