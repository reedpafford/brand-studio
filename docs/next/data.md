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
| 15 | n16 | #1053 | n15 | Open, testing (QA-3) |

## 1. Song ads

| Where | Change | Notes |
|---|---|---|
| `scripts` | `kind` text: the **Format**. `story` (shown as **Dialogue**), `song` or `narrated`, default `story` | Set at New script (S1). Dialogue ↔ Narrated can change before publishing (ST0); Song never changes. `narrated` needs no migration (text). |
| `script_drafts` (a version) | The lyrics are the version's `text`, as a story's words are. Add `style_line` text (default ""), `song_directions` JSON list (default [], each `{concept, lyrics, style_line, visual_concept, recommended}`), `singer` text (the cast role who sings, "" = nobody on camera) and `spoken_end_line` text (default "", S2) | Rule 19: only the owner's typing or **Use this one** writes `text`. |
| New: `song_takes` | `id`, `draft_id` (FK script_drafts, cascade), `project_id` (nullable FK projects: set when an editor made it in their video, V2a), `job_id`, `file_id` (null until made), `lyrics` and `style_line` (the exact text it was made from), `seconds` (null until measured), `timing` (JSON: sections, beats, lines, words `[{word, start, end}]`; null until measured), `timing_job_id`, `trim_to` (seconds, null = whole take; "Use the first 0:55"), `advice` (JSON list), `preferred` bool, `batch` (each "Make 2" press), `track` (0 or 1: which of the Suno request's two songs this is; `job_id` is shared by the pair), `timing_guessed` bool, `created_by_id`, `deleted_at` (Undo) | A take can be Preferred only when `lyrics` and `style_line` equal the version's and its timing is measured (S4). At most one preferred per version, enforced in code and tested. Takes with a `project_id` are seen only in that video. |
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
| New: `item_checks` | `id`, `project_id`, `target` (`frame` or `take`), `target_id`, `job_id`, `status` (`checking`/`done`/`failed`/`skipped`), `findings` JSON `[{kind: face/outfit/product, role, text, change_note}]`, `dismissed` JSON (finding indexes with who and when), `created_at` | One row per still or take checked. Never touches approvals. `findings[].role` holds the reference id the finding is about (char:N, slot:N or product:N). Runs on the stand-ins; for real only with `BS_ITEM_CHECKS_PAID` (off until the Producer approves a test). |
| Migration plan | n06 adds the columns only. A video with a breakdown and no stored `plan` gets one read from its breakdown when it's first asked for (in code, free, `source = "from_breakdown"`, approved), so no video is blocked, made before or after. Every "is the plan approved?" (the Plan GET, the shots/breakdown guard, the step ✓ in ProjectOut, the lists and "Needs you") goes through that one function. | n06, one number for all of 1b (Builder-Server-8; Next-Lead agreed reading at read time, 2026-10-29). |

## 3. Brand setup (BR1)

| Where | Change | Notes |
|---|---|---|
| `brands` | `audience` text "", `do_list` JSON [], `dont_list` JSON [] (copied from `never_say`, deduped, order kept), `cta_lines` JSON `[{id, text, default, deleted_at}]` (seeded from `end_line`), `default_cast` JSON [] (library item ids), `music_style` text "", `default_language` String(10) "en", and later `default_look` String(40) "house" (after n07) | n08. Exactly one default among live CTA lines; deleting it promotes the next (Undo). A deleted or archived cast item reads `{id, deleted: true}`. `music_style` prefills new song versions only. |
| `brands.tone_notes` | Unchanged column; shown as "How the brand talks" | No reader changes. |
| `brands.never_say`, `brands.end_line` | **Kept on next** and written through: `never_say` = `dont_list`, `end_line` = the default CTA's text ("" if none) | Main still reads them, and main merges into next. They're dropped at the move to main (ops/NEXT.md). Next's readers use the new fields. |
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
| `scripts.language` | String(10) "en", filled from the brand's `default_language` when a script is made (every create path; a copy keeps its original's) | n09. A video reads it, read only. "Make a copy in another language" is its own (paid) item. Checked against the languages list (`app/languages.py`, #937): English on, the others off until their sample test (LG1, `language_switches` overrides a language's `on`). An editor can't pick an Off language; an Off brand default starts an editor's script in English. |
| Brand `default_cast` | No column: a new video with no cast starts with the brand's live default cast | — |
| `projects.own_looks` | JSON {} : `{slot_id: {look: item_id}}`, every own look a role has had in each look | n12. A look switch re-points `slot_cast`/`slot_looks` to the role's own look in the new look when there is one (free, Undo = switch back), and VS1's preview doesn't count it. |

## 5. Organization

| Where | Change | Notes |
|---|---|---|
| `folders` (people see "Project") | {id, workspace_id, brand_id, name String(120), created_by_id, created_at, deleted_at} | n11. Delete is soft: its items read as No project everywhere until Undo restores it. A live name is unique per brand, checked in code (a deleted one never blocks). |
| `scripts.folder_id`, `projects.folder_id`, `jobs.folder_id` | Nullable FK to `folders`; null = No project | n11. Only quick clips (jobs with no video) are filed by `jobs.folder_id`; a video's own jobs follow the video. An item goes only in a project of its own brand. Counts match the lists as the person sees them (an editor's own videos). |
| Media (OR2) | No storage: read from stills, sheets, takes, quick clips, songs and final videos | #954. A take's poster is the still it was made from. |
| `projects.storyboard_history`, `project_clips.prompt_history` | JSON [] : the 10 newest earlier storyboards (their frames as data) and clip prompts | n13. "Use this version" puts the one in hand into history first (Undo). Breakdowns go back by copying the old row as a new one (history only grows). A frame's earlier stills gain `made_at`/`made_by`; a take records its `prompt_version` in `made_with`. Files are never deleted. |
| Cost log (OR4) | No storage | #958. Spend follows where an item is filed now. |

## Brand: import from website (BR2)

No storage: the found items wait in the read's own job output until Save or Cancel; Save writes only the ticked ones through BR1's brand writes (#971).
