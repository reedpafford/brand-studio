# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation phase (issue #1): login/team/roles, brands + brand kit, file storage, job queue, usage + credits.
- Server scaffold in review: `server/` (FastAPI, SQLAlchemy, Alembic, ruff, pytest), CI in `.github/workflows/server.yml`. How to run: `server/README.md`.
- Accounts in review: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`), email+password login (httpOnly cookie, hashed session tokens), invites (owner shares the link token), remove member, roles owner/editor.
- Files in review: `POST /files` upload (images/audio/video, no SVG, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`. Storage interface in `server/app/storage.py` (local disk now, S3 later).
- Brands in review: brand CRUD + kit (logo, colours, fonts, style board, tone, never-say, legal line, end card); screens with tags and `default_for` moments. fomo + Iron Paws created on setup; fomo screens imported from `BS_FOMO_SCREENS_DIR` or `python -m app.seed <folder>` (copy story-studio `style-references/fomo-ui/` later).
- Libraries in review: `/library/{character|place|prop}` filtered by `?brand_id=`; an item can be in several brands; characters have sheet images, outfits, voice sample; every edit saves a version that can be restored.
- Rule for every resource PR: use `tests/helpers.py` (`assert_hidden` for other-workspace 404s, `assert_no_dollars` for editors) and check attached file ids with `get_file(..., kind)` (same workspace + right kind).
- Convention: any dollar field is named `*_usd` and only sent to owners (a guard test lands with usage).
## Next
- Builder-Server: jobs + usage, credits (one PR each).
- Explorer maps tezu.ai once network access is granted.
## Blocked
- tezu.ai access (Reed adding it).
