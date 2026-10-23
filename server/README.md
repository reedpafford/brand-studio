# Server
FastAPI + SQLAlchemy + Alembic. Settings come from `BS_*` environment variables (see `app/settings.py`).

```
uv sync                                   # install
uv run alembic upgrade head               # create/upgrade the database
uv run uvicorn app.main:create_app --factory --reload
uv run ruff check . && uv run pytest      # lint + tests
```
API docs: `/docs` once running.
