# Reel import: server plan

This is a plan only. The build starts after the open screen PRs land. Source: Reed's 2026-10-25 entries in `ops/DECISIONS.md` (reel import in New script, and #271: the "same style" switch and several links in bulk create).

## The idea in one paragraph

In New script, an editor uploads a reel's video or pastes an Instagram reel link. Free local steps then run in the worker: get the video, transcribe the dialogue, find the shot cuts and make a contact sheet. The editor sees one price, "Read this reel · N credits", and nothing paid runs until they press it. Then three paid steps run:

1. Gemini watches the reel and writes the shot-by-shot breakdown.
2. Claude writes version A, keeping the dialogue word for word unless the script's "Write new lines in the same style" switch is on.
3. Cast read fills the slots.

The breakdown is saved on the script, in the same shape as `docs/references/*/BREAKDOWN.json`. "Start production" passes it to the project the way a catalogue reel is passed today, so live-action parts are still dropped.

## 1. Getting the video

| Path | How | Notes |
|---|---|---|
| **Upload** (always works) | `POST /scripts/import/upload` (multipart: `brand_id`, `title`, `file`) | Stored like any other file (`files` table, local storage). The upload-size middleware gets a path entry for it. |
| **Instagram link** | `POST /scripts/import/link` `{brand_id, title, url}` | Only `https://www.instagram.com/reel/<id>/` (and `/reels/<id>/`, with or without `www.`). The worker fetches it with `yt-dlp` (pinned, no cookies, no login, 60 s timeout). |

- **Expect Instagram to block servers.** It often rate-limits or asks for a login from data-centre addresses, so the link is a convenience and the upload is the dependable path. Any fetch failure (blocked, private, removed, timeout, too big) ends the same way: "Instagram didn't let us download this reel. Upload the video instead." The script stays, and the editor can upload to it (`POST /scripts/{id}/import/upload`).
- **Caps, checked with ffprobe after the download or upload:**
  - Up to 100 MB.
  - Up to 90 seconds.
  - Video with an audio track; mp4 or mov.
  - Anything else is refused in plain words ("This video is 3 minutes long; reels up to 90 seconds can be read").
- The link is never fetched by the web server, only by the worker, and only for that one host.

## 2. Free local steps (one job: `reel_prepare`)

A new local provider, `local`, has `paid = False`, so it runs even with `BS_GENERATION_ENABLED` off. It does the free work in one job: fetch if it's a link, then probe, transcribe, cut and make the contact sheet. The result is saved on the script (see §6).

**Transcription:** faster-whisper `small`, int8, on CPU, with word timestamps. This is the same setup the Reference Analyst used for the gold altar breakdown, so we know it gives breakdown-quality lines.

| | Local faster-whisper small | Replicate Whisper model |
|---|---|---|
| Cost per reel | Free | About $0.01–0.03 (logged like any Replicate call) |
| Time for a ~60 s reel | About 20–40 s on the KVM 2 (2 CPUs) | About 10–30 s, plus upload and queue |
| VPS cost | Nothing extra: the KVM 2 we already have (8 GB) is enough. The model needs about 1 GB of memory while running. KVM 1 would also cope, just slower. | None |
| Image size | About +300 MB (ctranslate2) plus the ~460 MB model, downloaded once to a volume | None |
| Risk | It holds the worker for those seconds. It runs in a subprocess with a 3-minute timeout, so a stuck run fails the job, not the worker. | One more paid call and one more key path |

**Recommendation:** local. It's free, private, proven on the gold reel, and fits the server we already pay for. If it ever proves too slow, swapping in the Replicate model touches only `transcribe()`.

**Shot cuts:** ffmpeg scene detection (`select='gt(scene,0.3)',showinfo`), free and local. Story-studio's cut detection is **not** in this repo, and we don't touch story-studio, so this is a small new `app/reel.py` (about 40 lines). It holds the cut times, shot count, median and shortest shot. These `stats` are computed here, not guessed by a model.

**Contact sheet:** one frame from the middle of each shot, tiled with ffmpeg into one JPEG, stored as a file. The editor sees it on the import screen, and Gemini gets it as an extra image.

## 3. Paid steps: one estimate, three jobs

- `GET /scripts/{id}/import` returns, once prep is done:
  - `{status: "ready", seconds, shots, transcript, contact_file_id, estimate: {credits, credits_left}}`.
  - The screen shows "Read this reel · N credits".
- N is the sum of the three steps' estimates:
  - watch-gemini: 1 call.
  - write-claude: 1 call.
  - Cast read: 1 write-claude call.
  - That's about 7 credits at today's rates (roughly $0.70).
