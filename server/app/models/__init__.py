"""Import every model module here so Alembic sees all tables."""

from app.models import accounts, brands, credits, files, jobs, library  # noqa: F401
