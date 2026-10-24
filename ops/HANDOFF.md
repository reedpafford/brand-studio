as of 410c815 · 2026-10-24 03:05 UTC
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
- Then: Approvals screen for the owner (#133), Product/Variant on brand screens (#137), credits left per stage (#138), Quick clip Improve prompt screen (#118), fomo Home screen counts for the win moment (#139); the whole video flow runs in the browser tests on free stand-ins (#151); gap-hunt fixes: script drafts, Edit brief, character photo, phone stage switch, 44px targets (#152).
- Also merged: montage rules, nobody speaks unless scripted (#135); stray control characters dropped from Claude answers (#136); real-brand-picture cut-ins over insert shots and the "Use the real image" switch (#134, #140); Approvals show who asked and dollars for the owner (#143, #147, #142); invite page says who invited you (#154, #156); byte-range file requests so phones can play videos (#144); no sideways scroll at 390 (#145); full-size peanut butter bag (#119); automatic deploy to the VPS on every merge to main (#150; skips with a warning unless the server secrets and `VPS_HOST_KEY` are set); `python -m app.seed refresh` makes manifest changes reach live databases (#149).
- Free local runs: `BS_FAKE_PROVIDERS=true` swaps in stand-in providers that never spend money; production refuses to start with it on (#128).
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
- Progress: the first Iron Paws (peanut butter) excerpt ran and Reed approved it (confirmed by the Producer); verdict in DECISIONS.md (#125), fixes merged in #124. The fomo trading montage ran twice; the re-run after #135 is logged in ops/SPEND.md ($1.96). Per the Producer: no speech and the hero in almost every shot now, but the payoff screen showed a coin price instead of the balance; the Director is proposing a fix. Excerpt spend $7.65 of the $8.30 approved (ops/SPEND.md on main).
## Open PRs (3, not counting the Scribe's own)
- #155 Brief: Adapt a reference reel | Builder-Screens | Designer re-check passed (3a393a3)
- #153 Reference reels: a catalogue to adapt from, picked on the brief | Builder-Server | QA at 6c5d137: 1 must-fix (live-action shots not removed from a reel picked by `reference_id`: `RefShot` has no `style`); head since moved to 11f2ec3
- #148 scripts/fake_run.py: both done-test videos end to end on the stand-ins | Builder-Server | QA passed at d38d388 before #135 merged; per the Producer it breaks under #135's checks and is back with Builder-Server; head now c1ead03
## Next
- Builder-Server: fix #153's `RefShot` style field and test; make #148 pass under #135's checks.
- Builder-Screens: land #155 once #153 is in.
- Director: fix the fomo payoff screen (balance, not a coin price) and re-run the excerpt; paid runs only with Producer approval, logged in ops/SPEND.md.
- Release: first live deploy needs Reed's server secrets (not tracked on GitHub).
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
- Reed's sign-off on videos A and B is the finish line.
