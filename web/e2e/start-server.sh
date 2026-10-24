#!/usr/bin/env bash
# Starts the real API on :8000 and its worker, with a throwaway database, for the browser tests.
# Claude and Replicate are stood in for by free fakes (BS_FAKE_PROVIDERS): nothing is sent or
# billed, so tests may press Generate. Paid generation stays switched off as well.
set -euo pipefail
cd "$(dirname "$0")/../../server"
data="$(cd .. && pwd)/web/e2e/.data"
rm -rf "$data" && mkdir -p "$data"
export BS_DATABASE_URL="sqlite:///$data/e2e.db"
export BS_STORAGE_DIR="$data/files"
export BS_SETUP_TOKEN="e2e-setup-code"
export BS_COOKIE_SECURE=false
export BS_GENERATION_ENABLED=false  # real paid generation is off
export BS_FAKE_PROVIDERS=true       # the stand-ins are free, so tests may press Generate
export BS_WORKER_POLL_SECONDS=0.2
uv run alembic upgrade head
uv run python -m app.worker &
worker=$!
trap 'kill $worker 2>/dev/null || true' EXIT
uv run uvicorn app.main:create_app --factory --port 8000
