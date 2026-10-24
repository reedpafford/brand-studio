as of 1691d19 · 2026-10-24 00:14 UTC
# Handoff (rewritten each refresh by the Scribe; under 80 lines)
## Built (on main)
- Foundation: server, accounts, files, brands, libraries, jobs/worker/usage, credits (#2–#8).
- Screens: design system, web scaffold, shell, brand kit, library, toasts, phone tab bar (#11–#17, #20, #21, #26, #29).
- Generation: catalogue, Replicate adapter, Claude client + streaming (#18, #22, #23, #44); Nano Banana rules (#56); per-video cap (#38, #45).
- Quick clip: create/estimate/retry (#33), Generate on (#31), references (#55, #72), Improve prompt + Seedance shape B (#67).
- Projects: list, brief, Script tab, workspace (#57, #60, #68); script drafts (#62); Script Enhance with tags, keys, Accept all (#51, #63, #74, #77, #81).
- Breakdown pane: make, redo, problems, scenes/clips/shots (#83, with browser test #86); edit, Split/Join, Save, Go to (#85); line links to the script and phone sheets (#90). Breakdown server (#66; `JobOut.step` tells Enhance from Breakdown runs, #84; tagged directions read by #75). Storyboard prompts (#78) and stills with Nano Banana (#82); stale frames are refused (#88). Project clip prompts (#87); frames can be approved and redone with a note (#97).
- Storyboard pane: frames, stills, Approve, Redo with a note, Next: Clips gate (#92, #99). Project clips: takes with Seedance, pick/approve, free stitched video (#94). Flaky dollar-amount test fixed (#102). Old gold examples and fomo style board removed, Iron Paws peanut butter bag added (#101); Library spec for Make sheet and photo → sheet → approve (#106, #111). Brief and end-line specs (#103). House style in the prompts (#98), live action becomes the brand CTA with definition-of-done eval cases (#107), character sheet and place still prompts (#108).
- Clips pane: takes, pick, approve, make the video, download (#104); server support: clip on jobs, Redo note, take cost, un-approve (#113). The path brief → script → breakdown → storyboard → clips → video exists end to end.
- Since then: Iron Paws flavour picker on the brief (#114) and product variants + brand end line (#110); cap 729 credits ($75), no editor length limit (#109); house-style character sheets and place stills with owner approval and "Waiting for Reed" (#116, #122, #130), warnings when a cast member has no approved sheet (#129); credits left per stage (#126); storyboard frames work around what the image model refuses (#121); Quick clip Improve prompt (server, #117); PB excerpt fixes (#124); Docker Compose deploy stack for the VPS (#112); specs for sheets, "Use the real image" and prices (#123, #127, #132).
- Director prompts/evals (#30, #36, #41, #54, #75); Iron Paws + fomo seeds (#27, #39); browser tests (#19, #86, #49, #52, #61, #65, #71, #73, #76).
- Design specs: Breakdown, Storyboard, Clips, Approvals (#79, #80); Prompting guides and FIT rows (#53, #70); house style and gold references from @nateassets (#96).
- How to run: `server/README.md`. After any server API change run `npm run api` in web/ and commit `web/src/api/schema.d.ts`.
- Accounts: first owner `POST /auth/setup` (needs `BS_SETUP_TOKEN`); roles owner/editor; invites; login throttled.
- Files: `POST /files` (type by content, cap `BS_MAX_UPLOAD_MB`), `GET /files/{id}`; storage `server/app/storage.py`.
- Brands/libraries: kit, screens (tags, `default_for` moments); fomo + Iron Paws seeded from `assets/brands/` (`BS_BRAND_ASSETS_DIR`; `python -m app.seed <folder> [slug]`). `/library/{character|place|prop}?brand_id=`: versions, restore, reversible archive, owner-only delete.
- Jobs: worker `python -m app.worker`; providers `replicate`, `claude`, `fake` (tests). Paid submits never auto-retried. `GET /usage` owner-only.
- Paid generation off unless `BS_GENERATION_ENABLED=true` (Generate/Enhance/Make answer 503). Replicate: `REPLICATE_API_TOKEN` or sandbox proxy. Claude: `STUDIO_ANTHROPIC_KEY` only.
- Rules for resource PRs: `tests/helpers.py` (`assert_hidden`, `assert_no_dollars`); `get_file(..., kind)`; dollar fields `*_usd`, owner-only.
- Credits: 1 credit = $0.1028. Project budget = 2x planned length. Quick clips 150 credits/editor/week. Hard per-video cap 729 credits ($75) for everyone, no editor length limit (#109). Over a limit = `needs_owner_approval`. `/credits/limits`.
- Catalogue `server/app/catalogue.json`; `GET /models`, `GET /models/prices` (owner).
- Quick clips: `POST /clips`, `/clips/estimate`, `GET /clips/{job}/request`.
- Scripts: versions by paste/upload; Enhance `POST .../script/enhance`, accept/reject, `.../script/apply`; drafts `.../script/draft`. Script words never change; marks only add direction lines.
- Breakdown: `POST/GET/PUT /projects/{id}/breakdown` (`stale` flag, problems saved).
- Project clips: `POST /projects/{id}/clips/prompts` (Claude writes one Seedance prompt + references per clip of the newest breakdown; replaces old clips), `GET /projects/{id}/clips` (problems, `stale`), `PUT .../clips/{id}` edit.
- Clip takes and video (`server/app/routes/project_clips.py`): `POST .../clips/{id}/takes/{take}/pick`, `POST .../clips/{id}/approve`, `POST/GET .../video` (free stitch once every clip is approved); a take is started by the generate route (paid).
- Storyboard: `POST/GET /projects/{id}/storyboard`, `PUT .../frames/{id}`, `POST .../frames/{id}/render` (paid, refused while frame has problems).
## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, same story and dialogue word for word, fomo logo and UI right (numbers free), live-action tag replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag (project picks the flavour).
- Tuning uses 15–30 s excerpts at 480p inside the $15/week test cap, with an estimate first.
- Progress: the first Iron Paws (peanut butter) excerpt ran and Reed approved it (confirmed by the Producer); his verdict is in DECISIONS.md (#125: main text on the bag must read right, small print may be garbled) and the fixes (dry eyes on the healed beat, pitbull drift) merged in #124. The fomo trading montage ran once ($1.87 per the Producer); Reed's notes are in DECISIONS.md and #131 (hero in every shot, creative wealth beats, logo/UI right, numbers free). It re-runs after #135 merges. Excerpt spend $5.54 of the $8.30 approved, logged in ops/SPEND.md on #119 (not on main yet).
## Open PRs (13, not counting the Scribe's own)
- #118 Quick clip: Improve prompt (screen) | Builder-Screens | in review (its server half #117 is merged)
- #119 Iron Paws: full-size peanut butter bag (scoop removed) + spend log | Producer | in review; head since moved to 11e9955
- #128 Local runs: BS_FAKE_PROVIDERS switch for free stand-ins | Builder-Server | QA passed (91cf778; production now refuses the flag)
- #133 Approvals: the owner's screen for held projects and jobs | Builder-Screens | Designer re-check passed (291b0a2); QA not seen
- #134 Cut-ins: real brand picture over insert shots when the video is made | Builder-Server | in review
- #135 Nobody speaks unless scripted; montages: hero in every shot, wealth payoffs | Director | QA at 56c569e: 1 must-fix (`test_improve_then_generate_as_is` expects the old "shown exactly" wording); head since moved to 9e60170
- #136 Claude answers: drop stray control characters before saving | Builder-Server | in review
- #137 Brand screens: Product and Variant, Edit a screen | Builder-Screens | Designer: 2 must-fixes (Done discards edits, Delete 19 px on phones); head since moved to 6ade551
- #138 Project: credits left per stage under the budget meter | Builder-Screens | Designer: 1 must-fix (opening the list pushes the page down); head since moved to a43d9c4
- #139 fomo: Home screen also counts for the win moment | Producer | in review
- #140 Clips: "Use the real image" switch per insert | Builder-Screens | in review
- #142 Approvals spec: planned length no longer waits for Reed | Designer | in review
- #143 Approvals: who asked, and a job's cost in dollars for the owner | Builder-Server | in review
- #144 Files: answer byte-range requests so phones can play videos | Builder-Server | in review
## Next
- Builder-Screens: Designer fixes on #137, #138; land #133, #118, #140.
- Builder-Server: #134 cut-ins; #136; #143 and #144.
- Director: fix #135's test, then re-run the fomo excerpt; paid runs only with Producer approval, logged in ops/SPEND.md.
- Release: the deploy stack is merged (#112); the live deploy is not tracked on GitHub yet.
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
- Reed's sign-off on videos A and B is the finish line.