- `POST /scripts/{id}/import/read` is billed like the other script steps:
  - Reed is unlimited.
  - An editor's import spends their weekly allowance.
  - If the **whole** estimate doesn't fit, it's declined (409, "This reel needs 7 credits; you have 4 left this week."), the same all-or-none rule as Write all.
- **How the chain runs:**
  1. The press queues the watch job. When it's saved, the worker queues the write job, and when that's saved, cast read.
  2. The follow-on jobs are already paid for by the press, so they skip the allowance check. `enqueue(..., prepaid=True)` keeps the rest: brand, credits, Usage.
  3. A failed step stops the chain and says which step didn't finish. `POST /scripts/{id}/import/read` again retries from that step, with a new estimate for what's left.

| Step | Job | Input | Saves |
|---|---|---|---|
| Watch | `watch-gemini` on Replicate (`gemini-3.5-flash`, already in the catalogue) | Video, contact sheet, transcript with times, and the cut list. Prompt `prompts/reel_watch.md` from the **Director**. | `scripts.reference_breakdown`: shots (framing, camera, on screen, action, emotion, style per shot), beats, hook, montage, why it works. `lines` come from the transcript, not from Gemini; Gemini only labels the speaker. |
| Write | `write-claude`, step `script_draft` (the existing Write; it already sends a `<reference>` block) | The script's own breakdown (not the catalogue reel), plus the "same style" switch below. The **Director** adds that input to `script_draft.md`. | Version A's words (slot 0) with history source `"reel"`, and `title` if it was blank. |
| Cast read | `write-claude`, step `cast_slots` (existing) | Unchanged | Slots, as today |

- **Video to Gemini:** our files are sent as data URLs today, which is fine for images. A 20–100 MB video is too big for that, so the build uploads it through Replicate's file upload (`POST /v1/files` on `api.replicate.com`, already allowed) and passes that URL. This is the one provider change, and it's inside `ReplicateProvider`. Generation behaviour doesn't change.
- **"Write new lines in the same style"** is a per-script switch, `scripts.new_lines`, off by default. It's set when the script is made (`new_lines: bool | None = None` on create, bulk and import) and can be changed until version A is approved.
  - **Off:** keep the reel's dialogue word for word. A new check, `check.reel_script(transcript, text)`, says which transcript line is missing or changed in version A. A failure keeps the words but lists the problem on the version, the same way breakdown problems show today. It never silently rewrites the text.
  - **On:** Claude writes new dialogue in the reel's style and beats. The word-for-word check is skipped, and the breakdown and length checks still run.
  - The switch goes to `script_draft` in its input. Variations and later Writes see it too.
