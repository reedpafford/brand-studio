"""Import every model module here so Alembic sees all tables."""

from app.models import (  # noqa: F401
    accounts,
    brands,
    credits,
    files,
    jobs,
    library,
    projects,
    scripts,
)
