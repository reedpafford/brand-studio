# Server
FastAPI + SQLAlchemy + Alembic. Settings come from `BS_*` environment variables (see `app/settings.py`).

```
uv sync                                   # install
uv run alembic upgrade head               # create/upgrade the database
uv run uvicorn app.main:create_app --factory --reload
uv run python -m app.worker                # background worker (separate process)
uv run ruff check . && uv run pytest      # lint + tests
```
API docs: `/docs` once running.

## Deploy notes
- Behind a proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so login throttling sees the real client IP, not the proxy's.
- Set `BS_SETUP_TOKEN` (a long random secret) before first setup; remove it afterwards.
