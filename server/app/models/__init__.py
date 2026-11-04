"""Import every model module here so Alembic sees all tables."""

from app import hidden  # noqa: F401 - the hidden rows' filter, on every session
from app.models import (  # noqa: F401
    accounts,
    brands,
    breakdowns,
    checks,
    clips,
    credits,
    files,
    folders,
    freestyles,
    jobs,
    languages,
    library,
    looks,
    projects,
    script_library,
    scripts,
    seen,
    songs,
    storyboards,
    voices,
)
