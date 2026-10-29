"""Import every model module here so Alembic sees all tables."""

from app.models import (  # noqa: F401
    accounts,
    brands,
    breakdowns,
    checks,
    clips,
    credits,
    files,
    folders,
    jobs,
    library,
    looks,
    projects,
    script_library,
    scripts,
    songs,
    storyboards,
)
