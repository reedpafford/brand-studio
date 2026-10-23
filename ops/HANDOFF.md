# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation phase (issue #1). Merged: scaffold, accounts, files, brands, libraries, jobs + usage. In review: credits. How to run: `server/README.md`.
- Accounts: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`); login throttled; invites; roles owner/editor.
- Files: `POST /files` (type checked by content, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage interface `server/app/storage.py`.
- Brands: kit + screens with tags and `default_for` moments; fomo + Iron Paws created on setup; fomo screens from `BS_FOMO_SCREENS_DIR` or `python -m app.seed <folder>`.
- Libraries: `/library/{character|place|prop}?brand_id=`, multi-brand, version history + restore. Editors archive (reversible: `?archived=true`, `/unarchive`); permanent delete is owner-only, from the archive.
- Jobs: worker `python -m app.worker` polls the `jobs` table. Providers behind `app/providers` (fake only; Replicate later). Paid submits never auto-retried; restarts re-check running jobs. Usage rows hold `cost_usd`; `GET /usage` is owner-only.
- Rule for every resource PR: use `tests/helpers.py` (`assert_hidden` for other-workspace 404s, `assert_no_dollars` for editors) and check attached file ids with `get_file(..., kind)`.
- Rule: dollar fields are named `*_usd`; `tests/test_no_dollars_for_editors.py` fails if a non-owner route returns one.
- Credits: 1 credit = $0.1028 real cost = 1 s of 480p. Rates (seeded, owner-editable) give estimates; real cost replaces them on success; kinds without a rate estimate at 1/unit. Projects: editors set planned length, budget = 2x (max 180 s without owner). Quick clips: 150 credits/editor/week. Over any limit = `needs_owner_approval`. Limits owner-editable at `/credits/limits`. Check + reserve is one locked transaction.
## Next
- Builder-Server: foundation done once credits merges; next issue from the Producer.
- Explorer maps tezu.ai once network access is granted.
## Blocked
- tezu.ai access (Reed adding it).
