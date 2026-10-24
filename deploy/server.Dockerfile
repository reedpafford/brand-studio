# API and worker share this image. Build context: the repo root.
FROM python:3.13-slim
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /srv/server
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/srv/server/.venv/bin:$PATH"
COPY server/pyproject.toml server/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
# Brand screens and logos are imported on first setup from /srv/assets/brands.
COPY assets /srv/assets
# Reference reels a brief can adapt (GET /references): BREAKDOWN.json + contact.jpg each.
COPY docs/references /srv/docs/references
COPY server/alembic.ini ./
COPY server/migrations ./migrations
COPY server/app ./app
RUN useradd --uid 1000 --create-home app && mkdir -p /data/storage && chown -R app /data
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
