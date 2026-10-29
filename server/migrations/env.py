from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

import app.models  # noqa: F401  (registers tables)
from app.db import Base
from app.settings import get_settings

config = context.config
if config.config_file_name:
    # Keep the app's loggers on: by default fileConfig turns off every logger that already exists,
    # so a migration run (in tests, or before the app logs) would silence them.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

url = config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run() -> None:
    engine = create_engine(url)
    with engine.connect() as conn:
        context.configure(
            connection=conn,
            target_metadata=Base.metadata,
            render_as_batch=True,  # SQLite needs batch mode for ALTER
        )
        with context.begin_transaction():
            context.run_migrations()


run()
