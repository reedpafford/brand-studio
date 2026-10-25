from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

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