- **Redo notes** (the decision's last point): when the Director's `check.redo_note` lands, `POST /clips/{id}/generate` runs it on the note. This is separate from import and wired as its own small PR.

## 4. Several reels at once (bulk create and Write all)

- **Bulk create:**
  - `POST /scripts/bulk` rows gain `reel_url: str | None = None` and `new_lines: bool | None = None`. The screen splits the pasted links, one per line, into rows. The title defaults to "Reel 1", "Reel 2"… until the read fills it.
  - Each row with a link becomes a draft script with its own `reel_prepare` job.
  - The cap stays at 50 rows, and a bad link refuses the whole request (422, naming the line).
- **Fetching:** Instagram fetches run one at a time with a short pause between them, so a batch is less likely to be blocked. Each reel that fails says "Upload the video instead" on its own row. The others carry on.
- **Write all:**
  - `POST /scripts/write/estimate` gives **one total**: for each script, reading its reel (watch + cast read) if it has an unread reel, plus writing.
  - The answer adds `{reading: n, writing: n, waiting: [ids], failed: [ids]}`, and the screen shows e.g. "Read 5 reels and write 5 scripts · 35 credits".
- **`POST /scripts/write`** stays all or none against an editor's allowance:
  - Reel scripts get the watch → write → cast read chain, and plain scripts get the usual write.
  - It's refused (409) while any chosen reel is still being prepared or failed to download: "2 reels are still being prepared". Then you can press again, or untick them.

## 5. Hand-off to production

- `POST /scripts/{id}/drafts/{slot}/produce` uses `script.reference_breakdown` when it's set, and otherwise the catalogue reel (`reference_id`) as today. `reference_replace` works the same.
- The breakdown, storyboard and clip prompts already read `project.reference_breakdown`. The existing rule drops shots marked live action or turns them into the brand CTA, so it applies unchanged.
- In the library, the "adapted from a reel" filter counts both catalogue and imported reels. `reference_name` for an imported reel is the first part of its logline.

## 6. Data and migration

**0031_reel_import** (one linear step after 0030) adds four columns to `scripts`:

| Column | Type | What |
|---|---|---|
| `reference_breakdown` | JSON, null | The imported reel's breakdown (BREAKDOWN.json shape) |
| `reel` | JSON, null | `{source: "upload" \| "link", url, video_file_id, contact_file_id, seconds, transcript: [{start, end, text, speaker}], cuts: [...], stats, step, problem}` |
| `reel_job_id` | int, null | The latest import job, so "is it running" is one lookup |
| `new_lines` | bool, default false | "Write new lines in the same style" |

Import status is worked out (`preparing / ready / reading / done / failed`), not stored. The video, contact sheet and transcript are kept for the life of the script, and deleting the script deletes its files.

## 7. Endpoints

| Method | Path | Who | Returns |
|---|---|---|---|
| POST | `/scripts/import/upload` | Any member, for a brand they can see | 201 script, `reel_prepare` queued |
| POST | `/scripts/import/link` | Same | 201 script, `reel_prepare` queued; 422 for a URL that isn't a reel |
| POST | `/scripts/{id}/import/upload` | Author or owner | Replaces a failed link with an upload |
| GET | `/scripts/{id}/import` | Whoever can see the script | Status, transcript, contact sheet, estimate, problem |
| POST | `/scripts/{id}/import/read` | Author or owner | 201 jobs; 409 over the allowance, while running, or once words are approved |
| POST | `/scripts/bulk` (existing) | Same as today | Rows may carry `reel_url` and `new_lines` |
| POST | `/scripts/write/estimate`, `/scripts/write` (existing) | Same as today | One total covering reading and writing; refused while a chosen reel isn't ready |
| PATCH | `/scripts/{id}` (existing) | Author or owner | Takes `new_lines` until version A is approved |

Request models get `None` defaults for their optional fields, so openapi-typescript doesn't make them required. `schema.d.ts` is regenerated in each PR.

## 8. Tests (all free; stand-ins only)

- Upload and link: caps (too long, too big, no audio), the URL allowlist, and a refused fetch giving the "Upload the video instead" message.
- `reel.py` on a generated two-scene clip (ffmpeg `testsrc`, then `smptebars`). It finds one cut, and the contact sheet has two tiles.
- Transcription goes through an interface. Tests use a stand-in, so CI never downloads the model. One opt-in test (`-m whisper`, skipped by default) runs the real model on a 5 s clip.
- Estimate and read:
  - All or none against an editor's allowance.
  - The owner is unlimited.
  - The chain queues write and then cast read with no second allowance check.
  - A failed watch stops the chain, and the retry re-estimates what's left.
- The dialogue check flags a dropped or changed line. With `new_lines` on, it's skipped, and the flag reaches the `script_draft` input.
- Bulk with three links makes three drafts and three prepare jobs. One link that is refused doesn't stop the others. Write all's total covers reading and writing, and it's refused while a reel is still being prepared.
- Produce passes `reference_breakdown` into the project, and a live-action shot is dropped as today.
- Brand on every job (tracker): import jobs carry the script's brand.

**fake_run:** a new `import_reel(c, work)` step. It uploads a generated 6 s, two-scene clip and drains. The stand-in transcription returns two lines. Then it checks the estimate, reads the reel and drains again. The stand-in Gemini returns the altar breakdown trimmed to the cuts, and the stand-in Claude writes version A that keeps both lines. It checks that version A and the slots are filled, then produces once and confirms the project has the reference.

## 9. Build order (small PRs, after the screen PRs land)

1. Migration 0031 (with `new_lines`), the model, and the produce hand-off (with the library filter).
2. Upload and link endpoints, the `local` provider, and `reel_prepare`: probe, caps, cuts, contact sheet, transcription with a stand-in, plus faster-whisper and yt-dlp in the server image.
3. Estimate and read: the watch, write and cast-read chain, `prepaid` enqueue, the dialogue check and the Replicate file upload.
4. Bulk links and Write all over reels (one total estimate).
5. The fake_run step (one reel through import, plus two links through bulk and Write all).
6. Redo-note check on clip generate (when the Director's check lands).

## Needs from others

- **Director:**
  - `reel_watch.md`.
  - The `new_lines` input and the use of a script's own breakdown in `script_draft.md`.
  - The JSON schema the watch must return (we'll validate it in `prompts/schemas.py`).
  - `check.redo_note`.
- **Producer:** approval for one real test read of the altar reel once 3 is merged. That's about 7 credits, logged in `ops/SPEND.md`. A yes or no on yt-dlp fetching from Instagram as a convenience path; the upload alone also meets the decision.
- **Builder-Screens:** the import screen uses `GET /scripts/{id}/import` as above.
