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
| n01 | Song ads: `scripts.kind`, `script_drafts.style_line`, `script_drafts.song_directions`, `script_drafts.singer`, `script_drafts.spoken_end_line`, `song_takes`, `projects.song_take_id` | Next-Server | — |
| n02 | Song ads: `project_clips.song_slice`, `final_videos.song_take_id` | Next-Server (with the breakdown work) | — |
| n03 | Flavour from the script: `script_drafts.flavours` JSON `{product: variant}` (default `{}`), copied to the video at Make this version (the video's own pick stays where it is today) | Next-Server | — |

## 1. Song ads

| Where | Change | Notes |
|---|---|---|
| `scripts` | `kind` text, `story` or `song`, default `story` | Set at New script (S1); never changes after. |
| `script_drafts` (a version) | The lyrics are the version's `text`, as a story's words are. Add `style_line` text (default ""), `song_directions` JSON list (default [], each `{concept, lyrics, style_line, visual_concept, recommended}`), `singer` text (the cast role who sings, "" = nobody on camera) and `spoken_end_line` text (default "", S2) | Rule 19: only the owner's typing or **Use this one** writes `text`. |
| New: `song_takes` | `id`, `draft_id` (FK script_drafts, cascade), `project_id` (nullable FK projects: set when an editor made it in their video, V2a), `job_id`, `file_id` (null until made), `lyrics` and `style_line` (the exact text it was made from), `seconds` (null until measured), `timing` (JSON: sections, beats, lines, words `[{word, start, end}]`; null until measured), `timing_job_id`, `trim_to` (seconds, null = whole take; "Use the first 0:55"), `advice` (JSON list), `preferred` bool, `batch` (each "Make 2" press), `track` (0 or 1: which of the Suno request's two songs this is; `job_id` is shared by the pair), `timing_guessed` bool, `created_by_id`, `deleted_at` (Undo) | A take can be Preferred only when `lyrics` and `style_line` equal the version's and its timing is measured (S4). At most one preferred per version, enforced in code and tested. Takes with a `project_id` are seen only in that video. |
| Breakdown shots (inside `breakdowns.data` and `script_drafts.breakdown`) | A song breakdown keeps the plain plan as it is, with a song part beside it: `data["song"] = {take_id, shots: {shot id: {start, end, sung}}}` (seconds in the song, at word or line edges). New rows carry the newest row's song part for the shots they keep (Next-Server, #799). | No migration. The ~43 readers of a plain Breakdown never see or drop it. A changed `take_id` versus the video's `song_take_id` is how a take change is noticed. |
| `project_clips` | `song_slice` JSON: `{start, end}` of the song this clip covers, and `sung_shots` | The slice is what a Sung clip lip-syncs. |
| `final_videos` | `song_take_id` (nullable FK) | The song laid underneath; null for a story video. |
| `projects` (a video) | `song_take_id` (nullable FK song_takes): the video's own song, starting as the version's preferred take (V2a); `singer` text (default: the version's; set by V2 "Who sings in this video?") | Changing it re-flows shot times for free and marks clips out of date. |

Code notes for Next-Server (not tables):
- **Whisper keeps word timings.** `server/app/whisper.py` computes them but returns lines only. Song takes need the words; the reel import keeps using lines.
- **Music provider interface.** One `music` kind behind the provider registry: **Suno** (Reed, 2026-10-28: the same service we'd use live; MiniMax dropped), its key in the server's environment through the deploy secrets only, and a free stand-in under `BS_FAKE_PROVIDERS` that, like Suno, returns two takes per request with known word timings, so every flow can be walked for free. One request makes both takes, so `song_takes.batch` is the request.
- **Credit rate** for a song take comes from the catalogue at its real Replicate cost (rule 2), seeded like the other rates.

## 2–6. Later items

Filled in before each item is built, in build order: style registry (a `styles/` folder, `style` on scripts and videos, per-style sheets as library versions), brand setup (new brand columns, `never_say` moving into `dont_list`), video settings (`video_model`, `image_model`, `language` on videos), organization (a grouping table, `folder` links, `preferred` on stills and looks, versions on storyboards and clip prompts).
