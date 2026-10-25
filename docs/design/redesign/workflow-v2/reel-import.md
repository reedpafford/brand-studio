# Reel import: read a reel into a new script

Reed, 2026-10-25 (DECISIONS #270): paste an Instagram reel link or upload the video. The app does the Reference Analyst's job:
1. download it
2. transcribe the dialogue
3. find the shots and the camera
4. write the shot-by-shot breakdown
5. pre-fill the script (the dialogue word for word) and the cast slots, for Reed to adapt

Live-action parts are dropped, as usual. The price shows before anything paid runs. A redo note can never change the dialogue.

This adds to the Description step (`description.md`, field 3) and the writing flow. Mock: `reel-import.png`.

## Where it sits
**New script** starts with a segmented switch above the form: **Describe it | Import a reel** (as built in #289).
- **Describe it:** the Description form as today. Its **Reference reel (optional)** list includes reels imported before.
- **Import a reel:** this spec. Instead of the form, it shows the link field, Upload, and the switch **Write new lines in the same style**:
  - off by default
  - helper (meta): "Off: keep the reel's lines and rewrite only what the brand swap needs."

  Getting the reel creates the draft, and its Description fields are filled in later (§6).

An imported reel is saved to the reel library, so anyone can pick it for another script later. Its name is the logline, and Reed can rename it.

## 1. Getting the reel (free)
```
Import a reel (tab)
[ Paste an Instagram reel link                     ] [Get the reel]      (desktop: one row)
or  [Upload  Upload a video]   MP4 or MOV, up to 90 s and 100 MB (meta)
```
- **Link:** an input with `inputmode="url"`, placeholder "https://www.instagram.com/reel/…". Then **Get the reel** (secondary).
  - It accepts `instagram.com/reel/…` and `instagram.com/p/…` links.
  - Anything else reads "That isn't an Instagram reel link." right under the field.
- **Upload:** secondary with `Upload`, which opens the file picker. MP4 or MOV, up to 90 seconds and 100 MB (the server's limits).
- Getting the reel is free: it's the download (or the upload) plus a check of its length. It **creates the draft right away** ("Untitled reel" until Reed names it), so a reel that is still downloading, or one that failed, is never lost; the draft opens at Description with the reel in the reference block.
  - While it runs, the row shows "Getting the reel… 6 s", or "Uploading… 42%" with a bar.
- **When it's in, a preview card replaces the inputs:**
  ```
  ┌ [9:16 thumb 72×128] │ instagram.com/reel/DehudnaAmce · 45 s          [Change] (ghost) ┐
  │                     │ Reading it costs about 7 credits (meta)                         │
  └─────────────────────┴────────────────────────────────────────────────────────────────┘
  [Read this reel · 7 credits]   (amber)
  ```
- **The one amber button is Read this reel · N credits.** The price comes from the length (the read estimate).
  - **Reed:** always enabled. There's no video yet, so no video budget applies.
  - **An editor** past their weekly allowance gets the button disabled with the reason "That's more than this week's 145 free credits (120 used). It resets on Monday." There's no Ask Reed (decision l).
- **On phone,** Read this reel takes the action bar. Get the reel and Upload are full width at 44px.

## 2. Reading it (paid)
Read this reel starts the paid steps on the draft that Get the reel made, and shows the progress in the reference block:
```
Reading the reel · 1 min 10 s (meta, counting up)
 ✓ Got the reel                       45 s · 1080×1920
 ✓ Listening to the dialogue          11 lines
 ◌ Finding the shots and the camera   (spinner)
 ○ Writing the breakdown
 ○ Writing the script and the cast
```
- **Five rows,** each with an icon: `Check` (success) for done, `Loader` (spinning) for now, and an empty circle (muted) for next. A done row gets a meta result on the right ("11 lines", "50 shots · 1 dropped").
- **It keeps going if Reed leaves the page.** The library row shows "A · Reading the reel…" (neutral, `Loader`), and the progress shows again when the script is opened. It's read from the job, on any device.
- **When it's done:** toast "Reel read. 50 shots, 1 dropped. Check the breakdown." The block becomes the done card (§3).

**Failure states.** One danger line replaces the row that failed, with its own button. Credits for unfinished steps are never charged (the server returns them).

| Step | What shows | Button |
|---|---|---|
| Got the reel (link) | "Instagram didn't let us download it. Upload the video instead." | **Upload a video** (secondary) |
| Got the reel (link, private or removed) | "That reel is private or was removed." | **Upload a video** |
| Got the reel (upload) | "That file isn't a video we can read. Use an MP4 or MOV." (Too long: "This reel is over 90 seconds. Upload a shorter cut.") | **Choose another file** |
| Listening | "We couldn't make out the dialogue. Nothing was charged." | **Try again** (free retry once) |
| No dialogue at all | Not an error: the row reads "No dialogue (music only)" and reading carries on. | — |
| Finding the shots | "The shots couldn't be found. Credits for the rest were returned." | **Try again · N credits** |
| Writing the breakdown or the script | "The breakdown didn't finish. Credits for this step were returned." | **Try again · N credits** |

## 3. The done card (in Description)
```
┌ [thumb 72×128] │ A groom is dumped at the altar for a richer man… (card, 2 lines)            ┐
│                │ Imported · 45 s · 50 shots · 1 dropped (live action) · 11 lines (meta)        │
│                │ [Review the breakdown] (secondary)   [Read it again] (ghost)                 │
└────────────────┴──────────────────────────────────────────────────────────────────────────────┘
What to change (textarea, as today): "For example: the altar becomes a car showroom…"
```
- **Review the breakdown** opens §4.
- **Read it again** opens the redo (§5).
- The **Script** step is filled in (§6), so Next: Script works straight away.

## 4. Review the breakdown (`/b/:brandId/scripts/:id/reel`)
A full page in the writing frame (header, step picker), reached from the done card. ‹ Back goes to the step it came from.

**Desktop (≥ 1024): two columns.**
- **Left (sticky, 300px):**
  - the player (9:16, with a scrubber)
  - under it: the logline (body), the hook as "Hook · 0:00–0:05: Cold open mid-climax…" (meta, 3 lines, `Show more`), and the length
  - **Use this reel** (amber, full width). It goes to Script with the toast "Script filled from the reel. Adapt it for Iron Paws."
- **Right:** the shot list, one card divided by rows.
  ```
  Shots (section)   50 shots · 1 dropped (live action) · 11 lines (meta)      [All | Lines only | Dropped]
  ┌──────────────────────────────────────────────────────────────────────────────────────────┐
  │ 1  0:00–0:00.4 · Wide three-shot, eye level · Static                                      │
  │    Groom says his vows; bride turns away (body)                                          │
  │    GROOM: I do.   (script font)                                                           │
  ├──────────────────────────────────────────────────────────────────────────────────────────┤
  │ 2  0:00.4–0:00.8 · Extreme close-up, low angle · Quick push-in                            │
  │    Bride screams her refusal straight at camera                                          │
  │    BRIDE: HELL NO!                                                                        │
  ├──────────────────────────────────────────────────────────────────────────────────────────┤
  │ 50 0:42.7–0:45 · Handheld phone clips                         [Dropped · live action]    │  (muted)
  │    Real creator's lifestyle flexes                                                       │
  └──────────────────────────────────────────────────────────────────────────────────────────┘
  ```
- **Each row:**
  - the number (meta, tabular)
  - the time "0:00.4–0:00.8" (meta, tabular)
  - framing · camera (meta)
  - the action (body, 2 lines)
  - the line in the script font, "SPEAKER: words", when there is one
  - Tapping a row seeks the player to that shot.
- **Live-action shots** are muted (text `--text-faint`) with a neutral badge `Dropped · live action`, and they're never in the script. The meta line counts them.
- **Montages** with many tiny shots (under 1 s each, 5 or more in a row) are grouped: "Shots 17–40 · montage · 11.7 s" (meta), with a disclosure that opens them.
- **Filters:** a segmented control: All · Lines only · Dropped.
- **Nothing here is edited.** The breakdown is what the reel does; Reed adapts it in the script. Fixes go through Read it again.

**Phone (< 1024):**
- The player sits at the top at full width, up to 360px tall, and doesn't stick.
- Then the logline and hook, then the segmented control, then the shots as stacked rows.
- **Use this reel** takes the action bar.

## 5. Read it again (a redo with a note)
- **Read it again** opens a sheet (phone) or side panel (desktop):
  - "What did it get wrong? (optional)", a textarea, placeholder "e.g. shot 3 is the groom, not the priest; the montage starts at 0:17".
  - The amber button is **Read it again · N credits**: the price of the breakdown and script steps only. The download and the transcript are kept.
- **The note can't change what's said.** It's checked like a clip prompt note. If it asks to change, add or remove dialogue, the server refuses and the panel shows:
  > "Notes can fix who's speaking, the shots and the camera, but not the words said in the reel. Change the words in the script instead."
- **When the new breakdown lands,** it replaces the old one, and the script and cast are filled again, but only if Reed hasn't edited them yet. If he has, the done card says "New breakdown ready. Your script edits are kept." with **Fill the script again** (ghost), which asks first: "Replace your script with the reel's? Your edits will be lost." **Keep my script** / **Replace**.

## 6. The script and the cast it fills
- **Script (A · Original), DECISIONS #271:** the reel's spoken lines are kept **word for word**, with its shots, beats, pacing and feel, as scenes with the shot actions as direction lines.
  - Only the lines the brand swap needs are rewritten. For example, with "What to change: reselling becomes trading", "I bought 40 hoodies to resell" becomes "I bought 40 shares of one coin".
  - Dropped live-action shots are left out.
  - **Rewritten lines are marked** like Directions and Variations: `bg-mark` with the 2px `mark-line` underline. Under each one, a meta line in the script font gives the reel's original: "Was: I bought 40 hoodies to resell." A legend sits above the script: "Marked lines were rewritten for Iron Paws. Everything else is said as in the reel."
  - Approve and Edit work as on any script. Editing a marked line keeps its mark and its "Was:" line until approval, so Reed can still compare.
  - A banner (`Info`) reads "From the reel: 9 lines kept, 2 rewritten for Iron Paws. Check them, then approve." It goes once Reed approves.
- **The switch "Write new lines in the same style",** off by default:
  - **Where it shows:** in New script (Import a reel, and also under a reel picked From the library), and on the **Script** step whenever the script has a reference.
  - **What it does:** when it's on, the dialogue is written fresh in the reel's voice, pacing and line lengths, and nothing is marked. The legend reads "New lines, in the style of the reel." The shots, beats and length still follow the reel.
  - **Helper (meta) under the switch:** "Off: keep the reel's lines and rewrite only what the brand swap needs."
  - **Changing it after the script is written** doesn't rewrite on its own. The Script step shows **Write the script again · N credits** (secondary), which asks first if Reed has edited: "Write the script again? Your edits will be lost." **Keep my script** / **Write again**.
- **Cast:** a slot for each named or recurring speaker or character in the breakdown (Bride, Groom/Nate, Rival), marked "From the reel" (meta). It's a free pre-fill, not the paid "Read the cast": the breakdown already names them.
  - Background people (guests, the priest as an extra) aren't slots, as in Cast.
  - Reed renames, locks and removes them as usual.
- **Description:** the title is empty for Reed to fill ("Untitled reel" until then). "What it's for" is pre-filled from the logline. The reference is the imported reel, and **What to change** is ready to type.

## 7. Bulk create: paste reel links (DECISIONS #271)
Bulk create (`description.md`) gets a mode switch at the top: a segmented control **Rows · Reel links**.
- **Reel links:**
  - A textarea, "Paste reel links, one per line", with the placeholder "https://www.instagram.com/reel/…".
  - Under it, the switch **Write new lines in the same style** (off), which applies to all of them.
  - The optional **What to change** (textarea, 2 rows) applies to all of them too: "For example: reselling becomes trading."
  - Up to 20 links. Lines that aren't Instagram reel links are listed under the field ("Line 3 isn't a reel link") and block the button.
- **Make {n} drafts:**
  - It creates one draft per link, with the reference attached and the title "Untitled reel" (filled from the logline once read).
  - It also gets each reel (free), so lengths are known.
  - Rows that couldn't be fetched stay as drafts marked "Couldn't get the reel" (danger), with **Upload the video** in the draft's Description.
- **Drafts made:** each draft with its chip ("Reel · 45 s", or "Couldn't get the reel"), then one total:
  - "About 35 credits: reading 5 reels (5) and writing 5 scripts and casts (30)" (meta). A failed row isn't counted.
  - The amber **Write all scripts · 35 credits** reads each reel, then writes each script and its cast.
  - For an editor, the same total is checked against the week. Past it, the button is disabled with the reason, and there's no Ask Reed. The server runs all or none, as for Write all.
- **After Write all:** the library rows show "A · Reading the reel…", then "A · Writing". The toast reads "Reading 5 reels and writing their scripts. They'll show as drafts when they're ready."
- **Phone:** the same, in the sheet. The mode control is full width, and the amber button is in the action bar.

## States (summary)
| State | What shows |
|---|---|
| Not started | Two tabs; Import shows the link field and Upload. |
| Getting the reel | "Getting the reel… 6 s" / "Uploading… 42%". Cancel (ghost). |
| Ready to read | Preview card, price, amber **Read this reel · N credits**. |
| Over the allowance (editor) | The button is disabled, with the reason and the reset day. |
| Reading | The five-row progress, with the time counting up. |
| Failed | The row's danger line and its button (table in §2). |
| Done | The done card; Script and Cast filled. |

## Words and icons
- **Icons:**
  - `Link` on the URL field
  - `Upload`, `Loader`, `Check`, `CircleAlert`
  - `RotateCcw` for Read it again
  - `Play` for the player
  - `Film` for the done card when there's no thumbnail
- **Never shown:** "whisper", "transcribe", model or provider names, job ids, raw times ("0.40" is shown as "0:00.4").

## Data the screens need (server)
For Builder-Server. Downloading and uploading are free. Every paid step goes through the estimate and the allowance (all or none, as for Write all).
- **Getting the reel (built, #282):**
  - **By link:** `POST /scripts/import/link {brand_id, url, title?, new_lines?}`. It accepts `/reel/` and `/p/` links and refuses others with "That isn't an Instagram reel link."
  - **By upload:** `POST /scripts/import/upload` (multipart: `file`, `brand_id`, `title?`, `new_lines?`), MP4 or MOV, up to 90 s and 100 MB.
  - Both create the draft straight away and return `ImportOut {script_id, status: preparing | ready | failed, source, url, seconds, shots, transcript, video_file_id, contact_file_id, problem, problem_code}`.
  - `problem_code` is `blocked` (Instagram refused), `gone` (private or removed), `bad_file` or `too_long`, and `problem` is the plain sentence to show.
  - `POST /scripts/{id}/import/upload` replaces a failed link with an upload ("Upload the video instead").
  - `GET /scripts/{id}/import` is the polled status.
- **Price (to build):** a read estimate for the script, from `seconds`.
- **Reading (to build):**
  - The paid read on the script refuses past an editor's allowance with the reason, and returns the job.
  - The finished read fills A's text (if unedited) and the cast slots (marked `from_reel`).
- **Progress (to build):** the import status grows `stage: listening | shots | breakdown | script | done | failed`, `failed_stage`, the per-stage results (`lines`, `shots`, `dropped`), and `breakdown` (the existing `ReferenceBreakdown` shape plus `style` per shot, so live action is marked).
- **Redo:** a paid re-read with `{note}` is paid (breakdown and script only). The note goes through the same check as clip prompt notes, and dialogue changes are refused with the plain reason.
- **Script and slots:**
  - The script draft gets `edited_since_fill` so the UI knows whether to refill.
  - `POST /scripts/{id}/fill-from-reel` (free) refills it on request.
- **Library:**
  - Imported reels join `GET /references`, with `imported_by` and `created_at`.
  - `PATCH /references/{id} {name}` renames one.
- **Keeping the lines (#271):**
  - The script write takes `new_lines: bool` (default false).
  - With false, it returns the script plus `rewritten: [{line_index, was}]` so the UI can mark rewritten lines. `script_draft.md` and the evals follow the rule: keep the reel's lines, rewrite only what the brand swap needs.
  - `POST /scripts/{id}/write {new_lines}` redoes it (paid).
- **Bulk from links (#271):**
  - `POST /scripts/bulk` accepts `reel_urls[]` (with `new_lines` and `reference_change`). It makes one draft per link and fetches each reel (free), returning per-row `fetch_error?`.
  - `POST /scripts/write/estimate` includes the reading of unread reels in its total and breaks it down (`read_credits`, `write_credits`).
  - `POST /scripts/write` reads and then writes, all or none against an editor's allowance.
