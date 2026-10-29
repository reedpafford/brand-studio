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
| n03 | Flavour from the script: `script_drafts.flavours` JSON `{product: variant}` (default `{}`), copied to the video at Make this version (the video's own pick stays where it is today) | Next-Server | — |
| n04 | Song-ad study (S3a): `script_drafts.song_study` JSON, default null | Builder-Server-7 | — |
| n05 | Narrated (N1, V6n): `song_takes.kind`, `voice`, `music_file_id`, `music_job_id`, `trimmed`; `scripts.kind` gains `narrated` (validation only) | Next-Server | — |
| n06 | Every video (1b): `projects.plan`, `projects.plan_history`, `script_drafts.plan`, `jobs.retry_of_id`, `jobs.auto`, `project_clips.auto_fix`, new `item_checks`; existing videos are planned from their breakdown in code, when read | Builder-Server-8 | — |
| n07 | Format and Look step 1: `scripts.look`, `projects.look` (text, default `house`), new `look_switches` {workspace_id, look_id, on, sample_still_id, sample_clip_id, switched_by_id, switched_at} | Next-Server | — |
| n08 | Brand setup (BR1): new `brands` columns and product description/claim, below | Builder-Server-7 | — |

## Merge order (the chain on `next`)

Numbers are names, not an order. A PR waiting its turn points its `down_revision` at next's current head so its CI runs (CI tests it merged with next), and moves to its real parent just before it merges; the Producer checks for one head before every merge. Each migration's `down_revision` is the head on `next` when it merges, so the chain stays one line. When one merges, Next-Lead tells the next owner to set their `down_revision` to it.

| Turn | Migration | PR | `down_revision` | State |
|---|---|---|---|---|
| — | n01 | #748 | 0053 | On `next` |
| 1 | n02 | #829 | n01 | On `next` |
| 2 | n04 | #851 | n02 | On `next` |
| 3 | n06 | #862 | n04 | On `next` |
| 4 | n07 | #873 | n06 | On `next` (merged before n05) |
| 5 | n05 | #858 | n07 | Open: being re-pointed to n07 |
| 6 | n08 | Builder-Server-7, brand setup | n05 (once #858 is in) | Not open; tracks next's head for CI until its turn |
| — | n03 | Next-Server, flavours | the head when it's built | Not started |

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
| Breakdown rows | `data["plan_version"]`: the plan version the breakdown was made from | No migration (inside the JSON). A smaller number than `projects.plan.version` means "Made for an older plan". |
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

## 2–6. Later items

Filled in before each item is built, in build order: looks (Reed, 2026-10-29: Format and Look are two settings; looks read from the existing `server/app/prompts/styles/` files (kind: look; the folder keeps its name, the screens say Look), `look` text on `scripts` and `projects`, default `house`, `look_switches` for On/Off (n07), and per-look sheets as library versions; Format is `scripts.kind`, above), video settings (`video_model`, `image_model`, `language` on videos), organization (a grouping table, `folder` links, `preferred` on stills and looks, versions on storyboards and clip prompts).
