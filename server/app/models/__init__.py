"""Import every model module here so Alembic sees all tables."""

from app.models import (  # noqa: F401
    accounts,
    brands,
    breakdowns,
    clips,
    credits,
    files,
    jobs,
    library,
    projects,
    scripts,
    storyboards,
)
