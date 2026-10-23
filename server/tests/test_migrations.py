from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

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
