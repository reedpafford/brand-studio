# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation phase (issue #1). Foundation merged (scaffold, accounts, files, brands, libraries, jobs + usage, credits). Now: generation (issue #15); catalogue in review. How to run: `server/README.md`.
- Accounts: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`); login throttled; invites; roles owner/editor.
- Files: `POST /files` (type checked by content, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage interface `server/app/storage.py`.
- Brands: kit + screens with tags and `default_for` moments; fomo + Iron Paws created on setup; fomo screens, logo and style board imported on setup from `assets/brands/fomo/` (override with `BS_FOMO_SCREENS_DIR`, re-run with `python -m app.seed <folder>`).
- Libraries: `/library/{character|place|prop}?brand_id=`, multi-brand, version history + restore. Editors archive (reversible: `?archived=true`, `/unarchive`); permanent delete is owner-only, from the archive.
- Jobs: worker `python -m app.worker` polls the `jobs` table. Providers behind `app/providers` (fake only; Replicate later). Paid submits never auto-retried; restarts re-check running jobs. Usage rows hold `cost_usd`; `GET /usage` is owner-only.
- Rule for every resource PR: use `tests/helpers.py` (`assert_hidden` for other-workspace 404s, `assert_no_dollars` for editors) and check attached file ids with `get_file(..., kind)`.
- Rule: dollar fields are named `*_usd`; `tests/test_no_dollars_for_editors.py` fails if a non-owner route returns one.
- Credits: 1 credit = $0.1028 real cost = 1 s of 480p. Rates (seeded, owner-editable) give estimates; real cost replaces them on success; kinds without a rate estimate at 1/unit. Projects: editors set planned length, budget = 2x (max 180 s without owner). Quick clips: 150 credits/editor/week. Over any limit = `needs_owner_approval`. Limits owner-editable at `/credits/limits`. Check + reserve is one locked transaction.
- Catalogue: `server/app/catalogue.json` is the one list of models (limits from Replicate schemas, snapshots in `tests/fixtures/replicate`). `GET /models` (credits) for everyone, `GET /models/prices` (dollars) owner-only.
- Replicate (in review): `app/providers/replicate.py`. Jobs with `provider="replicate"` and input `{"model": <catalogue id>, "input": {...}}`; the worker polls, copies outputs into our storage (`output.file_ids`), records real cost (from Replicate metrics, else marked `estimated`). Token from `REPLICATE_API_TOKEN` if set, else the sandbox proxy adds it; base URL `BS_REPLICATE_BASE_URL`.
- Claude client (in review): `server/app/claude.py` `ask()` = claude-opus-5-5, adaptive thinking, Pydantic structured output, cached system prompt (base + brand), server-side fallbacks. Key from `STUDIO_ANTHROPIC_KEY` only; always api.anthropic.com.
## Next
- Builder-Server: Quick clip routes, then #24 (script projects).
- Explorer maps tezu.ai once network access is granted.
## Blocked
- tezu.ai access (Reed adding it).
