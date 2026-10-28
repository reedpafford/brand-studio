# Next: screen plan (draft for Next-Lead to check against flows.md)

Owner: Next-Screens. Status: **draft**. Song ads only so far; styles, brand setup, video settings, organization and the layout follow.
Built strictly to `docs/next/flows.md` once it lands: where this plan and the flows disagree, the flows win and this file is fixed.

Sources: spec §1 (`docs/research/starpop-2026-10-28/spec.md`), `ops/NEXT.md`, the Current rules in `ops/DECISIONS.md`, and the design rules in `docs/design/redesign/phase3/README.md` (one amber button per area, price inside every paid button, a disabled button says why, status in words, 44px on phones, no sideways scroll at 390).

## How to read this
- Each screen lists its **states**. Each state says **what's on it** and **the one press** that moves the person on (rule 22).
- **390** is a phone; **desktop** is 1024 wide and up (the side rail starts there). Where they differ, both are written.
- "Amber" is the screen's one main button. On desktop it sits top right of the work area; on 390 it is in the action bar above the bottom tabs. That's where the cost bar will go later (layout, step 6), so every paid amber below already has a "what runs · price" label ready for it.
- Prices are whole credits. Editors never see dollars (rule 4). Reed sees the plain button past a budget; his press is the approval. An editor past an allowance gets the button disabled with the reason under it, never "Ask Reed".
- Every failure says what happened, that the credits came back, and offers **Try again** on the same screen. A failure is cleared the moment a new try starts or succeeds; it never sits under a newer good result (the stale-failure pattern from #725, #726, #730).
- No count or "Loading…" from a read made before the step opened (#725, #726): a step shows a skeleton in its final layout until its own read lands, then never flashes back to loading on a later re-read.

---

## Where song ads sit

| Who | Path | What changes |
|---|---|---|
| Owner (or an editor on their own script) writing | Script Library → **New script** → **Song** → Song → Takes → Cast → Breakdown → Publish | Song and Takes replace Script; Directions and Variations don't show for a song (see Questions). |
| Editor making | Script Library → version → **Make this version** → Breakdown → Assets → Storyboard → Clips → Downloads | Same five steps. The song is already made; each step shows the song's timing. |

A song script carries a **Song** badge everywhere it's listed (Library card, In production, Videos), in words, not only an icon.

---

## S1. New script: Story or Song

**Today:** "New script" makes a draft at once and opens it.
**Now:** "New script" asks one thing first.

| | Desktop | 390 |
|---|---|---|
| Opens as | A small menu under the button | A bottom sheet |
| Choices | **Story** "Dialogue and action, as today." · **Song** "Your lyrics, sung word for word, over B-roll." | Same, each a full-width 44px row |

- **One press:** pick one. It makes the draft and opens it at its first step (Script for Story, Song for Song).
- **Failed to make the draft:** the menu/sheet stays open with the reason in red and the same two choices to press again.
- **Double tap:** one draft only (as today).
- **Import a reel** stays as it is (always Story).

---

## S2. Song step (writing): lyrics and style

The first step of a song script. Header, step picker, Back/Next as the Script step today. Steps for a song: **Song · Takes · Cast · Breakdown · Publish**.

### What's on it
- **Lyrics** box (Courier Prime, as scripts are). Helper: "Sung exactly as written. [Verse] and [Chorus] tags are fine." Counter "0 / 5,000".
- **Style** one line. Helper: "Genre, voice, speed and feel, e.g. pop, female lead, 120 BPM, upbeat." Pre-filled from the brand's music style when it has one (brand setup, step 3); empty until then. Counter "0 / 200" (limit to agree with Next-Server).
- **Write 2 song directions for me · 3 credits** (secondary) with the line "From About and the brand. You pick one; nothing is sung yet."
- **About this script** (closed), as today: title, what it's for, notes. Directions are written from it.

### States
| State | What's on it | The one press |
|---|---|---|
| **Empty** (new) | Empty Lyrics and Style (Style pre-filled if the brand has one). Directions button. | Amber **Next: Takes** is disabled, reason "Write or pick the lyrics first". The press is paste lyrics → **Save lyrics**, or **Write 2 song directions for me**. |
| **Typing, not saved** | "Not saved yet" in amber text, **Save lyrics** (primary inside the card), **Discard changes** (ghost). Leaving asks once, as the Script step does today; words kept for the tab. | **Save lyrics**. |
| **Saved: locked** | Lyrics shown read-only with a **Locked · sung word for word** badge. Style shown with **Edit style** (ghost). **Edit lyrics** (secondary). | Amber **Next: Takes**. |
| **Style missing** | Lyrics saved, Style empty. | Amber disabled, reason "Add a style line first", with the Style box focused one press away (**Add style**). |
| **Editing lyrics after takes exist** | Pressing **Edit lyrics** asks: "Edit the lyrics? Your 2 takes will be out of date. They're kept, and you can make new ones." **Keep them** / **Edit lyrics**. | **Edit lyrics** opens the box; saving marks the takes Out of date (S3). |
| **Writing directions** | Card with "Claude is writing 2 song directions… 12 s" (count-up after 1 s). "You can leave this page." Lyrics box stays usable. | None needed; it shows when ready. |
| **Directions ready** | Two cards (S2a). | **Use this one** on a card. |
| **Directions failed** | "The directions didn't finish. Credits were returned." in the card; the button reads **Try again · 3 credits**. Cleared as soon as a new try starts. | **Try again**. |
| **Nothing to go on** | About is empty and the brand has nothing set. Directions button disabled, reason "Say what it's for in About first", with **Open About** (ghost) beside it. | **Open About**. |
| **Over the weekly allowance** (editor's own script) | Directions button disabled: "That's more than this week's 145 credits. It resets on Monday." | Paste lyrics instead (the boxes stay free). |
| **Published** | Lyrics and style read-only, **Published · final** badge, no Edit. The owner can still edit title, about and notes (rule 31). | Amber **Next: Takes** (to listen). |

### S2a. The two directions
| | Desktop | 390 |
|---|---|---|
| Layout | Two cards side by side, same height | Stacked, Recommended first |
| Each card | Title · **Recommended** badge on one · Concept (2 lines) · Style line · Visual concept (2 lines) · Lyrics (first 4 lines, **Show all lyrics** opens them in place) | Same; lyrics closed by default |
| Button | **Use this one** (secondary; it's free) | Full width |

- Pressing **Use this one** copies its lyrics and style into the boxes, saves and locks them. Toast "Using 'Title'." with **Undo** (puts the boxes back as they were).
- If lyrics are already saved, it asks first: "Replace your lyrics with these?" **Keep mine** / **Replace**. When takes exist it adds: "Your 2 takes will be out of date. They're kept, and you can make new ones."
- The cards stay under the boxes (closed, "2 directions · Show") so the other can still be picked; **Write 2 more · 3 credits** under them.
- Claims in a direction that aren't in the brand facts are marked "Not checked" next to the line (as Starpop labels them unverified). Advice only.

---

## S3. Takes step (writing): make the song

### What's on it
- Lyrics (read-only, closed after the first take is made: "Lyrics · Show") and the style line.
- Up to N take cards. Each: an audio player (play/pause 44px, a waveform bar you can tap to seek, time "0:12 / 0:31"), **Take 1** title, length, made at "10:42", and either the **Preferred** badge or **Make this Preferred** (secondary).
- At 390: take cards stacked, full width; the waveform sits inside its card and fits it (no sideways scroll); the seek bar is at least 44px tall; Preferred / **Make this Preferred** under the player, full width. Desktop: two cards side by side, a third and fourth wrap to a new row.
- Before any take exists: "These lyrics make a song of about 0:30 (about 75 sung words)." The likely length comes from the word count, so the person sees it before paying.
- Under the cards: "The song sets the video's length. Take 2 is 0:31, about 34 credits to make the video at 480p." (the estimate follows the Preferred take; credits only).

### States
| State | What's on it | The one press |
|---|---|---|
| **No takes yet** | Empty card: "Make the song. You get 2 takes and pick one." plus the likely length. | Amber **Make 2 takes · up to N credits** (the price depends on the length; the meta line under it says "Usually M. Anything not used comes back.", and the charge never goes over N). Disabled with reason if lyrics or style are missing ("Write or pick the lyrics first", with **Back to Song**). |
| **Making** | Two placeholder cards in the final layout with "Making the song… 0:42" (count-up). "You can leave this page; it carries on." Amber shows **Making…** (busy, not disabled-looking). | None needed. |
| **Stopped by a restart** | "The song stopped when the server restarted. Nothing was charged." Any good takes from before stay above. | **Try again · up to N credits**. |
| **Both made** | Two players. The first is **Preferred** unless Next-Server marks another. | Amber **Next: Cast**. **Make this Preferred** on the other; **Make 2 more · N credits** (secondary). |
| **One made, one failed** | The good take plays and is Preferred. The failed card: "Take 2 didn't finish. Its credits were returned." **Try again · N credits** (if a single take can be made; else it rides **Make 2 more**). | Amber **Next: Cast** (one good take is enough). |
| **Both failed** | Banner: "The song didn't finish. Credits were returned." plus the reason in plain words when the provider gives one. **Try again · N credits**. Old good takes (if any) stay above, still Preferred. | **Try again**. |
| **Refused by the music model** | Banner: "The music model wouldn't make this: {reason}. Nothing was charged." When the provider names the line (a lyric line, or a style line that names an artist), that line is quoted. | **Edit lyrics** or **Edit style**, whichever the reason names (both when it names neither); each opens S2 with that box open. |
| **A line isn't sung** | The take drops or repeats a lyric line (found from the free word timing). On the card: "Line 4 isn't sung in this take." (or "Line 4 is sung twice"). Block or Advice is for flows.md; this plan treats it as Advice on that take. | **Make this Preferred** on the other take when it sings every line; else **Make 2 more · up to N credits**. |
| **Long, under the cap** | Advice under the card: "This take is 1:12, about 78 credits to make the video. Shorter lyrics make a shorter song." | Amber still **Next: Cast**. |
| **Over the per-video cap** (rule 3) | The Preferred take would make a video over 729 credits: amber **Next: Cast** disabled, reason "This take makes a video of about 812 credits; the most is 729." A shorter take, if there is one, says "Fits". | **Edit lyrics** (shorter), or **Make this Preferred** on a take that fits. |
| **Out of date** | After the lyrics or style changed: each old take has an **Out of date** badge (kept, still plays). | Amber **Make 2 takes for the new lyrics · N credits**. Next is disabled: "Make takes of the new lyrics first". |
| **Preferred switched after Breakdown** | Toast: "Take 2 is Preferred. The breakdown was timed to Take 1, so it's out of date." **Undo**. | Next: Cast; Breakdown then shows Out of date (S5). |
| **Allowance** | Editor's own script over the week: amber disabled with the week's reason. Reed: plain button. | — |
| **Published** | Players only, Preferred fixed, no Make. | **Next: Cast**. |

- Deleting a take: in the card's "…" menu, **Delete take**, with Undo. The Preferred one can't be deleted while it's Preferred ("Make another take Preferred first"), nor can the take a breakdown was timed to ("The breakdown is timed to this take. Make the breakdown again first."), so S5's **Go back to Take 1** always works.

---

## S4. Cast (writing)

As today. One difference: the cast is read from the lyrics plus the visual concept (if a direction was used). The singer is a role like any other; if the lyrics have no named person, the cast read proposes "Singer" so Sung shots have a face (to confirm with Next-Server and the Director).

---

## S5. Breakdown, timed to the song (writing preview and the editor's video)

### What's on it
- **Song strip** at the top: the Preferred take's waveform across the full width, with a play button (44px), the playhead, and the shots laid under it as segments. Each segment shows its shot number and **Sung** or **B-roll** in words (Sung segments also filled with the accent, as a second signal).
  - Desktop: segments wide enough to show "3 · Sung"; tapping one scrolls to its shot and plays from its start.
  - 390: the strip fits the width, no sideways scroll; segments show only the number. Tapping one opens that shot. A segment narrower than 44px gets a 44px hit area.
- **Shots** as today, each with: time range "0:06–0:11", the lyric line(s) sung in it (Courier Prime), a **Sung / B-roll** two-way switch (44px), the cast and place chips, and its problems.
- A **Play this shot** button on each shot plays its slice of the song.
- "Made from Take 2 (Preferred) · 0:31" under the strip.

### States
| State | What's on it | The one press |
|---|---|---|
| **No breakdown yet** | Empty: "Time the shots to the song." | Amber **Make the breakdown · N credits** (word timing is free; the Claude call is not). |
| **Reading the timing / making** | Strip skeleton with the real waveform once the file loads; "Timing the shots to the song… 8 s". | None needed. |
| **Made, no problems** | Strip + shots. Default: the hook and the last chorus Sung, the rest B-roll. | Amber **Next: Publish** (writing) / **Next: Assets** (editor). |
| **Problems** | As today ("Fix the 2 problems first"), each with its one-click fix. New ones:<br>• a shot that cuts mid-word ("Shot 4 ends in the middle of 'tonight'.") → **Move to the beat** (free);<br>• a shot that crosses a place or time change (rule 29) → **Split at the place change** (free);<br>• a Sung shot longer than the video model can lip-sync in one clip ("Shot 2 is sung for 14 s; one clip holds 10 s.") → **Split at a beat** (free);<br>• a Sung shot whose singer has no role with a look ("Shot 3 is Sung, but nobody sings in it.") → **Pick the singer** (choose a cast role, free) or **Make it B-roll** (free). The look's approval itself is checked at Assets and blocks Storyboard as today (rule 8), with its one-click way to Assets. | The fix button on each problem. |
| **Advice** | Closed list, never blocks: "No Sung shot. The hero never sings." **Mark the hook Sung**; "The song doesn't end on the brand (rule 18)." | — |
| **Out of date (song changed)** | Banner: "Timed to Take 1. Take 2 is Preferred now." Shots kept, dimmed badge **Out of date**. | Amber **Make it again for Take 2 · N credits**; secondary **Go back to Take 1** (free, sets Preferred back). |
| **Timing failed** | "Couldn't read the song's timing. Nothing was charged." The timing gives the same answer for the same file, so a retry alone may not help. | **Use Take 1** (the other take, free) when there is one; else **Make 2 more takes · up to N credits**. **Try again** (free) stays as a secondary, for a failure the server marks as passing (a restart, say). |
| **Making failed** | As today: "The shots didn't finish. Credits were returned." | **Try again · N credits**. |
| **Read-only (published, or editor where the flows say so)** | Switches shown as text badges. | Next. |

- Who may flip: the owner in the writing preview. In an editor's video this waits on Question 2 (rule 31); until flows.md says yes, the switches are read-only text badges there.
- Flipping Sung/B-roll saves at once (no Save button for a flip), shows "Shot 3 is Sung now." with **Undo**, and marks later steps Out of date if they exist.
- Unsaved shot edits keep the existing "Save your changes first." rule.

---

## S6. Storyboard (editor)

As today, plus:
- Each frame card shows the time range and **Sung** or **B-roll** as a badge, and the lyric line under the picture.
- **Play with the song** (secondary, free): plays the Preferred take while the stills change at each shot's start. Desktop: in a player above the grid. 390: full-width player that sticks under the header while it plays; **Stop** is 44px.
  - While stills are still being made, missing ones show the skeleton with the shot number; the song still plays.
- States, Approve all, Change this…, failures: unchanged.

---

## S7. Clips (editor)

As today, plus on each clip card:
- **B-roll · 0:06–0:11 · picture only** or **Sung · lip-syncs 0:00–0:06** under the title, and the lyric line for Sung clips.
- Takes play **with the song slice** under them (in the browser, free). A small **Song on / off** toggle (44px) per player.
- Sung clips: the prompt panel says, in plain words, that the song slice and the character sheet go in, not a first frame.

| New state | What's on it | The one press |
|---|---|---|
| **Sung take refused / failed** | As today (#728 pattern): what happened, credits returned. | **Make another take** or the free reword. |
| **Lip-sync doesn't match** | No automatic check (rule 11). | **Make another take · N credits** or **Change this…**. |
| **Make this B-roll instead** | Held until flows.md answers Question 2 (rule 31: a published breakdown is final). If allowed: on a Sung clip whose takes keep failing, a secondary button, free; the clip's prompt is rewritten as B-roll and its old takes kept. | — |

---

## S8. Downloads (editor)

As today, plus:
- "Song: Take 2 (Preferred), laid under the whole video." The final MP4 already has the song.
- **Download the song (.mp3)** beside Download MP4.
- Fitting clips to the song: each clip is made for its range rounded up to a whole second, and the stitch trims it to the range, so the song and picture stay in step. A take shorter than its range (a provider cut it short) holds its last frame and shows Advice on that clip in Clips: "Clip 3 is 0.4 s short; its last frame is held." with **Make another take**. Downloads can't open until every clip has an approved take (as today).

| State | What's on it | The one press |
|---|---|---|
| **Putting it together** | As today (free, on open). | — |
| **Out of date** | The Preferred take or a clip changed after the stitch: "Out of date." | **Make it again** (free). |
| **Failed** | "The video couldn't be put together. Nothing was charged." | **Try again**. |

---

## S9. Make this version (editor, Script Library)

The version panel gets the Preferred take's player and its length ("Song · 0:31") above the words. The estimate says "About N credits" (the song is already made, so it costs the editor nothing). **Make this version** is unchanged.

---

## Fields needed from Next-Server (to agree)

| Where | Field | Used by |
|---|---|---|
| Script | `kind: "story" \| "song"` | S1, the Song badge, which steps show |
| Script version | `style_line` (and its limit) | S2 |
| Brand | `music_style` (may be empty) | S2 pre-fill |
| Directions | job + 2 options: `title, concept, lyrics, style_line, visual_concept, recommended, unchecked_claims[]`; estimate | S2a |
| Song takes | list per version: `id, number, file_id, seconds, made_at, preferred, out_of_date, status, failed_reason`; make (2) with estimate; make one; set preferred (with undo); delete (with undo) | S3 |
| Song take waveform | a small array of peaks (e.g. 200 numbers) so the strip draws without decoding the file on a phone | S3, S5 |
| Breakdown shot | `start, end` (seconds in the song), `sung: bool`, `lyric` (the words sung in it), made-from take id | S5, S6, S7 |
| Breakdown | `song_take_id` it was timed to, so "Out of date" is decided by the server | S5 |
| Clip | `song_slice: {start, end} \| null` | S7 |
| Final video | `song_take_id` | S8 |
| Jobs | step names for directions, song takes, timing; refusal reason in plain words | all waiting and failed states |

## Questions for Next-Lead (answer in flows.md)
1. Do Directions (camera suggestions) and Variations (B/C versions) show for a song? This plan hides both.
2. Can an editor flip Sung/B-roll in their video's Breakdown, or is that final once published (rule 31)?
3. Is the singer always a cast role, and who adds "Singer" when the lyrics name nobody?
4. One take or always two per press? (MiniMax may return one; Suno returns two.)
5. Song length: this plan blocks Next over the per-video cap (rule 3) and gives Advice below it. Is 2x the budget also a block?
6. A take that drops or repeats a lyric line: Advice on that take (this plan) or a block?
