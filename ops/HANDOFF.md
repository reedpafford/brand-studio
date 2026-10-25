as of a8685b9 · 2026-10-25 02:20 UTC
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
- Also merged: payoff screen, named screens, two screens per clip, hero in frame from the first moment (#159); reference reel catalogue picked on the brief, live-action shots dropped (#153, #155); Clips refetch after a take or prompts finish, the real fix for the flaky pipeline e2e (#161); `scripts/fake_run.py` runs both done-test videos end to end on the free stand-ins (#148).
- Invite page polish: "Sign in" wording, a failed check says try again (#163); login and invite page specs updated (#164).
- fomo "Home (rich)" brand screen for the got-rich payoff (#167); montage clips use at most 3 screens (#168); step-by-step phone-friendly deploy guide for Reed in `deploy/README.md` (#166).
- Redesign docs (`docs/design/redesign/`): phase 1 structure map and top 10 changes (#170, approved by Reed), phase 2 three visual directions (#173; Reed picked B, Screening room), phase 3 Screening room design system, screen specs and a 14-PR build order (#174, `phase3/README.md`). Quick clip bar no longer covers the form; 44px phone fields (#172).
- Redesign build (14 PRs, `docs/design/redesign/phase3/README.md`): 1/14 Screening room tokens and fonts, dark by default (#175); 2/14 shared parts in `web/src/components/` (#176); 3/14 app shell with top bar, rail and phone tab bar (#178). 4/14 Videos home (#180); 6/14 video frame (#179). Screens still on the old layout until the rest land.
- Workflow v2 plan docs (#189 server plan, #191 Director plan, #192 design) and Quick clip specs (#184, #187). Planned only; nothing of workflow v2 is built yet.
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
- Progress: the first Iron Paws (peanut butter) excerpt ran and Reed approved it (confirmed by the Producer); verdict in DECISIONS.md (#125), fixes merged in #124. The fomo trading montage has run three times; run 3, after #159 and the Home (rich) screen (balance $348,920.15), cost $1.88 and is logged in ops/SPEND.md. Excerpt batch spend is $9.68 (the $8.30 plus one more montage re-run Reed approved). Per the Producer, run 3 shows the payoff balance, the hero in every shot and no speech; Reed has not signed off on video A or B yet.
## Workflow v2 (Reed's decisions, 2026-10-25, ops/DECISIONS.md)
- Owner writes a script (title, description, optional reference reel), runs Enhance, picks 0–2 variations, locks characters, optionally previews the breakdown, and publishes to the Script Library. Editors pick a version and produce it once (max 3 videos per script). Editors can write their own scripts: $15 a week free generation each, beyond that declined. No final-video upload: download clips one by one or all at once, older takes too.
## Open PRs (7, not counting the Scribe's own)
- #196 Montage check: hand and screen inserts count as the hero; never a dead end | Director | in review
- #195 Workflow v2 re-spec 2: Description, New script, Bulk create | Designer | in review (docs)
- #194 Workflow v2 re-spec 1: Script library | Designer | in review (docs)
- #193 Redesign 4b/14: Videos home follow-up (step, line, poster, sections) | Builder-Screens | in review
- #186 Redesign 7b/14: Shots step (stacked on #185) | Builder-Screens | Designer review at 920ce36: 1 must-fix (on phone and tablet the Save / Discard bar sits behind the tab bar)
- #185 Redesign 7a/14: Script step | Builder-Screens | Designer re-check passed (1e00b89)
- #183 Redesign 10/14: Quick clip | Builder-Screens | Designer re-check at 9c920fe: 1 must-fix (desktop layout from #172 not back: remove the inner scroll, make the footer sticky)
## Next
- Builder-Screens: fix #186's Save bar and #183's desktop layout; land #185, #193; then the remaining redesign PRs (clip prompt review with "Looks good" before takes are paid for comes in PR 9).
- Builder-Server / Director / Designer: workflow v2 build per #189, #191, #192 and the re-specs #194, #195; land #196.
- Producer / Reed: Reed adds the VPS secrets following `deploy/README.md` (per the Producer), then the first live deploy runs on merge to main.
- Director: further excerpt runs only with Producer approval, logged in ops/SPEND.md.
- Explorer: nightly checks of test and live sites (later).
## Blocked / needs Reed
- Replicate key for the deployed server (later). Keys stay server-side only.
- Waiting on Reed: the VPS secrets (see `deploy/README.md`), per the Producer.
- Reed's sign-off on videos A and B is the finish line.
