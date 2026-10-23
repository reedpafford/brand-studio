#!/usr/bin/env bash
# Starts the real API on :8000 with a throwaway database, for the browser tests.
set -euo pipefail
cd "$(dirname "$0")/../../server"
data="$(cd .. && pwd)/web/e2e/.data"
rm -rf "$data" && mkdir -p "$data"
export BS_DATABASE_URL="sqlite:///$data/e2e.db"
export BS_STORAGE_DIR="$data/files"
export BS_SETUP_TOKEN="e2e-setup-code"
export BS_COOKIE_SECURE=false
uv run alembic upgrade head
exec uv run uvicorn app.main:create_app --factory --port 8000
