#!/usr/bin/env bash
# Regenerate src/api/schema.d.ts from the server's OpenAPI. Run after any server API change.
set -euo pipefail
cd "$(dirname "$0")/.."
tmp="$(mktemp)"
(cd ../server && BS_SETUP_TOKEN=unused uv run python -c \
  'import json; from app.main import create_app; print(json.dumps(create_app().openapi()))') > "$tmp"
npx openapi-typescript "$tmp" -o src/api/schema.d.ts
rm "$tmp"
