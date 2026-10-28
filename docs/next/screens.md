# Next: screens (layout companion to flows.md)

Owner: Next-Screens. **`docs/next/flows.md` is the source of truth** for every step, state and press; this file never restates a state table. It adds only what the flows leave to the screens: the layout at 390 and on desktop, which existing parts each screen reuses, and wording settled with QA-2 and Flow-QA. Where the two ever disagree, the flows win and this file is fixed.

Ids below are the flows' (S1–S7 owner, V1–V6 editor).

## Rules every song screen follows
- Design rules from `docs/design/redesign/phase3/README.md`: one amber button per area (desktop: top right of the work area; 390: the action bar above the tabs), the price inside every paid button, a disabled button says why on the line under it, status in words, 44px controls on phones, no sideways scroll at 390.
- Every paid amber already reads "what runs · price" so the cost bar (layout, item 6) can take it over unchanged.
- Credits only for editors (rule 4); the owner never sees dollars on these screens either.
- No stale failures: a failure is cleared as soon as a new try starts or a later result lands (#725, #726, #730). No counts from a read made before the step opened; a skeleton in the final layout until the step's own read lands.
- Prices come from the server's estimate, never hard-coded. Today a song take is 1.46 credits, shown rounded up: **Make 2 takes · 3 credits**, a single take's **Try again · 2 credits**.

## S1. New script: Story or Song
| | Desktop | 390 |
|---|---|---|
| Opens as | A menu under **New script** (Esc or a click outside closes it) | A bottom sheet with a 44px **Close** at the top |
| Choices | **Story** "Dialogue and action, as today." · **Song** "Your lyrics, sung word for word over a music video." | Same, stacked, each a full-width 44px row |

- Reuses `NewScriptButton` (one draft per press, double-tap safe) and `Menu` / `Sheet`.
- Library: a **Song** badge (in words) on song cards and a **Song** filter chip beside the existing filters.

## S2. Song: lyrics and style
- The writing frame is `ScriptFlowPage` with a step list per kind: song scripts show **Song · Takes · Cast · Breakdown · Publish**; Directions and Variations are not in the picker.
- **Lyrics** box: today's Script-step editor (explicit **Save lyrics** / **Discard changes**, words kept for the tab, leaving asks once), Courier Prime, grows with its text; counter "0 / 3,500" and the live "About 30 s sung · 75 words" under it. At 390 the word count stays visible above the action bar.
- **Style** box: grows as it wraps (one line to start, up to 4 at 390, then scrolls inside itself); counter "0 / 2,000"; placeholder "pop, female lead, 120 BPM, upbeat, modern polished".
- Saved: the lyrics read only (Courier Prime) with a "Sung word for word" badge and **Edit lyrics** (secondary); with takes, Edit lyrics asks first (the flows' wording).
- Over 3,500 characters: the counter says "Cut 120 characters"; the words stay in the box; saving waits until it fits.
- Advice (long style, long song, no end line) uses today's Advice list look, closed by default, each with its free button (**Shorten it**, **Sing the end line**, **Speak it over the end**). A spoken end line shows as one row under the boxes with **Edit** and **Remove**.
- **Write 2 song directions for me · about 3 credits** is secondary, under the boxes.

## S3. The two directions
| | Desktop | 390 |
|---|---|---|
| Layout | Two cards side by side, equal height | Stacked, Recommended first |
| Card | Title · **Recommended** badge on one · concept · style · visual concept · first 4 lyric lines with **Show all lyrics** in place | Same; lyrics closed |
| Press | **Use this one** (secondary, free) | Full width |

- After a pick the cards fold under a "Directions · 2" row (open/close) and stay until deleted; **Write 2 more · about 3 credits** sits under them.
- Writing: "Writing 2 directions… 12 s" (count-up after 1 s) and "You can leave this page."
- A direction whose lyrics are over 3,500 characters opens in the box unsaved, with "Cut N characters".

## S4 and V2a. Takes
| | Desktop | 390 |
|---|---|---|
| Take cards | Two side by side; more wrap to new rows | Stacked, full width |
| Each card | 44px play/pause, the waveform from the take's `peaks` as the seek bar (tap or drag to seek), "0:12 / 0:31", **Take 1**, made at "10:42", the **Preferred** badge or **Make this the preferred one** (secondary), and a "…" menu with **Delete** | Same; the seek bar is at least 44px tall; the Preferred row is full width under the player |
| Labels | "Sings older words" / "Older style" (grey badge), "Reading the song's timing…", "Timing guessed": always in words, never colour alone | Same |

- Only one take plays at a time (starting one pauses the other).
- The waveform never decodes audio in the browser: it draws the server's 200 peaks.
- A take whose timing failed leads with **Use timing spread evenly** (free) or **Make this Preferred** on the other take; **Try again** (free) is secondary, and hidden when `retry_helps` is false.
- **Make this Preferred** is disabled with its reason while a take's timing is still being read, or when it sings older words.
- V2a in the editor's Breakdown: a one-row strip (play, "Song: take 2 · 0:31", **Change song** secondary). **Change song** opens a side panel on desktop and a full-screen sheet with a 44px **Close** at 390, holding the same take cards; the current one is marked **In this video**.

## S5. Cast: the Singer card
- A card on top of today's Cast step: "Who sings on camera?" as a radio list of 44px rows: the roles, the brand's default cast, **Nobody on camera**. Desktop: one column, 480px wide; 390: full width.

## S6 and V2. Breakdown on the song
- **Song strip** above the shots: the take's waveform across the full width, a 44px play button, the play head, and the shots as segments under it, each labelled with its number and **Sung** or **B-roll** in words (Sung also filled with the accent). Tapping a segment scrolls to its shot and plays its stretch.
  - 390: the strip fits the width; segments show only their number; a segment under 44px gets a 44px hit area, and neighbours whose hit areas would overlap group into one target that opens a small list of their shots.
- **Shot rows** (today's `BreakdownView` rows) gain the time range "0:00–0:04", the sung words (Courier Prime), a **Sung / B-roll** two-way switch (44px), **Play this shot**, and **Split here** / **Join with next** in the row's menu. Instrumental stretches show as "Music · 0:12–0:16" rows.
- Split: **Split here** turns the shot's words into tappable gaps; the chosen gap splits it (free, Undo).
- Problems and Advice use today's lists and their one-click fixes.

## S7 and V1. Publish and Make this version
- The version card gains a compact player row, "Song: take 2 · 0:31" with a 44px play button, then the Singer, then the rest as today.
- V1's price line: "About N credits to make · 0:31 song".

## V4. Storyboard
- Each frame card shows its time range and a **Sung** or **B-roll** badge, the sung line under the picture, and on Sung frames the note "Sung: used as a reference, not the first frame."

## V5. Clips
- A clip with a Sung shot shows "Lip-syncs 0:00–0:06" under its title, with a small player of that stretch (44px play).
- Takes play with their song stretch under them (in the browser, free), with a **Song on / off** toggle (44px) per player.

## V6. Downloads
- Layout as today plus "Song: take 2, laid under the whole video" and **Download the song** (secondary) beside **Download MP4**. A spoken end line shows as "Spoken at the end: '…'".

## Fields (agreed with Next-Server; the tables are in `docs/next/data.md`)
| Where | Field |
|---|---|
| Script | `kind: "story" \| "song"` |
| Version | lyrics as `text` (≤ 3,500), `style_line` (≤ 2,000), `song_directions[]`, `singer`, `spoken_end_line` |
| Song take | `id, number, file_id, seconds, made_at, preferred, status (making \| timing \| ready \| failed \| timing_failed), failed_reason, retry_helps, peaks, project_id`, plus the flows' labels (older words, older style, `trim_to`, advice) |
| Breakdown shot | `start, end, sung`, the sung words; breakdown `song_take_id` |
| Video | `song_take_id` |
| Clip | `song_slice` |
| Final video | `song_take_id` |
| Jobs | steps `song_directions`, `song_take`, `song_timing` |

## Build order (one PR each, into `next`)
1. **S1 + S2 + S3**: the Story/Song choice, the song step list, Lyrics and style with their Advice, the two directions.
2. **S4**: takes, Preferred, delete, too long, refused, songs off.
3. **S5 + S7 + V1**: the Singer card, the song on Publish and on Make this version.
4. **V2a + V2/S6**: the song strip, Change song, Sung/B-roll, split and join.
5. **V4 + V5 + V6**: storyboard, clips and downloads on the song.

Each PR has vitest at 390 and desktop and a Playwright walk on the free stand-ins.
