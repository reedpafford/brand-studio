# Brand Studio Next: data changes

What each spec item adds or changes in the database, and how migrations are numbered so the builders, and main, never collide. Flows are in [flows.md](flows.md). Owner: Next-Lead. A builder adding a table or column not listed here asks Next-Lead first; Next-Lead updates this file in the same PR.

## Migration rules

- **Next's migrations are named `n01`, `n02`, …** (file `n01_song_scripts.py`, `revision = "n01"`), so they never take a number main uses (main is at 0053 and still counting).
- **One builder holds the next number at a time.** Claim it in the table below (in your PR, or by asking Next-Lead) before writing the migration. Two open PRs never share a number.
- **When main merges into `next` with a new migration**, alembic sees two heads (e.g. 0054 and n01). Next-Lead does every such merge as its own PR: branch from `next`, merge `main`, add an empty merge migration (`alembic merge heads`, the next `nNN`, `down_revision = ("0054", "nNN")`), run `test_migrations`, and say in the PR which heads it joins. The Producer tells Next-Lead before merging main into `next` when main has a migration `next` doesn't.
- **Two heads can't deploy:** `test_migrations` upgrades to "head", which fails with two heads, so CI goes red and deploy-next never runs. On the server, `migrate` would also refuse, and the api waits on it, so a half-migrated test site can't start.
- Every migration has a downgrade and keeps old rows valid (new columns have defaults). JSON fields inside an existing JSON column (like breakdown shots) need no migration, but are listed here so everyone reads them the same way.
- The test site's database is a copy of nothing: it can be wiped and re-seeded (`docker volume rm brand-studio-next_db`) if a migration goes wrong there. Live is never touched.

## Claimed numbers

