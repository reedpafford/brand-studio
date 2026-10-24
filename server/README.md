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

Local runs without real calls: set `BS_FAKE_PROVIDERS=true` for both the server and the worker.
Stand-ins replace Replicate and Claude (grey pictures and videos, simple answers in the right
shape), so a project can be clicked through from script to final cut for free. Never set it on
the live server.
`uv run python -m scripts.fake_run` makes both done-test videos that way, end to end through
the API, and exits 1 if anything goes wrong (a quick regression check).

## Deploy notes
- Paid generation (Replicate, Claude) is off unless `BS_GENERATION_ENABLED=true`. While off, Generate answers "switched off" and the worker leaves paid jobs queued.
- Behind a proxy, run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy ip>` so login throttling sees the real client IP, not the proxy's.
- `ffmpeg` must be installed: "Make the video" stitches the picked clips with it (free, no provider).
- Set `BS_SETUP_TOKEN` (a long random secret) before first setup; remove it afterwards.
- Production runs with Docker Compose and Postgres: see `deploy/README.md`.
