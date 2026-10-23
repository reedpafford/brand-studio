as of 184361f · 2026-10-23 22:58 UTC
# Handoff (rewritten each refresh by the Scribe; under 80 lines)
## Built (on main)
- Foundation: server, accounts, files, brands, libraries, jobs/worker/usage, credits (#2–#8).
- Screens: design system, web scaffold, shell, brand kit, library, toasts, phone tab bar (#11–#17, #20, #21, #26, #29).
- Generation: catalogue, Replicate adapter, Claude client + streaming (#18, #22, #23, #44); Nano Banana rules (#56); per-video cap (#38, #45).
- Quick clip: create/estimate/retry (#33), Generate on (#31), references (#55, #72), Improve prompt + Seedance shape B (#67).
- Projects: list, brief, Script tab, workspace (#57, #60, #68); script drafts (#62); Script Enhance with tags, keys, Accept all (#51, #63, #74, #77, #81).
- Breakdown pane: make, redo, problems, scenes/clips/shots (#83, with browser test #86); edit, Split/Join, Save, Go to (#85); line links to the script and phone sheets (#90). Breakdown server (#66; `JobOut.step` tells Enhance from Breakdown runs, #84; tagged directions read by #75). Storyboard prompts (#78) and stills with Nano Banana (#82); stale frames are refused (#88). Project clip prompts (#87); frames can be approved and redone with a note (#97).
- Storyboard pane: frames, stills, Approve, Redo with a note, Next: Clips gate (#92, #99). Project clips: takes with Seedance, pick/approve, free stitched video (#94). Flaky dollar-amount test fixed (#102). Old gold examples and fomo style board removed, Iron Paws peanut butter bag added (#101); Library spec for Make sheet (#106).
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
- Clip takes and video (`server/app/routes/project_clips.py`): `POST .../clips/{id}/takes/{take}/pick`, `POST .../clips/{id}/approve`, `POST/GET .../video` (free stitch once every clip is approved); a take is started by the generate route (paid).
- Storyboard: `POST/GET /projects/{id}/storyboard`, `PUT .../frames/{id}`, `POST .../frames/{id}/render` (paid, refused while frame has problems).
## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, same story and dialogue word for word, fomo screens exact, live-action tag replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag exactly (project picks the flavour).
- Tuning uses 15–30 s excerpts at 480p inside the $15/week test cap, with an estimate first.
## Open PRs (6, not counting the Scribe's own)
- #104 Clips pane: takes, pick, approve, make the video, download | Builder-Screens | Designer re-check passed (89c9875); QA passed at d7fd538, head since moved to 89c9875
- #109 Credits: per-video cap 729 credits ($75), no editor length limit | Builder-Server | in review
- #107 Reference reels: live action becomes the brand CTA; definition-of-done eval cases | Director | QA pass at 062a17f; contains #98; `end_line` not wired to the Brand model yet
- #108 Character sheet and place still prompts (Nano Banana) | Director | QA pass at 178dffd; stacked on #107
- #103 Specs: brief product picker, no length note; end line is the last clip | Designer | in review (docs only)
- #98 House style in the prompts: new fomo worked examples, style lines, pacing | Director | QA re-check passed at b5e9c7d
## Next
- Builder-Screens: land #104 (Clips pane, the last stage).
- Builder-Server: #109, then products on the brand kit and `product` on the project, and the brand end line (per #103, #107).
- Director: land #98, #107, #108; paid evals only with Producer approval, logged in ops/SPEND.md.
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
- Reed's sign-off on videos A and B is the finish line.