| Number | What | Who | PR |
|---|---|---|---|
| n01 | Song ads: `scripts.kind`, `script_drafts.style_line`, `script_drafts.song_directions`, `script_drafts.singer`, `script_drafts.spoken_end_line`, `song_takes`, `projects.song_take_id` | Next-Server | #748 |
| n02 | Song ads: `project_clips.song_slice`, `final_videos.song_take_id` | Next-Server (with the breakdown work) | #829 |
| n03 | Flavour from the script: `script_drafts.flavours` JSON `{product: variant}` (default `{}`), copied to the video at Make this version (the video's own pick stays where it is today; a pick sent with Make this version wins) | Next-Server | #968 |
| n04 | Song-ad study (S3a): `script_drafts.song_study` JSON, default null | Builder-Server-7 | — |
| n05 | Narrated (N1, V6n): `song_takes.kind`, `voice`, `music_file_id`, `music_job_id`, `trimmed`; `scripts.kind` gains `narrated` (validation only) | Next-Server | — |
| n06 | Every video (1b): `projects.plan`, `projects.plan_history`, `script_drafts.plan`, `jobs.retry_of_id`, `jobs.auto`, `project_clips.auto_fix`, new `item_checks`; existing videos are planned from their breakdown in code, when read | Builder-Server-8 | — |
| n07 | Format and Look step 1: `scripts.look`, `projects.look` (text, default `house`), new `look_switches` {workspace_id, look_id, on, sample_still_id, sample_clip_id, switched_by_id, switched_at} | Next-Server | — |
| n08 | Brand setup (BR1): new `brands` columns and product description/claim, below | Builder-Server-7 | #910 |
| n09 | Video settings (VS1): `projects.video_model`, `projects.image_model`, `projects.sung_flipped`, `storyboard_frames.made_with`, `clip_takes.made_with`, `scripts.language`, below | Builder-Server-7 | #925 |
| n10 | Per-look sheets (ST2): `library_items.look_sheets`, `library_items.sheet_look`, `projects.look_copies`, below | Next-Server | #930 |
| n11 | Projects (OR1): new `folders`, `folder_id` on `scripts`, `projects` and `jobs`, below | Next-Server | #946 |
| n12 | A role's own look per look: `projects.own_looks` JSON `{slot_id: {look: item_id}}`, so switching back to a look reuses its own look (ST2) | Next-Server | #979 |
| n13 | Preferred and going back (OR3): `projects.storyboard_history`, `project_clips.prompt_history`, below | Builder-Server-8 | #957 |
| n14 | Languages (LG1): new `language_switches` {workspace_id, language_id, on, sample, switched_by_id, switched_at}, one per workspace and language | Switch-On | #972 |
| n15 | Song in any look: no new column. Rows on look `song` (`scripts`, `projects`, `brands.default_look`) move to their brand's default look, else `house`; `look_switches` rows for `song` are deleted. Song is the script's `kind` (its Format), never a look. Downgrade is a no-op (which rows were on Song isn't kept) | Next-Server | #1031 |
| n16 | One editor allowance (Reed, 30 Oct; DECISIONS rule 5): no new column. Workspace limits still on the old default (145 or 150 credits) move to 97 ($10); a custom figure stays. The allowance counts Quick clips only (a video or image job outside any video, with no step) | Next-Server | #1053 |
| n17 | Screen figures (#1057's `Shot.screen_figure`): `brand_screens.figure_spot` JSON, nullable, no default (null = the screen is never drawn on): `{box [x0,y0,x1,y1], at [x,y], size px, chart [x0,y0,x1,y1] optional}`. Sets the spots for fomo's Home (rich), Token chart up and Token chart down | Next-Server | #1059 |
| n18 | Locks and per-video outfits (director-chat.md §1): `projects.locks` JSON not null default `{}` (the choices fixed for the director: cast, look, length, song, end_line as true; screens as a list of ids) and `projects.outfits` JSON not null default `{}` (this video's outfit per character, keyed `char:<id>`, ≤200 chars; empty = the sheet's outfit). Downgrade drops both | Next-Server | #1104 |
| n20 | Freestyle (Reed's v4): new `freestyles` {workspace_id, created_by_id, title, type, look, shape, brand_id (nullable), chat JSON default `[]` (the thread), stopped_at}, indexed by workspace | Next-Server | #1159 |
| n19 | The director's chat (director-chat.md §1 item 4): `projects.director_chat` JSON not null default `[]`, each `{by, text, at, run}` | Next-Server | #1155 |
| n21 | Hidden rows (Freestyle 3a): `hidden` bool default false on `projects`, `scripts` and `brands` (a freestyle's own script, video and the workspace's "Freestyle" brand; app/hidden.py leaves them out of every list); `freestyles.project_id` (FK projects, nullable) and `freestyles.up_to` (numeric, the price the owner approved) | Next-Server | #1171 |
| n22 | More than one video from a version (the Producer on P1): drops the unique `uq_projects_script_draft_id` on `projects`, so "Make another" makes a new video from the same frozen version | Next-Server | #1190 |
| n23 | A final cut taken off Media (v5 G boards): `final_videos.off_media_at`, nullable. The owner's Delete on a Media item keeps the video's own copy and only marks the cut off Media. Downgrade drops it | Next-Server | #1212 |
| n24 | Last active (v5 audit, Team): `users.last_active_at`, nullable, no default (null: not seen since it shipped); kept to within 5 minutes by `auth.current_user`. Downgrade drops it | Next-Server | #1247 |
| n25 | Forecast and score (app/scorecard.py): four nullable columns on `projects` for what Make forecast and the owner's 1–5 score and note. Downgrade drops them | Spend-metrics | #1258 |
| n26 | A script's format (stream D): `scripts.format`, nullable text, a guides format id (null: the format its `kind` stands for); `scripts.kind` is always that format's engine. `freestyles.type` widens to 40 characters and now holds a format id (or `one_clip`). Downgrade drops the column and narrows the type | Format-picker | — |
| n28 | No per-video cap (Reed, 2026-11-03: "Just remove the cap entirely"): drops `credit_limits.per_video_max_credits` and `song_takes.trim_to` ("Use the first 0:55", which only existed to fit a song video under the cap). A take that was trimmed is used whole. Downgrade adds both back (the cap at 729, trims empty) | No-video-cap | — |
| n29 | Media for v5 (C_Media): new `media_uploads` {workspace_id, brand_id, created_by_id, file_id, seconds (null for a picture), removed_at}, a picture or clip added to a brand's Media, checked by its contents; `final_videos.seconds` (nullable, no default: kept when a cut is made, an older one's read once). Downgrade drops both | Next-Server | #1267 |
| n30 | Folders inside folders (v6 S0-01): `folders.parent_id`, nullable FK to `folders` (null: at the top). Downgrade drops it | v6-folders | — |
| n31 | A hosted video's B-roll look (v6 S-gaps-01, option 1): `projects.broll_look`, nullable text (null: the style's own). Its stills, takes, B-roll model and the briefed steps' shots use it; the host, voice and cast keep `projects.look`. Downgrade drops it | v6-newvideo | — |
| n32 | New video's picks (v6): `projects.attachments`, JSON list of file ids not null default `[]`, pictures or clips attached for this video only, never added to the brand (rule 12; S-gaps-01, option 3), listed in the director's context; and `projects.reel_script_id`, nullable FK to `scripts`, the reel it was adapted from (Use a reel, S2-07). Downgrade drops both | v6-newvideo | — |
| n33 | Voices (v6 S8-04): new `voices` {workspace_id, brand_id (null: a style's voice), look, name, kind cloned/described, provider, provider_voice_id, speech_model, description, sample_file_id, preview_file_id, job_id, cloned_at, last_used_at, lost_at, created_by_id, archived_at}; `library_items.voice_id` (nullable FK to `voices`) and `library_items.voice_stock_key` (String(60), an app voice's key), one or neither (S8-03). No data step: a style's voice (Dr. Pickle's clone) is added to a workspace the first time its voices are read (app/voices.py). Downgrade drops both | v6-models | — |
| n34 | Who has watched which take (v6 piece C, S3-09): new table `take_seen` {take_id (FK clip_takes, indexed), user_id (FK users), created_at}, unique per take and person. A clip the director changed stays outlined for a person until they've watched its new take. Downgrade drops the table. **Renumber at merge** if another n34 lands first | v6-progress | — |
| n35 | The v6 library (S8, S-gaps-05): `library_items.archived_at` (set on archive, cleared on Undo; items archived before it have none), `created_by_id` FK users, `presenter` bool false (a face and a voice; how they appear is each video's pick), `place_id` FK `library_items` (a character's usual place), `product_type` String(10) null ("app" or "physical"; existing products are physical); `brand_screens.product_id` FK `library_items` replaces the free-text `brand_screens.product`: each brand's product word is matched to its library product by name (any case), a word with no product makes one in that brand, and a screen with no product word goes to the brand's app product ("<brand> app", made once). Downgrade writes physical products' names back | v6-library | — |
| n36 | A short Brand kit (S-gaps-05 L1, Reed 4 Nov): drops `brands.end_line`, `cta_lines`, `never_say`, `do_list`, `dont_list`, `legal_line`, `audience`, `fonts`, `style_board_file_id`, `end_card_file_id`, `music_style`, `default_language`, `default_look`, `default_cast`; a brand keeps name, logo, colours and `tone_notes` ("Tone and rules"). Videos' `end_line` lock is taken out of `projects.locks` (rule 18: the ending comes from the script). Downgrade adds the columns back empty | v6-library | — |
| n37 | The director's questions and money OKs (v6 piece B, S4-01 to S4-04): new `asks` {workspace_id, project_id, run (the director run that asked), kind (cast, presenter, voice, place, product, brand_item, story, question, start, budget, own, plan), topic, subject, question, why, describe, choices JSON `[]`, pick, decide_at, state (open, uploading, answered, not_needed), answer JSON, answered_by_id, answered_at, rounds JSON `[]` (Generate options' jobs), job_ids JSON `[]` (a money card's held jobs), closed}. Downgrade drops it | v6-ask | — |
| n38 | The model each clip is made with, who switched a video's settings, how its presenter appears, its Omni voice and narrator (v6 F, S-gaps-05 V1, Reed's L3 and 4 Nov answers): `project_clips.model` (JSON, nullable: `{id, why, by, speaks}`, the director's model for that clip; null: the video's); `projects.settings_log` (JSON list, default []: `{field, was, now, by, by_id, why, at}` per switch; a person's own choice wins over the director's); `projects.presenter` (String(20), nullable: talks, corner or acts; null: the style's start); `projects.omni_voice` (String(300), nullable: the talker's voice described to Omni, the same in every clip); `projects.narration_only` (Boolean, nullable); `projects.voice` (String(60), nullable: "stock:<key>" or "voice:<id>", a person's narrator for this video); `host_pieces.how` (String(20), nullable: the way of appearing a host take was made for). Downgrade drops them | v6-models | — |
| n39 | The director's watch of each take and host piece (rule 11): `clip_takes.watch` and `host_pieces.watch`, nullable JSON: what it found looking at it and what it did (kept, remade, waiting for the owner's OK or flagged), with the remake's "up to". Downgrade drops it | v6-watch | — |
| n40 | A narrated video keeps its narration throughout (Reed, 5 Nov): drops `projects.omni_voice` and `projects.narration_only` (no talker speaks on Omni in it). Downgrade adds them back, empty | v6-models | — |
| n41 | Approve cast & places (Reed, 4 Nov, S-gaps-07): `projects.cast_ok`, nullable JSON, what the person making the video approved, each character and place as its stills and takes are made with (`{"items": {ref: {sig, item, version, file}}, "by", "at", "asked"}`, app/cast_gate.py); a still or take that shows something new or changed waits for it. Data step: every drawn look made for one video is marked usable (its video's OK covers it, no per-card approval); downgrade drops the column and leaves those | v6-castgate | — |
| n42 | The cut editor (v6 S7): `final_videos.number` (Cut 1, Cut 2, … within a video; existing cuts numbered in the order made), `final_videos.edit_ids` (JSON list, default `[]`: the edits it was made with) and `final_videos.timeline` (JSON, nullable: where each piece sat); new `cut_edits` {project_id, by_id, director, kind (trim, retime, split, swap, presenter, music), data JSON, said, at, undone_at}, replayed in order over the picked takes (app/cut.py). Downgrade drops them | v6-cut | — |

## Merge order (the chain on `next`)

Numbers are names, not an order. A PR waiting its turn points its `down_revision` at next's current head so its CI runs (CI tests it merged with next), and moves to its real parent just before it merges; the Producer checks for one head before every merge. Each migration's `down_revision` is the head on `next` when it merges, so the chain stays one line. When one merges, Next-Lead tells the next owner to set their `down_revision` to it.

| Turn | Migration | PR | `down_revision` | State |
|---|---|---|---|---|
| — | n01 | #748 | 0053 | On `next` |
| 1 | n02 | #829 | n01 | On `next` |
| 2 | n04 | #851 | n02 | On `next` |
| 3 | n06 | #862 | n04 | On `next` |
| 4 | n07 | #873 | n06 | On `next` (merged before n05) |
| 5 | n05 | #858 | n07 | On `next` (ade1a9f1) |
| 6 | n08 | #910 | n05 | On `next` (c098abd9) |
| 7 | n09 | #925 | n08 | On `next` |
| 8 | n10 | #930 | n09 | On `next` |
| 9 | n11 | #946 | n10 | On `next` |
| 10 | n13 | #957 | n11 | On `next` (20d1df59) |
| 11 | n03 | #968 | n13 | On `next` (e1517285) |
| 12 | n12 | #979 | n03 | On `next` (d76cdfd6) |
| 13 | n14 | #972 | n12 | On `next` (dfc43b33) |
| 14 | n15 | #1031 | n14 | On `next` (9f72273b) |
| 15 | n16 | #1053 | n15 | On `next` |
| 16 | n17 | #1059 | n16 | On `next` (08d2dce5) |
| 17 | n18 | #1104 | n17 | On `next` |
| 18 | n20 | #1159 | n18 | On `next` (ce0fe386) |
| 19 | n19 | #1155 | n20 | On `next` (28f3e729) |
| 20 | n21 | #1171 | n19 | On `next` (ae65863f) |
| 21 | n22 | #1190 | n21 | On `next` (331bc51f) |
| 22 | n23 | #1212 | n22 | On `next` (dc0753e7) |
| 23 | n24 | #1247 | n23 | On `next` (6bef3c48) |
| 24 | n25 | #1258 | n24 | On `next` (a8e8b9d2) |
| 25 | n26 | — | n25 | On its PR |
| 26 | n28 | — | n27 | On its PR |
| 27 | n29 | #1267 | n28 | On `next` (19be9833) |
| 28 | n30 | #1296 | n29 | On `next` |
| 29 | n31 | #1298 | n30 | On `next` |
| 30 | n32 | — | n31 | On `next` |
| 31 | n33 | #1314 | n32 | On `next` |
| 32 | n34 | #1306 | n33 | On `next` |
| 33 | n35 | #1326 | n34 | On `next` |
| 34 | n36 | #1334 | n35 | On `next` |
| 35 | n37 | #1313 | n36 | On `next` |
| 36 | n38 | #1327 | n37 | On `next` |
| 37 | n39 | #1308 | n38 | On `next` |
| 38 | n40 | #1346 | n39 | On `next` |
| 39 | n41 | #1331 | n40 | On `next` |
| 40 | n42 | #1299 | n41 | On its PR |

## 1. Song ads

| Where | Change | Notes |
|---|---|---|
| `scripts` | `kind` text: the **Format**. `story` (shown as **Dialogue**), `song` or `narrated`, default `story` | Set at New script (S1). Dialogue ↔ Narrated can change before publishing (ST0); Song never changes. `narrated` needs no migration (text). Since n26 it is the engine of the script's `format` (a guides format id), set whenever the format is. |
| `script_drafts` (a version) | The lyrics are the version's `text`, as a story's words are. Add `style_line` text (default ""), `song_directions` JSON list (default [], each `{concept, lyrics, style_line, visual_concept, recommended}`), `singer` text (the cast role who sings, "" = nobody on camera) and `spoken_end_line` text (default "", S2) | Rule 19: only the owner's typing or **Use this one** writes `text`. |
| New: `song_takes` | `id`, `draft_id` (FK script_drafts, cascade), `project_id` (nullable FK projects: set when an editor made it in their video, V2a), `job_id`, `file_id` (null until made), `lyrics` and `style_line` (the exact text it was made from), `seconds` (null until measured), `timing` (JSON: sections, beats, lines, words `[{word, start, end}]`; null until measured), `timing_job_id`, `advice` (JSON list), `preferred` bool, `batch` (each "Make 2" press), `track` (0 or 1: which of the Suno request's two songs this is; `job_id` is shared by the pair), `timing_guessed` bool, `created_by_id`, `deleted_at` (Undo) | A take can be Preferred only when `lyrics` and `style_line` equal the version's and its timing is measured (S4). At most one preferred per version, enforced in code and tested. Takes with a `project_id` are seen only in that video. |
| Breakdown shots (inside `breakdowns.data` and `script_drafts.breakdown`) | A song breakdown keeps the plain plan as it is, with a song part beside it: `data["song"] = {take_id, shots: {shot id: {start, end, sung}}}` (seconds in the song, at word or line edges). New rows carry the newest row's song part for the shots they keep (Next-Server, #799). | No migration. The ~43 readers of a plain Breakdown never see or drop it. A changed `take_id` versus the video's `song_take_id` is how a take change is noticed. |
| `project_clips` | `song_slice` JSON: `{start, end}` of the song this clip covers, and `sung_shots` | The slice is what a Sung clip lip-syncs. |
| `final_videos` | `song_take_id` (nullable FK) | The song laid underneath; null for a story video. |
| `song_takes` (narrated videos, N1, V6n) | `kind` text (`song` or `narration`, default `song`), `voice` text (default ""; "Sarah" for now), `music_file_id` and `music_job_id` (nullable: the narration's music bed and its own job, so a failed bed keeps the narration) and `trimmed` bool (the silence trim matched letter for letter and is used). A narration is a take with `lyrics` = the version's words, `style_line` = "", and timing with one line per sentence. The song sidecar `data["song"]` holds a narration's times the same way (every shot `sung: false`) | No new table: the take's lifecycle (measured, Use, out of date, Undo) is the same. n05. |
| `script_drafts` (a version) | `song_study` JSON (default null): S3a's study and its job, `{job_id, source, link, seconds, bpm, sections: [{name, start, end, lines, guessed}], lines: [{text, start, end}], words: [{word, start, end}], frames: [{file_id, t}], use_as_guide, problem, problem_code, removed_at, attempt, stale_frames}`. `attempt` `{job_id, source, link, problem, problem_code}` is the newest press, kept apart from the finished study while it runs or after it fails; `stale_frames` `[file ids]` are replaced frames, deleted at the next press | n04. Never copied into `text` or `style_line`. Remove sets `removed_at` and keeps it on the server; Undo clears it (no study comes back from the client). A removed study is never passed to S3. |
| A video's look (V3a) | `copied_from_id` (nullable, the look in the other video it came from) | Same migration as V3a. The copy is a row of its own: changing either never changes the other. Never in Cast & places (rule 12). |
| `projects` (a video) | `song_take_id` (nullable FK song_takes): the video's own song, starting as the version's preferred take (V2a); `singer` text (default: the version's; set by V2 "Who sings in this video?") | Changing it re-flows shot times for free and marks clips out of date. |

Code notes for Next-Server (not tables):
- **Whisper keeps word timings.** `server/app/whisper.py` computes them but returns lines only. Song takes need the words; the reel import keeps using lines.
- **Music provider interface.** One `music` kind behind the provider registry: **Suno** (Reed, 2026-10-28: the same service we'd use live; MiniMax dropped), its key in the server's environment through the deploy secrets only, and a free stand-in under `BS_FAKE_PROVIDERS` that, like Suno, returns two takes per request with known word timings, so every flow can be walked for free. One request makes both takes, so `song_takes.batch` is the request.
- **Credit rate** for a song take comes from the catalogue at its real Replicate cost (rule 2), seeded like the other rates.

## 1b. The plan, automatic fixes, the check (every video)

| Where | Change | Notes |
|---|---|---|
| `projects` (a video) | `plan` JSON (default null): our fields `{version, source: "made"/"owner"/"from_breakdown"/"by_hand", approved_at, approved_by_id, job_id, made_for_text_hash}` next to the Director's `schemas.ScenePlan` (`plan.model_dump()`): `structure: {name, parts: [..], based_on: "reference"/"pattern"}` (`name` carries the pattern), `cast: [cast ids]`, `scenes: [{id, part, place, cast: [cast ids], lines: [{line, action, product: id or null}]}]` | Every script line (`prompts.plan_lines`) is in exactly one scene, in order (enforced in code and tested; rule 19: the words are never stored here, only line numbers). `based_on` and a list of lines, not dicts keyed by line: a model writes a list more reliably (Director, 2026-10-29). |
| `projects` | `plan_history` JSON list (default []): earlier plans, newest first, for **Earlier plans** | Capped at 10. |
| `script_drafts` (a version) | `plan` JSON, the same shape: the owner's plan, each new video's start (S6) | Read only once published (rule 31). |
| Breakdown rows | `data["plan_version"]`: the plan version the breakdown was made from (every new plan and every edit takes the next version; Earlier plans keep theirs) | No migration (inside the JSON). A smaller number than `projects.plan.version` means "Made for an older plan". |
| `jobs` | `retry_of_id` (nullable FK jobs) and `auto` bool (default false): the one automatic retry (P3) | At most one auto retry per job, enforced in code and tested. |
| `project_clips` | `auto_fix` JSON (default null): `{before, after, fixed: ["removed \"9:16\"", …], undone}`, the wording fixed for you (P3) | **Undo** puts `before` back and sets `undone`; while the prompt is still `before`, it isn't fixed again and its flags are Advice. Spoken (quoted) words are never changed. |
| New: `item_checks` | `id`, `project_id`, `target` (`frame`, `take`, `words` or `piece`: a still's check, the director's watch of a take, a take's words, the watch of a host piece), `target_id`, `job_id`, `status` (`checking`/`done`/`failed`/`skipped`), `findings` JSON `[{kind, role, text, change_note, at?, verified?}]` (`verified` false: a watch's doubt, shown, never remade on its own), `dismissed` JSON (finding indexes with who and when), `created_at` | One row per still or take checked. Never touches approvals. `findings[].role` holds the reference id the finding is about (char:N, slot:N or product:N). Runs on the stand-ins; for real only with `BS_ITEM_CHECKS_PAID` (off until the Producer approves a test). |
| Migration plan | n06 adds the columns only. A video with a breakdown and no stored `plan` gets one read from its breakdown when it's first asked for (in code, free, `source = "from_breakdown"`, approved), so no video is blocked, made before or after. Every "is the plan approved?" (the Plan GET, the shots/breakdown guard, the step ✓ in ProjectOut, the lists and "Needs you") goes through that one function. | n06, one number for all of 1b (Builder-Server-8; Next-Lead agreed reading at read time, 2026-10-29). |

## 3. Brand setup (BR1)

| Where | Change | Notes |
|---|---|---|
| *(dropped in n36)* `brands` | `audience` text "", `do_list` JSON [], `dont_list` JSON [] (copied from `never_say`, deduped, order kept), `cta_lines` JSON `[{id, text, default, deleted_at}]` (seeded from `end_line`), `default_cast` JSON [] (library item ids), `music_style` text "", `default_language` String(10) "en", and later `default_look` String(40) "house" (after n07) | n08. Exactly one default among live CTA lines; deleting it promotes the next (Undo). A deleted or archived cast item reads `{id, deleted: true}`. `music_style` prefills new song versions only. |
| `brands.tone_notes` | Unchanged column; shown as "How the brand talks" | No reader changes. |
| *(dropped in n36)* `brands.never_say`, `brands.end_line` | **Kept on next** and written through: `never_say` = `dont_list`, `end_line` = the default CTA's text ("" if none) | Main still reads them, and main merges into next. They're dropped at the move to main (ops/NEXT.md). Next's readers use the new fields. |
| `library_items` (products) | `short_description` text "", `main_claim` text "" | Empty claim: Advice "Scripts won't mention a claim for this product." |
| BR1's S state | No brand write touches a script, version or video; later steps read the brand live | Tested: a published script and a made video are unchanged after brand edits. |

## 2. Looks: per-look sheets (ST2)

| Where | Change | Notes |
|---|---|---|
| `library_items.look_sheets` | JSON {} : `{look_id: {"file_id", "approved"}}`, the owner's sheets of a Cast & places character or place in other looks | n10. House stays in `sheet_file_id`/`sheet_approved`, so nothing existing moves. Making one is a new version of the item (Undo and versions as today). |
| `library_items.sheet_look` | String(40) "house": the look a video's own look was drawn in | n10. After the video's look changes, an own look in another look reads as out of date (ST1 counts it as "needs a new look"). |
| `projects.look_copies` | JSON {} : `{"<library item id>": <this video's own copy>}`, from "Make a {look} look for this video" | n10. For locked roles' library characters, never saved to Cast & places (rule 12). Not `slot_looks`, which is for unlocked roles. The rule is `sheets.sheet_for(db, project, item)`. |

## 4. Video settings (VS1)

| Where | Change | Notes |
|---|---|---|
| `projects.video_model`, `projects.image_model` | String(40), null = Auto (the catalogue default) | n09. The price and the job follow the pick. `catalogue.json` marks `lip_sync` on video models (no migration). |
| `projects.sung_flipped` | JSON [] : `[{shot, print}]`, the song shots a no-lip-sync model turned to B-roll | n09. Switching to a lip-sync model flips exactly those back, unless the shot's print (its plan and song timing) changed since. |
| `storyboard_frames.made_with`, `clip_takes.made_with` | JSON {} : the model, shape and products (product → variant actually attached) a still or take was made with; a take also keeps its Sung shots | n09. Out of date = any recorded value differs from the video's now; switching back makes it current again (nothing deleted). n09 fills in older rows from their job, else today's default and the video's shape. `look` keeps its own column. |
| `scripts.language` | String(10) "en", English unless one is given since n36 (was filled from the brand's `default_language`) when a script is made (every create path; a copy keeps its original's) | n09. A video reads it, read only. "Make a copy in another language" is its own (paid) item. Checked against the languages list (`app/languages.py`, #937): English on, the others off until their sample test (LG1, `language_switches` overrides a language's `on`). An editor can't pick an Off language; an Off brand default starts an editor's script in English. |
| *(dropped in n36)* Brand `default_cast` | No column: a new video with no cast starts with the brand's live default cast | — |
| `projects.own_looks` | JSON {} : `{slot_id: {look: item_id}}`, every own look a role has had in each look | n12. A look switch re-points `slot_cast`/`slot_looks` to the role's own look in the new look when there is one (free, Undo = switch back), and VS1's preview doesn't count it. |

## 5. Organization

| Where | Change | Notes |
|---|---|---|
| `folders` (people see "Project", v6 "folder") | {id, workspace_id, brand_id, parent_id, name String(120), created_by_id, created_at, deleted_at} | n11, n30. A folder can sit inside another of its brand (`parent_id`; never inside itself or a folder inside it). Delete is soft and takes the folders inside with it (same `deleted_at`): their items read as Unsorted everywhere until Undo restores them all. A live name is unique among its siblings, checked in code (a deleted one never blocks). |
| `scripts.folder_id`, `projects.folder_id`, `jobs.folder_id` | Nullable FK to `folders`; null = No project | n11. Only quick clips (jobs with no video) are filed by `jobs.folder_id`; a video's own jobs follow the video. An item goes only in a project of its own brand. Counts match the lists as the person sees them (an editor's own videos). |
| Media (OR2) | No storage: read from stills, sheets, takes, quick clips, songs and final videos | #954. A take's poster is the still it was made from. |
| `projects.storyboard_history`, `project_clips.prompt_history` | JSON [] : the 10 newest earlier storyboards (their frames as data) and clip prompts | n13. "Use this version" puts the one in hand into history first (Undo). Breakdowns go back by copying the old row as a new one (history only grows). A frame's earlier stills gain `made_at`/`made_by`; a take records its `prompt_version` in `made_with`. Files are never deleted. |
| Cost log (OR4) | No storage | #958. Spend follows where an item is filed now. |

## Voices (v6 S8-04, n32)

| Where | Change | Notes |
|---|---|---|
| `voices` | {id, workspace_id, brand_id, look, name, kind, provider, provider_voice_id, speech_model, description, sample_file_id, preview_file_id, job_id, cloned_at, last_used_at, lost_at, created_by_id, created_at, archived_at} | A brand's own voices (Reed, 4 Nov: only uploaded or cloned ones; the app's voices stay in code): clones (`cloned`, spoken through `speech_model`, minimax-speech-02-hd) and described voices (`described`, for Omni). `brand_id` null: a style's own voice (`look`), e.g. Dr. Pickle's clone. A clone may be deleted by MiniMax 7 days after `last_used_at`; `lost_at` when MiniMax said it's gone. Remove is soft (`archived_at`) with restore. |
| `library_items.voice_id`, `library_items.voice_stock_key` | Nullable FK to `voices`; String(60) an app voice's key ("Roger") | A character's voice (S8-03): a saved voice or an app voice, never both (422). A presenter's host narrates in it. |
| `song_takes.voice` | No new column: "voice:<id>" names a saved voice | A narration in a saved voice is read through its `speech_model`. |

## Brand: import from website (BR2)

No storage: the found items wait in the read's own job output until Save or Cancel; Save writes only the ticked ones through BR1's brand writes (#971).

- **New brand's Website (F_BrandNew):** `POST /brands` takes an optional `website`; the brand is made first, then its site is read as above. The answer carries `site_read_job_id` (the page opens on that review) or `site_read_problem` (why the read didn't start; the brand is made all the same). The price before the press: `GET /brands/site-read/estimate`. The website isn't stored on the brand, only on the read.
- **The review (F_BrandImport):** a read answers with its `id` and the `url` it read; `GET /brands/{id}/site-read/latest` reopens the newest one. Each found product has a `mark`: new, fills (an empty description gets this one) or have ("Already in your products", no tick). `GET …/{read}/logo` shows the found logo: fetched once with the same checks, kept on the read (`logo_file_id` in its output), and Save uses that same file.

## Team and Usage (v5 audit, #1247)

| Where | Change | Notes |
|---|---|---|
| `users` | `last_active_at` (n24): kept to within 5 minutes by `auth.current_user`; shown on Team | A locked write never fails the request. |
| `invites` | No new column. The standing editor link is an invite with `email` "" (role editor): one per workspace, works once, ends in 7 days; only a hash of its token is kept, so a fresh link replaces it | The person gives their own email when they join. Any email already here, active or removed, is refused with one wording (no "ask the owner", rule 22). The invite is claimed with a conditional update before the user is made, so two joins at once can't both use it. |
| `/usage/charges.csv?month=YYYY-MM` | No table: the month's charges read from what Usage already reads, owner only | Months 2000–2999. No cell starts a formula. |
