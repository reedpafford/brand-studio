as of 71bf8e2 · 2026-10-23 22:41 UTC
# Handoff (rewritten each refresh by the Scribe; under 80 lines)
## Built (on main)
- Foundation: server, accounts, files, brands, libraries, jobs/worker/usage, credits (#2–#8).
- Screens: design system, web scaffold, shell, brand kit, library, toasts, phone tab bar (#11–#17, #20, #21, #26, #29).
- Generation: catalogue, Replicate adapter, Claude client + streaming (#18, #22, #23, #44); Nano Banana rules (#56); per-video cap (#38, #45).
- Quick clip: create/estimate/retry (#33), Generate on (#31), references (#55, #72), Improve prompt + Seedance shape B (#67).
- Projects: list, brief, Script tab, workspace (#57, #60, #68); script drafts (#62); Script Enhance with tags, keys, Accept all (#51, #63, #74, #77, #81).
- Breakdown pane: make, redo, problems, scenes/clips/shots (#83, with browser test #86); edit, Split/Join, Save, Go to (#85); line links to the script and phone sheets (#90). Breakdown server (#66; `JobOut.step` tells Enhance from Breakdown runs, #84; tagged directions read by #75). Storyboard prompts (#78) and stills with Nano Banana (#82); stale frames are refused (#88). Project clip prompts (#87); frames can be approved and redone with a note (#97).
- Storyboard pane: frames, stills, Approve, Redo with a note, Next: Clips gate (#92, #99). Project clips: takes with Seedance, pick/approve, free stitched video (#94). Flaky dollar-amount test fixed (#102).
- Director prompts/evals (#30, #36, #41, #54, #75); Iron Paws + fomo seeds (#27, #39); browser tests (#19, #86, #49, #52, #61, #65, #71, #73, #76).
- Design specs: Breakdown, Storyboard, Clips, Approvals (#79, #80); Prompting guides and FIT rows (#53, #70); house style and gold references from @nateassets (#96).
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
- Clip takes and the stitched video: routes in `server/app/routes/` from #94 (generate, pick, approve, video); see its tests in `server/tests/test_clip_takes.py`.
- Storyboard: `POST/GET /projects/{id}/storyboard`, `PUT .../frames/{id}`, `POST .../frames/{id}/render` (paid, refused while frame has problems).
## Open PRs (4, not counting the Scribe's own)
- #104 Clips pane: takes, pick, approve, make the video, download | Builder-Screens | in review (its base #99 and #94 are merged)
- #103 Specs: brief product picker, no length note; end line is the last clip | Designer | in review (docs only)
- #101 ops: Definition of done in MISSION.md; $75 per-video cap, flavour and live-action decisions; remove old gold examples and fomo style board | Producer | in review
- #98 House style in the prompts: new fomo worked examples, style lines, pacing | Director | in review (its base #96 is merged)
## Next
- Builder-Screens: land #104 (Clips pane, the last stage).
- Builder-Server: per #101/#103, once merged: $75 cap, products on the brand kit and `product` on the project, brand end line.
- Director: #98 house style; paid evals only with Producer approval, logged in ops/SPEND.md.
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
- #101 changes the per-video cap from $35 to $75 and adds the Definition of done to MISSION.md; the cap rule above stays $35 on main until it merges.
