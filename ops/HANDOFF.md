# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation phase (issue #1): login/team/roles, brands + brand kit, file storage, job queue, usage + credits.
- Server scaffold in review: `server/` (FastAPI, SQLAlchemy, Alembic, ruff, pytest), CI in `.github/workflows/server.yml`. How to run: `server/README.md`.
- Accounts in review: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`), email+password login (httpOnly cookie, hashed session tokens), invites (owner shares the link token), remove member, roles owner/editor.
- Files in review: `POST /files` upload (images/audio/video, no SVG, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`. Storage interface in `server/app/storage.py` (local disk now, S3 later).
- Convention: any dollar field is named `*_usd` and only sent to owners (a guard test lands with usage).
## Next
- Builder-Server: brands, libraries, jobs + usage, credits (one PR each).
- Explorer maps tezu.ai once network access is granted.
## Blocked
- tezu.ai access (Reed adding it).
