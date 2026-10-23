as of 9659dd8 · 2026-10-23 22:25 UTC
# Handoff (rewritten each refresh by the Scribe; under 80 lines)
## Built (on main)
- Foundation: server, accounts, files, brands, libraries, jobs/worker/usage, credits (#2–#8).
- Screens: design system, web scaffold, shell, brand kit, library, toasts, phone tab bar (#11–#17, #20, #21, #26, #29).
- Generation: catalogue, Replicate adapter, Claude client + streaming (#18, #22, #23, #44); Nano Banana rules (#56); per-video cap (#38, #45).
- Quick clip: create/estimate/retry (#33), Generate on (#31), references (#55, #72), Improve prompt + Seedance shape B (#67).
- Projects: list, brief, Script tab, workspace (#57, #60, #68); script drafts (#62); Script Enhance with tags, keys, Accept all (#51, #63, #74, #77, #81).
- Breakdown pane: make, redo, problems, scenes/clips/shots (#83, with browser test #86). Breakdown server (#66; `JobOut.step` tells Enhance from Breakdown runs, #84; tagged directions read by #75). Storyboard prompts (#78) and stills with Nano Banana (#82); stale frames are refused (#88). Project clip prompts (#87).
- Director prompts/evals (#30, #36, #41, #54, #75); Iron Paws + fomo seeds (#27, #39); browser tests (#19, #86, #49, #52, #61, #65, #71, #73, #76).
- Design specs: Breakdown, Storyboard, Clips, Approvals (#79, #80); Prompting guides and FIT rows (#53, #70).
- How to run: `server/README.md`. After any server API change run `npm run api` in web/ and commit `web/src/api/schema.d.ts`.
- Accounts: first owner `POST /auth/setup` (needs `BS_SETUP_TOKEN`); roles owner/editor; invites; login throttled.
- Files: `POST /files` (type by content, cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage `server/app/storage.py`.
- Brands/libraries: kit, screens (tags, `default_for` moments); fomo + Iron Paws seeded from `assets/brands/` (`BS_BRAND_ASSETS_DIR`; `python -m app.seed <folder> [slug]`). `/library/{character|place|prop}?brand_id=`: versions, restore, reversible archive, owner-only delete.
- Jobs: worker `python -m app.worker`; providers `replicate`, `claude`, `fake` (tests). Paid submits never auto-retried. `GET /usage` owner-only.
- Paid generation off unless `BS_GENERATION_ENABLED=true` (Generate/Enhance/Make answer 503). Replicate: `REPLICATE_API_TOKEN` or sandbox proxy. Claude: `STUDIO_ANTHROPIC_KEY` only.
- Rules for resource PRs: `tests/helpers.py` (`assert_hidden`, `assert_no_dollars`); `get_file(..., kind)`; dollar fields `*_usd`, owner-only.
- Credits: 1 credit = $0.1028. Project budget = 2x planned length (editors ≤ 170 s without owner). Quick clips 150 credits/editor/week. Hard per-video cap 340 credits ($35). Over a limit = `needs_owner_approval`. `/credits/limits`.
- Catalogue `server/app/catalogue.json`; `GET /models`, `GET /models/prices` (owner).
- Quick clips: `POST /clips`, `/clips/estimate`, `GET /clips/{job}/request`.
- Scripts: versions by paste/upload; Enhance `POST .../script/enhance`, accept/reject, `.../script/apply`; drafts `.../script/draft`. Script words never change; marks only add direction lines.
- Breakdown: `POST/GET/PUT /projects/{id}/breakdown` (`stale` flag, problems saved).
- Project clips: `POST /projects/{id}/clips/prompts` (Claude writes one Seedance prompt + references per clip of the newest breakdown; replaces old clips), `GET /projects/{id}/clips` (problems, `stale`), `PUT .../clips/{id}` edit.
- Storyboard: `POST/GET /projects/{id}/storyboard`, `PUT .../frames/{id}`, `POST .../frames/{id}/render` (paid, refused while frame has problems).
## Open PRs (6, not counting the Scribe's own)
- #85 Breakdown edit/Split/Join (2/3) | Builder-Screens | 44px tap-target fix and `JobOut.step` pushed; waiting on Designer/QA re-check
- #90 Breakdown line links + phone sheets (3/3) | Builder-Screens | stacked on #85; QA passed (88f545f); Designer: 1 must-fix (44px phone tap targets)
- #92 Storyboard pane: frames and stills (1/2) | Builder-Screens | QA passed (fcb82e3); Designer: 1 must-fix (Storyboard opens past the breakdown gate); head since moved to d7f1934
- #94 Project clips: takes with Seedance, pick/approve, stitched video | Builder-Server | QA at 8ad56b1: 3 must-fixes (stale clips can be generated, reference with no picture gives a 500, no test of the money rules)
- #97 Storyboard: approve frames on the server, Redo note, frame_id on jobs | Builder-Server | in review
- #96 House style + gold references from @nateassets' reels | Reference Analyst | in review
## Next
- Builder-Screens: finish #85/#90 tap targets; fix #92's Storyboard gate; Storyboard 2/2 after #92.
- Builder-Server: fix #94's three must-fixes before its first real take; then the next clip steps.
- Director: paid evals only with Producer approval; log each paid call in ops/SPEND.md.
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
