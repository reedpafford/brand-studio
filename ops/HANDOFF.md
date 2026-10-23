# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation phase (issue #1). Merged: scaffold, accounts, files. How to run: `server/README.md`.
- In review: brands (#5), libraries (#6), jobs + usage (stacked on #6).
- Accounts: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`); login throttled; invites; roles owner/editor.
- Files: `POST /files` (type checked by content, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage interface `server/app/storage.py`.
- Brands: kit + screens with tags and `default_for` moments; fomo + Iron Paws created on setup; fomo screens from `BS_FOMO_SCREENS_DIR` or `python -m app.seed <folder>`.
- Libraries: `/library/{character|place|prop}?brand_id=`, multi-brand, version history + restore.
- Jobs: worker `python -m app.worker` polls the `jobs` table. Providers behind `app/providers` (fake only; Replicate later). Paid submits never auto-retried; restarts re-check running jobs. Usage rows hold `cost_usd`; `GET /usage` is owner-only.
- Rule for every resource PR: use `tests/helpers.py` (`assert_hidden` for other-workspace 404s, `assert_no_dollars` for editors) and check attached file ids with `get_file(..., kind)`.
- Rule: dollar fields are named `*_usd`; `tests/test_no_dollars_for_editors.py` fails if a non-owner route returns one.
## Next
- Builder-Server: credits (rates, project budgets, `needs_owner_approval`).
- Explorer maps tezu.ai once network access is granted.
## Blocked
- tezu.ai access (Reed adding it).
