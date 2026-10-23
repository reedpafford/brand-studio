# Handoff (current state, rewritten not appended; keep under 60 lines)
## Now
- Foundation done (#2–#8). tezu.ai mapped (#9, docs/tezu).
- Design system and screens merged (#11–#17, #20, #21, #26, #29).
- Merged: catalogue, Claude client (streaming), Replicate adapter, brand assets, Director prompts, project brief + scripts, $35 cap, Iron Paws seed, Quick clips (#18, #22, #23, #25, #27, #28, #30, #33, #34, #38, #39, #44, #45).
- In review: Generate wiring (#31), Enhance (#24 part 2).
- Reed's 2026-10-23 decisions are in ops/DECISIONS.md. Credits and per-video budgets follow them.
- How to run: `server/README.md`. Any server API change: run `npm run api` in web/ and commit `web/src/api/schema.d.ts`.
- Accounts: first owner via `POST /auth/setup` (needs `BS_SETUP_TOKEN`); login throttled; invites; roles owner/editor.
- Files: `POST /files` (type checked by content, size cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage interface `server/app/storage.py`.
- Brands: kit + screens with tags and `default_for` moments; fomo + Iron Paws created on setup with screens, logo and style board from `assets/brands/` (`BS_BRAND_ASSETS_DIR`; re-run `python -m app.seed <folder> [brand-slug]`).
- Libraries: `/library/{character|place|prop}?brand_id=`, multi-brand, version history + restore; reversible archive; permanent delete owner-only.
- Jobs: worker `python -m app.worker`. Providers in `app/providers`: `replicate` (polled; outputs copied to storage), `claude` (runs in the worker), `fake` (tests). Paid submits never auto-retried. Usage rows hold `cost_usd`; `GET /usage` owner-only.
- Paid generation is off unless `BS_GENERATION_ENABLED=true`: Generate/Enhance answer 503, the worker leaves paid jobs queued.
- Replicate token: `REPLICATE_API_TOKEN` if set (deployed server), else the sandbox proxy adds it. Claude key: `STUDIO_ANTHROPIC_KEY` only.
- Rules for every resource PR: `tests/helpers.py` (`assert_hidden`, `assert_no_dollars`); attached file ids via `get_file(..., kind)`; dollar fields named `*_usd` and owner-only.
- Credits: 1 credit = $0.1028 = 1 s of 480p. Catalogue prices give clip estimates, rates table the rest; real cost replaces estimates. Projects: budget = 2x planned length (editors ≤ 170 s without owner). Quick clips: 150 credits/editor/week. Over a limit = `needs_owner_approval`. Hard per-video cap 340 (= $35) for everyone, quick clips included. Limits at `/credits/limits`.
- Catalogue: `server/app/catalogue.json` (limits from Replicate schemas). `GET /models` (credits), `GET /models/prices` (owner).
- Quick clips: `POST /clips`, `POST /clips/estimate`, `GET /clips/{job}/request`; moment screens auto-attached unless in `skip_screen_ids`.
- Scripts: brief on projects; versions via paste/upload (txt/docx/pdf). Enhance: `POST .../script/enhance` (Claude via Director prompts + `check.enhance`), accept/reject, `POST .../script/apply` → new version. Enhance never changes the script's words: marks only add lines before/after a line; `notes` (problems in the words) are shown as information.
## Next
- Builder-Server: #24 next: script draft, breakdown, storyboard, clip prompts; then Quick clip "Improve prompt".
- Director's paid evals: log each paid call in ops/SPEND.md when it runs.
- Explorer: nightly checks of test and live sites (later).
## Blocked
- Replicate key for the deployed server (later). Keys stay server-side only.
