# Brand Studio Next: the flow map

Every flow, step by step, with every state. Nothing on Next is built before its flow is here, and every PR into `next` names the flows it touches (by their ids, e.g. **S3**) and what it changes for later steps. Flow-QA walks this file on the test site.

Sources: the spec (`docs/research/starpop-2026-10-28/spec.md`), Reed's changes (`ops/NEXT.md`), the Current rules (`ops/DECISIONS.md`). Where this file decides something the spec left open, it says **Decided here** and the Producer can overturn it.

## How to read a step

Each step has a table of states. Every state says **what the person sees** and **the one press that moves them on** (rule 22: never a dead end; editing a raw prompt is never the only way out). The states every step is checked for:

| Code | State | Meaning |
|---|---|---|
| E | Empty | Nothing made yet |
| L | Loading | The page is reading what exists |
| Q | Waiting | Pressed, not started yet (in the queue) |
| R | Running | Being made |
| F | Failed | The service didn't finish it |
| X | Refused | The model said no (safety, policy, a name it won't use) |
| B | Over budget | Over the video's budget, the editor's week, or the $75 cap |
| O/Ed | Owner vs editor | What differs by role (owner sees dollars only in Usage; editors see credits, rule 4) |
| P | Phone | 390 wide: no sideways scroll, controls at least 44px, the one amber button in the bottom bar |
| U | Back / Undo | Going back a step, undoing, deleting |
| S | Out of date | An earlier step changed after this one was made |

Words in "quotes" are what the screen says. They are a starting point for Next-Screens; keep the meaning, polish the words.

Shared behaviour (as today, so not repeated in every table):
- **Loading** shows the step's outline with grey placeholders, never a blank page and never a count read before the step opened (#725).
- **Waiting** shows "Waiting to start" with a timer. After 10 minutes: "This hasn't started yet: the service that makes it isn't taking work right now. It's charged only if it runs." Press: **Cancel** (only before it starts).
- **Leaving the page** never stops anything: jobs run on the server, and the step shows the result when the person comes back.
- **Failed** always says "Nothing was charged" (or "credits returned") and offers **Try again** on the same screen.
- **Undo** sits in the toast for 8 seconds after any delete, replace, pick or Approve all.
- **Price first:** every paid button shows its price ("· 4 credits", or "free"), and the charge lands within that quote ("up to N" when it can vary; anything unused comes back). A charge above its quote is a bug for Flow-QA to file.
- **Server restart** mid-job: "The server restarted while this was being made. Nothing was charged; try again." with **Try again**.
- **Over budget, editor:** the paid button is disabled with the reason as its label ("That's more than this video's budget."); the free alternatives on the screen stay pressable. Past the week: "You've used this week's N credits. It resets on Monday." Never "Ask Reed".
- **The cap** ($75, 729 credits) stops everyone, owner included: "This video would go over its limit."

---

# 1. Song ads (build first)

**The idea in one line.** The owner pastes lyrics (or picks one of 2 AI directions), makes the song, picks the preferred take, and publishes. An editor makes the video: the breakdown is timed to the real song, most shots are B-roll under the song, and only the shots marked **Sung** lip-sync. The final video lays the whole song underneath.

**The lyrics are the script** (rules 19 and 31). The AI never changes them. They change only when the owner types, or presses a button that says it replaces them (picking a direction).

## Map

```mermaid
flowchart LR
  subgraph Owner["Owner: writing a song script"]
    N[S1 New script: Song] --> L[S2 Song: lyrics + style]
    L -. optional .-> D[S3 Write 2 song directions]
    D --> L
    L --> M[S4 Takes: make the song, Preferred]
    M --> C[S5 Cast: who sings]
    C --> BP[S6 Breakdown preview]
    BP --> P[S7 Publish]
  end
  subgraph Editor["Editor: making the video"]
    P --> V[V1 Make this version]
    V --> B[V2 Breakdown on the song]
    B --> A[V3 Assets]
    A --> SB[V4 Storyboard]
    SB --> CL[V5 Clips: Sung and B-roll]
    CL --> DL[V6 Downloads: song underneath]
  end
```

Owner steps on a song script: **Song → Takes → Cast → Breakdown → Publish** (the names Next-Screens uses in docs/next/screens.md). "Write 2 song directions" is a button inside Song, not a step. Variations are not offered on a song script (they would rewrite the words); to try other lyrics, the owner duplicates the script. **Decided here.**

Editor steps: the same five as a story video (**Breakdown → Assets → Storyboard → Clips → Downloads**).

## S1. New script: choosing Song

Where: Script Library → **New script**.

| State | What they see | The one press |
|---|---|---|
| E | Two choices: **Story** (as today) and **Song** ("Your lyrics, sung word for word over a music video"). | **Song** → a new draft opens on its Song step. |
| O/Ed | Both roles see it. An editor's song script is their own script: everything paid on it counts against their week (rule 5). | — |
| P | The two choices stacked, full width. | — |
| U | Back leaves an untouched draft behind? No: an empty draft is not saved until the first word is typed (as today). | Browser back returns to the Library. |
| Library | Song scripts carry a **Song** tag in the Library list and a "Song" filter chip. | Tapping one opens it on its first unfinished step. |

Out for now: Bulk create and reel import make Story scripts only. A pasted reel that is a song ad is imported as a Story (its words become the script). **Decided here**; reel-to-song is a later item.

## S2. Song: lyrics and style

Two boxes and one button.

- **Lyrics.** Paste or type. `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]` tags are fine; they are not sung and don't count. Under the box, live: "About 30 s sung · 75 words" (2.5 words a second, Starpop's rule).
- **Style.** One line: genre, voice, tempo, mood, sound. Pre-filled from the brand's music style (spec item 3). Until brand setup exists, it starts empty with an example placeholder: "pop, female lead, 120 BPM, upbeat, modern polished".
- **"Write 2 song directions for me · about 3 credits"** (S3).

| State | What they see | The one press |
|---|---|---|
| E | Both boxes empty; Next is disabled with "Write or pick the lyrics first". | Type, or **Write 2 song directions for me**. |
| L | The boxes with placeholders. | — |
| Typing | "Not saved yet" with **Save lyrics** (and **Discard changes**). Leaving with unsaved words: "Leave without saving? The lyrics you changed are not saved." Stay / Leave. | **Save lyrics**, then **Next: Takes**. |
| Saved | The lyrics read only with "Sung word for word", and **Edit lyrics**. When takes exist, Edit lyrics asks first: "Edit the lyrics? Your 2 takes will be out of date. They're kept, and you can make new ones." | **Next: Takes**. |
| Nothing to go on | About is empty and the brand has no facts: the directions button is disabled with "Say what it's for in About first". | **Open About**. |
| Style empty | Never a block. Next stays allowed and the takes use the brand's music style, else the default; Advice under the box: "No style yet: the song will be upbeat pop by default." | **Next: Takes**. |
| Advice: long style | Over 25 words: "Music models follow short styles better. Keep it under 25 words." Advice only. | **Shorten it** (free, cuts in code to the first 25 words, Undo). |
| Advice: long song | Over about 150 words: "About 70 s sung. That's a long ad: the video will be about that long too." Advice only. | — |
| Advice: no end line (rule 18) | The lyrics don't name the brand or where to find it: "The song doesn't say fomo or where to find it." Advice only. Two ways to meet it, either one: | **Sing the end line** (free: adds the brand's end line as a last `[Outro]` line; the owner can edit it; Undo), or **Speak it over the end** (free: the brand's end line, editable, is spoken over the song's last seconds with the music lowered under it; see V6). |
| Spoken end line set | Under the boxes: "Spoken at the end: 'Download fomo through the link in my bio.'" with **Edit** and **Remove** (Undo). | — |
| B (too long for the cap) | The sung length would make a video over 729 credits: "A song this long would go over the video limit. Cut it to about N words." This blocks **Make the song** only. | The owner cuts words; the count updates live. |
| O/Ed | Same for both. An editor's own script: the price lines show their week ("This week: U of A"). | — |
| P | Boxes full width, the Lyrics box grows with its text; the word count stays visible above the bottom bar. | — |
| U: lyrics changed after a song exists | See **Effects of changes** below: takes that sing other words are marked "Sings older words". | — |
| Published | Read only, with "Published · final" (rule 31: the lyrics are the script's lines). | — |
| "Locked" means | The AI never changes the lyrics. The owner types freely until publishing. There is no lock to undo. | — |

## S3. Write 2 song directions (optional)

Pressed on S2. Uses the brand, the product and anything already typed (as a brief, not as lyrics to keep).

| State | What they see | The one press |
|---|---|---|
| Q/R | "Writing 2 directions…" with a timer. "It shows here when it's ready. You can leave this page." | Cancel (before it starts). |
| Done | Two cards side by side (stacked on a phone): title, concept, lyrics, style, visual concept. One is marked **Recommended**. | **Use this one** on a card. |
| Use this one, boxes empty | Its lyrics and style fill the boxes. Toast: "Option B's lyrics are in. They're yours now: the AI won't change them." Undo. | **Next**. |
| Use this one, boxes have words | Confirm: "Replace your lyrics with option B's? Your words are kept in Undo." Not yet / Replace. | **Replace**. |
| Neither fits | Under the cards: **Write 2 more · about 3 credits** and "Or write your own above." | Either. |
| F | "The directions didn't finish. Nothing was charged." | **Try again**. |
| X | Claude refuses (e.g. a health claim): "Claude won't write this: [its reason, one line]." | **Try again** with the reason's free repair when there is one, else the owner types their own. |
| B | Editor past the week: the button says why and is disabled. Typing lyrics is always free. | Type the lyrics. |
| U | The directions stay on the page (collapsed under "Directions") until the owner deletes them; they're never used without **Use this one**. | — |

Rule 19 holds: directions are suggestions. Nothing the AI writes reaches the lyrics without **Use this one**, and once in, only the owner changes them.

## S4. Takes: make the song

| State | What they see | The one press |
|---|---|---|
| Locked | Step label: "Write or pick the lyrics first". | Goes to Song. |
| E | "Make 2 takes · N credits". Under it: "Each take is a full song. The song sets the video's length." | **Make 2 takes**. |
| Q/R | Two player placeholders: "Making the song…" with a timer. | Cancel (before it starts). |
| Reading timing | After a take arrives, free, on the local lane: "Reading the song's timing…" on that take. The player already plays. | — |
| Done | Two players. Each shows its length ("0:31") and **Preferred** on one: the first take whose timing is read, until the owner picks. | **Next: Cast**, or **Make this Preferred**, or **Make 2 more · N credits**. |
| Timing still reading | That take's **Make this Preferred** is disabled with "Reading the song's timing…"; it turns on by itself when the timing is read. | — |
| Timing failed | "Couldn't read this take's timing. Nothing was charged." Reading again gives the same answer for the same file, so the fixes don't depend on it. | **Use timing spread evenly** (free: the lines are spread over the take's length in order, each shot marked "Timing guessed"; the take can then be Preferred), or **Make this Preferred** on the other take. **Try again** (free) stays as a secondary press. |
| Advice: words off | Timing found lines the singer skipped or slurred: "The singer skips 'every single bowl' at 0:12." Advice only (rule 19 binds us, not the singer). | **Make 2 more**, or keep it. |
| Advice: sung twice | A line is sung twice: "Line 4 is sung twice in this take." Advice only; the shots follow the first time it's sung and the repeat rides in the shot after it. | **Make 2 more**, or keep it. |
| Advice: instrumental intro | Over 2 s before the first word: "This take starts with 4 s of music before the singing." Advice. At the stitch the head is trimmed to 0.5 s automatically (free). | — |
| Too long (after) | A take came out longer than the lyrics promised and a video of it would go over the cap: "This take is 1:12: a video of it would go over the limit." | **Use the first 0:55** (free: the take is trimmed at the last section end that fits, never mid-word, and the trimmed take becomes the one used; the full take is kept). |
| F | Per take: "This take didn't finish. Credits returned." | **Try again** (makes that take again at its price). |
| X | The music model refused: "The music model won't sing this: [reason]". The common one is an artist's name in the style line: "Music models refuse artists' names. Describe the sound instead." The fix is always in the style line or a retry, never in the lyrics (rule 19). | **Use the brand's style instead** (free, swaps the style line for the brand's music style or the default, Undo, then Make 2 takes again at its price). If the refusal is about the words themselves: "The music model won't sing these words: [reason]." The owner, on a draft, gets **Edit lyrics** (their own typing; the AI never rewords) and **Try again** (some refusals don't repeat). In a video (V2a), the lyrics are final, so the press is **Use this take** on another take, or **Try again**. |
| Songs off | No music service on this site (the test site without a music key, or the stand-ins off): "Songs aren't switched on here." in place of the button. Lyrics, style and directions still work. | — |
| Too long (before) | The price line under the button covers the song and the clips it implies: "2 takes · N credits. A video this long: about M credits to make." Over the 729-credit cap: the button is replaced by the fix. | **Keep the first N lines** (free: cuts the lyrics at the last section that fits, shown before/after, Undo), then Make 2 takes. |
| B | Owner: only the cap stops them. Editor's own script: the week. | Disabled button with the reason; the existing takes stay playable and pickable. |
| O/Ed | The same; dollars never shown. | — |
| P | Players stacked, full width; each has a 44px play button and its Preferred toggle as a full-width row under it. | — |
| U: delete a take | **Delete take** in the take's menu; Undo. Guards, each with its press: the Preferred take can't be deleted ("Make another take Preferred first", with **Make this Preferred** on the other take right there; when the other takes sing older words: "Make takes of the new lyrics first", with **Make 2 takes**). A take a video uses can't be deleted ("Video 'Pitbull song' uses this take"); takes on a published script aren't deletable at all. | — |
| U: change Preferred | Moves Preferred; a breakdown preview made on the other take goes out of date (S). | — |
| S | A take made before the lyrics or style changed: grey label "Sings older words" (or "Older style"). It can't be Preferred. | **Make 2 takes** for the new words. The old ones stay playable, and deletable. |
| Published | Read only for the owner. The preferred take becomes each new video's starting song; every published take is offered to editors in their video (V2a), where the choice is theirs (rule 31). | — |

**Decided here:** a take is tied to the exact lyrics and style it was made from. Only a take that sings the current lyrics can be Preferred. That keeps rule 19 true all the way to the final cut.

Takes per press: always 2 (two calls to the music model, priced as two). One take can be remade alone with its own **Try again**.

## S5. Cast: who sings

As today's Cast step, with one addition: **the Singer**.

| State | What they see | The one press |
|---|---|---|
| Locked | "Make the song first" (no preferred take yet). | Goes to Takes. |
| E / reading | The cast read runs on the lyrics and the visual concept (free reading as today). Roles named in the lyrics or concept appear. | — |
| Singer | A card on top: "Who sings on camera?" with the roles, the brand's default cast, or **Nobody on camera** (all shots B-roll). The Singer is always a cast role. Pre-picked: the hero from the visual concept, else the brand's default cast's first character. When the lyrics and concept name nobody, the cast read adds a role named **Singer** automatically (its look is made per video at Assets, rule 7). | Pick, then **Next**. |
| Nobody on camera | Advice: "No shot will lip-sync. The song plays over B-roll only." | — |
| Rest | Exactly as today's Cast (lock to a library look, or "made at Assets"). | — |
| U | Changing the Singer after a breakdown preview marks it out of date (S6 S). | — |
| P | As today. | — |

## S6. Breakdown preview (owner, optional as today)

Same step as the editor's Breakdown (V2), made by the owner from the preferred take. If the owner skips it, it runs when the editor starts (as today), using the published preferred take.

| State | What they see | The one press |
|---|---|---|
| Locked | "Make the song first". | Goes to Takes. |
| Take changed | Preferred moved to another take of the same lyrics: the times re-flow to it in code, free, with Undo (as V2a). Nothing to press. | — |
| S | The lyrics, style or Singer changed after it was made: "Out of date: the song changed." | **Make it again · N credits** (as today). |
| Everything else | As V2. | — |

## S7. Publish

| State | What they see | The one press |
|---|---|---|
| Locked | "Make the song first" / "Pick the preferred take first" (a take exists, none singing the current words). | Goes to Takes. |
| Ready | The version card lists: Lyrics, Style, **Song: take 2 · 0:31** (a small player), Singer, Cast, Breakdown. Note: "Publishing makes this ready to make. After that the lyrics can't change (each video still picks its own take). To change the lyrics, duplicate the script." | **Publish**. |
| Confirm | "Publish {title}? Its lyrics become final." Not yet / Publish. | **Publish**. |
| Published | "Published · final". Only **Duplicate script** (copies lyrics, style and all takes, Preferred kept). The owner can still edit title, about and notes (rule 31). | — |

Not on song scripts: the Story flow's **Directions** (camera suggestions) and **Variations** steps are hidden. "Write 2 song directions" (S3) is the only writing help.

## V1. Make this version (editor)

As today. The price includes the song's Sung clips; the song is already paid.

| State | What they see | The one press |
|---|---|---|
| Ready | "Make this version · free" (breakdown saved) or "· N credits". Under it: "About N credits to make · 0:31 song". | **Make this version** → Breakdown. |
| B | "That's more than this week's N free credits…" (own script) or the video budget reason. | — |
| Taken | "{name} is making this version." | — |

## V2a. The song in this video (top of the editor's Breakdown)

A strip above the shots: the video's song (a player and its length) and **Change song**. The choice of take is the video's own (rule 31); the lyrics are not.

| State | What they see | The one press |
|---|---|---|
| Default | The published preferred take: "Song: take 2 · 0:31". | — |
| Change song | A sheet with every published take and any this video made, each with a player and length; the current one marked **In this video**. | **Use this take**. |
| Use this take, shots exist | Confirm: "Use take 1? The shots keep their lines and Sung marks; their times move to take 1 (free). Clips already made for take 2 go out of date." Not yet / Use it. | **Use it** (free re-timing in code, Undo). |
| Make 2 more | In the sheet: **Make 2 more takes · N credits** (the same lyrics and style; billed to this video's budget, or the editor's week on their own script). States as S4 (waiting, running, timing, timing failed, refused). | — |
| Too long | A take whose video would go over the cap: "Too long for this video" and its **Use this take** is disabled with that reason; the current take stays. | **Use the first 0:55** on that take (free, as S4), which makes it usable. |
| Delete | A take this video made can be deleted (Undo), except the one the video uses. Published takes can't. | — |
| B | The make button is disabled with the reason; the existing takes stay usable. | **Use this take** on an existing one. |
| P | The strip is one row (play, "0:31", Change song); the sheet is full screen, takes stacked. | — |

## V2. Breakdown on the song

The shots are built from the preferred take's word timings. Each shot covers a stretch of the song, from one word boundary to another (never mid-word), and is marked **Sung** or **B-roll**. Default: the hook (first line or two) and the last chorus are Sung, everything else B-roll. Instrumental stretches get B-roll shots of their own ("Music · 0:12–0:16"). The shots cover the song from its first word to its end with no gaps.

Desktop: the song's waveform across the top, the shots as blocks under it, a play head. Phone: the waveform fits the width (no sideways scroll), and the shots are a list under it; tapping a shot plays its stretch.

| State | What they see | The one press |
|---|---|---|
| E | "No shots yet". | **Make shots · N credits**. |
| R | "Planning shots to the song…" with a timer. | — |
| Done | Shot rows: time range ("0:00–0:04"), the sung words, **Sung** or **B-roll** badge, who's in it, where. | **Next** (Assets). |
| Flip | Each row has a **Sung / B-roll** switch. Sung needs the Singer in the shot: flipping a shot without the Singer adds the Singer to it (said in the toast, Undo). | — |
| Flip, nobody sings | The script said "Nobody on camera", so this video has no Singer yet. Flipping a shot to Sung opens "Who sings in this video?" with the video's roles. | Pick one: it becomes this video's Singer (per video; the script is unchanged) and is added to the shot. A role with no look goes to Assets as usual (rule 8). |
| Edit timing | No free dragging. A row has **Split here** (at a line or word gap the owner picks from the words) and **Join with next**. The times follow the song. | — |
| Problems | As today ("Fix the N problems in Breakdown first"), each with its one-click fix. New ones: "This shot crosses a place change" (rule 29) with **Split at the change** (free); "A Sung shot is longer than one clip can be" with **Split it** (free). | The fix. |
| Advice | "No shot is Sung" (when the Singer exists). "The last chorus isn't Sung." Advice only. | — |
| F | "The shots didn't finish. Nothing was charged." | **Try again**. |
| X | Claude refuses: the reason, plus **Try again**. | — |
| B | As today. | — |
| O/Ed | The editor edits their video's breakdown, as today: Sung or B-roll, split and join are theirs (rule 31). The lyrics can't change. A flip that changes a clip's price shows the new price on that clip's **Rewrite clip prompts** before anything is made. | — |
| U | Every flip, split and join has Undo. | — |
| S | The video's take changed (V2a): times re-flow for free; nothing else goes out of date in Breakdown. The owner can't change a published script, so an editor's video is never pulled out of date from outside. | — |
| Timing guessed | A line the take skipped or slurred has no measured time: its shot shows "Timing guessed" (Advice). | **Change song** to another take, or keep it. |

Clips follow scenes, not shots (rule 29): consecutive shots in one place and one action become one clip, as today. The song is sliced to fit each clip, never the clip to the song. A clip that holds a Sung shot lip-syncs only that shot's stretch; its other shots in the same clip are picture.

## V3. Assets

As today. The Singer is a role like any other and needs an approved look (rule 8): Storyboard and Clips stay locked with "Approve every asset first (N left)" and the one press to Assets, exactly as today. Nothing new.

## V4. Storyboard

As today: one still per shot. For Sung shots the still is used as a reference picture, not the first frame (Seedance can't take a first frame and an audio slice together). The frame card says so: "Sung: used as a reference, not the first frame."

| State | What they see | The one press |
|---|---|---|
| S | A shot flipped Sung ↔ B-roll after the still was made: the still is kept (it's the same picture), but its clip goes out of date (V5 S). | — |
| Everything else | As today. | — |

## V5. Clips

As today (prompts reviewable, "Looks good", takes, pick, Approve all), plus:

- A clip with a Sung shot shows "Lip-syncs 0:00–0:06" and a small player of that stretch.
- B-roll clips are made with sound off, as today.
- The clip's length is its song stretch, rounded up to what the video model accepts; the extra is trimmed at the stitch.

| State | What they see | The one press |
|---|---|---|
| Sung, done | The take plays with the song stretch. | Pick, approve, as today. |
| Advice: lip-sync drift | Not checked automatically (rule 11). The editor watches. | **Make another take**, or **Change this…**. |
| X | As today's refusal messages, naming the character (rule 23), with the free reword (#728). | **Reword and try again** (free). |
| S | The shot flipped Sung ↔ B-roll, or split/joined: "Made for an older breakdown". | **Rewrite clip prompts · N credits** (as today); old takes kept. |
| Sung keeps failing | A Sung clip whose takes fail or refuse: **Make this B-roll instead** (free: flips its Sung shots in this video's breakdown and rewrites the clip as B-roll; old takes kept; Undo). | — |
| Everything else | As today. | — |

## V6. Downloads: the song underneath

The final video is stitched as today (free), and the preferred take's full song is laid underneath. The clips' own sound is dropped, so the song is the only sound: the lip-sync clips were made from the same song, so they match. The picture is trimmed to the song's length; if the picture is short, the last shot holds its final frame.

| State | What they see | The one press |
|---|---|---|
| Done | The player, "Song: take 2, laid under the whole video", **Download MP4**, **Download the song**, **Download all clips (.zip)**. | — |
| F | "The video couldn't be put together. Nothing was charged." | **Try again**. |
| S | As today ("A clip changed since this video was made. It's free."), and also when the video's take or spoken end line changed. | **Make it again**. |
| Spoken end line | When set (S2), it's spoken over the song's last seconds with the music lowered under it (free, in the stitch). | — |
| Lengths | A take longer than its song stretch is trimmed to it; a shorter one holds its last frame to fill it. Never a gap, never silence. A clip with no approved take blocks the stitch as today: "Approve every clip to make the video (N left)." with the press to Clips. | — |

## Effects of changes (song ads)

What happens to later steps when an earlier one changes. "Out of date" items are always kept, never deleted, and always offer the press that brings them up to date.

| Change | Takes | Breakdown | Stills | Clips | Final video |
|---|---|---|---|---|---|
| Lyrics edited (owner, draft) | Takes singing the old words: "Sings older words", can't be Preferred | Preview out of date | — | — | — |
| Style edited | "Older style" (still playable, can't be Preferred) | Preview out of date | — | — | — |
| Preferred take changed (owner, draft) | — | Times re-flow, free, Undo | — | — | — |
| Video's take changed (editor, V2a) | — | Times re-flow, free, Undo | Kept | Clips out of date | Out of date |
| Singer changed | — | Preview out of date | — | — | — |
| Published | The lyrics are fixed; takes become each video's choice | The published preview is each new video's start | — | — | — |
| Shot flipped Sung ↔ B-roll (editor) | — | Saved, Undo | Kept | That clip out of date | Out of date |
| Shot split or joined | — | Saved, Undo | New shot needs a still; others kept | Clips touching it out of date | Out of date |
| Look changed at Assets | — | — | Redrawn as today | Out of date as today | Out of date |
| New take picked in Clips | — | — | — | — | Out of date ("Make it again", free) |

---

# 2. Style registry (build second)

**The idea.** A style is a config file, not code. The **House style** (our current look) is the default and stays on. Starpop's styles are added as entries, in Reed's order: **Disney Pixar, Song, Zack D, Skeleton**, then the rest. Each entry is either a **look** (how pictures are drawn: works with any script) or a **format** (it changes the flow: Song, and later voiceover-led ones). An entry is **On** (editors can pick it) only after Reed has approved a sample.

## ST1. Picking a style (on a script)

Where: the script's header, next to the title ("Style: House ▾"). Story and Song scripts both have it. It defaults to the brand's default style (item 3), else House.

| State | What they see | The one press |
|---|---|---|
| E | "Style: House" (the default). | Tap → the picker. |
| L | The picker's cards as grey tiles. | — |
| Picker | Cards with one sample still each, name, one line ("Soft 3D feature-film look"). House first, then Reed's order. Off entries show **Off** for editors and are greyed: "Not switched on yet". | **Use this style** on a card. |
| Owner sees Off entries | Owner can pick an Off entry on their own draft to try it, labelled "Off for editors: only you can use it". | **Use this style**, or **Switch on for editors** (only once a sample is approved, ST3). |
| Publishing on an Off style | Publish says first: "Claymation is off for editors, so they couldn't make this." | **Publish on House instead** (free, Undo), or **Make a sample** (ST3) and switch it on, then publish. |
| Format entry | "Song" is a format: on a Story script its card says "Song is a kind of script: start a new song script". | **Start a song script** (opens S1 with Song picked). |
| Voiceover-led entry | Zack D and Skeleton are narrated: they use the narrator voiceover lines clips already carry ("Voiceover (Biscuit, in English…)", as Iron Paws Pitbull 1 does). Picking one on a script with no narrator line: Advice "This style is narrated: the script has no narrator lines yet." | **Make the narrator a role** (free: the cast read marks the script's voiceover speaker as the narrator), or keep it as a look only. |
| Format not built | An entry that needs steps we don't have (podcast, whiteboard): "Needs its own steps: not built yet". Not pickable. | — |
| Change after looks exist | Confirm with the whole price of redoing: "Change to Claymation? 3 roles need a new look, 9 stills and 4 clips go out of date. To finish: about N credits (was M)." Not yet / Change. | **Change**. |
| B | The estimate updates before the confirm; an editor over budget sees the reason and the picker stays on the current style. | — |
| P | Cards in one column, sample still full width, the button under each. | — |
| U | Undo in the toast after a change; changing back is free and the earlier looks come back (they're kept per style). | — |
| Published | Read only on the script; the video's own style can still be set in Video settings (item 4). | — |

## ST2. What a style changes downstream

| Step | Effect |
|---|---|
| Assets | A look is per style. A library character with no sheet in this style: the editor gets "Make a {style} look for this video · N credits", a per-video look that stays with the video and is never saved to Cast & places (rule 12). Only the owner adds a style sheet to a library character, in Cast & places ("Make a {style} sheet", a new version on the item; the House one is kept). Unlocked roles get a per-video look in the style automatically, as today. (Producer, 2026-10-28) |
| Storyboard | Stills use the style's paragraphs (look, character when people are in frame, camera) and its default picture model. |
| Clips | Prompts open with the style's motion line. Banned words from the style are repaired in code (free), never a block, and only in the picture descriptions: the script's spoken lines are never touched (rule 19). A banned word inside a spoken line is Advice only. |
| Refusals | The style's failure/fix list drives the free fix offered on a refused or broken still ("Make another" before rewording, per the entry). |

## ST3. Switching a style on (owner)

| State | What they see | The one press |
|---|---|---|
| E | On the Styles page (owner): each Off entry has "Make a sample · N credits" (one still and one 5 s clip of the brand's hero: its default cast's first character). | **Make a sample**. |
| No hero | The brand has no default cast yet: "Who's in the sample?" with the brand's library characters. With none at all, a sample character is described in the style itself. | Pick one, or **Use a sample character**. |
| R/F/X | As Storyboard and Clips today. | Try again / the free fix. |
| Sample ready | The still and clip. | **Switch on for editors**, or **Not yet**. |
| On | "On · editors can pick it". | **Switch off** (Undo). Videos already using it keep it. |

**Out of date (ST):** changing a video's style marks its stills and clips "Out of date" (kept, with the usual redo press), exactly like a look change.

---

# 3. Brand setup (build third)

One Brand page with sections, each saying where it's used ("Used in: script, stills, clips"). Owner edits; editors read.

## BR1. The Brand page

| Section | Edit | States |
|---|---|---|
| Logo, colours, fonts, style board | As today. | — |
| Products and bags | As today, plus a short description and the main claim per product. | Empty claim: Advice "Scripts won't mention a claim for this product." |
| App screens | As today. | — |
| Voice and tone | Audience; how the brand talks; **Do** list; **Don't** list (today's "never say" moves here, nothing lost). | — |
| CTA lines | Several lines, one marked **Default**. | Deleting the default: the next line becomes default (toast, Undo). Deleting the last: Advice "Videos will end without a saved call to action" (rule 18 stays Advice). |
| Default cast | Pick library characters. | A picked character later deleted: shows "Deleted: pick another" with **Pick another** / **Remove**. |
| Music style | One line (feeds S2). | — |
| Default style and language | Pickers (ST1, item 4). | Picking an Off style: "Off for editors: new scripts will start on House until it's on." |

| State | What they see | The one press |
|---|---|---|
| L | Section outlines. | — |
| Typing | "Saved" per section after a pause. Leaving unsaved: "Leave without saving?" | Stay / Leave. |
| Editor | Read only, with "Only the owner changes the brand." | — |
| P | Sections stacked, each collapsible; lists edited one row at a time. | — |
| U | Every delete has Undo. | — |
| S | Brand changes never touch published scripts, and nothing already made goes out of date. A video in progress uses the brand as it is when each later step runs (a new end line shows up in clips not yet written). Said under the page title: "Changes apply to work from now on. Nothing already made changes." | — |

## BR2. Import from website (nice-to-have, last)

| State | What they see | The one press |
|---|---|---|
| E | "Paste the brand's website" box. | **Read the site · about 3 credits** (owner only). |
| R | "Reading the site…" | — |
| Done | A review screen: each found item (logo, colours, description, products) with a tick, nothing saved yet. | **Save the ticked ones**, or **Cancel**. |
| F | "Couldn't read that site. Nothing was charged." | **Try again**, or fill it in by hand. |
| Nothing found | "Nothing useful on that page. Try the home page." | — |

**Effects:** one brand summary built in code from these fields feeds every writing and prompting step. It replaces the per-prompt copies (rule 26).

---

# 4. Video settings (build fourth)

A small **Video settings** row at the top of every video and on "Make this version": Style · Video model · Picture model · Language. Each shows its choice ("Auto" by default) and price.

## VS1. Changing a setting

| State | What they see | The one press |
|---|---|---|
| E | "House · Auto · Auto · English". | Tap a setting → its picker. |
| Picker | Each choice with its price in credits ("Seedance 2.5 · 1 credit a second", "Nano Banana Pro · 1.2 credits a still"). Off choices (an untested language) are hidden from editors. | Pick → confirm. |
| Song video, model can't lip-sync | Video models that can't take a song slice are labelled "No lip-sync" in the picker. Picking one asks: "Seedance 2.0 can't lip-sync. Your 3 Sung shots become B-roll (picture only)." Not yet / Switch. | **Switch** (the Sung shots flip to B-roll in this video, with Undo; switching back flips them back). |
| Confirm | "Switch to Seedance 2.0? To finish: about N credits (was M). Clips already made stay as they are and show Out of date." Not yet / Switch. | **Switch**. |
| B | The confirm shows "That's more than this video's budget" and Switch is disabled; the picker stays open. | Pick a cheaper choice. |
| Cap | A choice that would push the video over 729 credits is greyed: "Over the video limit". | — |
| O/Ed | Editors see credits only. The owner picks for any video; an editor for their videos. | — |
| P | The row collapses to one line "Settings: House · Auto…"; tapping opens a sheet with the four pickers. | — |
| U | Undo after a switch. Switching back makes the old takes current again (they were kept). | — |
| S | Model or style switch: later stills or clips "Out of date". | — |
| Language (Reed, 2026-10-28) | A video follows its script's language, shown read only in Video settings: "Spanish (from the script)". The language is chosen when the script is written. To make another language, the owner presses **Make a copy in another language** on the script: a new, unpublished, translated script for the owner to review and publish (rule 19 holds: the published words never change). | — |

**Language:** the script is written in the chosen language, every spoken line in a clip prompt says "in Spanish", and the English-only checks follow the language. Each language is switched on only after a sample test.

---

# 5. Organization (build fifth)

## OR1. Projects (folders)

A brand holds projects ("November launch"). A project holds scripts, videos and quick clips. "No project" is always there. Internally the table has another name (the database already calls a video a project); people only see "Project".

| State | What they see | The one press |
|---|---|---|
| E | "No projects yet. Everything works without one." | **New project**. |
| Moving | On any script, video or clip: "Project: none ▾". | Pick → moved (toast, Undo). |
| Delete project | "Delete November launch? Its 6 items move to No project." | **Delete** (Undo). Nothing inside is deleted. |
| Editor | Sees the projects of the brands they work on; files their own items into them and can make a project. Only the owner renames or deletes a project made by someone else. The owner files anything. | — |
| P | Projects are a list in the left tab (item 6). | — |

## OR2. Media

One page with every still, sheet, take, song and final video. Filters: brand, project, kind, who made it.

| State | What they see | The one press |
|---|---|---|
| E | "Nothing made yet in {brand}." | **Make a quick clip**. |
| L | Grey tiles. | — |
| Item | Thumbnail, kind, when, who. | **Open in {step}** (e.g. "Open in Clips"), or **Download**. |
| Owner vs editor | The owner sees everything. An editor sees what they can already open today (their own work and published scripts' videos); nothing new becomes visible through Media. | — |
| Deleted video | Its media is listed as "From a deleted video" until it's purged. | **Restore the video** (owner). |
| P | Two-column grid, filters in a sheet. | — |

## OR3. Preferred and going back

- **Preferred** (already on takes and song takes) also goes on stills and looks. Later steps use the preferred one. Moving Preferred marks later steps "Out of date" (kept, with the usual redo).
- **Versions** on storyboards and clip prompts, as breakdowns have. "Versions" lists them with **Go back to this** (Undo). Going back to an older breakdown marks later steps out of date: never a dead end (rule 22).

## OR4. Cost log

Usage adds per-project and per-video rows: dollars for the owner, credits for editors (who only see their own videos).

---

# 6. Cleaner layout (designed alongside, built last)

Three columns everywhere: **left** brands → projects → scripts and videos with a status ("Making", "Needs you"); **centre** the work; **right** this video's media. One bottom **cost bar** says what's about to run and its price before any paid press.

| State | What they see |
|---|---|
| Phone 390 | Left and right columns become tabs ("Browse · Work · Media"); the cost bar sits above the bottom tabs and holds the one amber button. No sideways scroll; controls 44px. |
| Nothing to pay | The cost bar shows the budget only ("412 / 660 credits"). |
| Over budget | The cost bar's button is disabled with the reason; free presses stay in the centre. |
| "Needs you" | A status in the left column means a step is waiting for this person (an approval, a pick); tapping it opens that step. |

The Designer draws it first (on the Screening room direction Reed picked); Reed approves; each page's PR deletes the old layout it replaces. Every flow above keeps its states and presses: the layout moves them, it never removes one.

## Open questions for the Producer

1. **The music price.** The free price check of MiniMax Music comes first (spec step 0); until then the buttons show the model catalogue's price, and the test site runs on the free stand-in.
2. **Lip-sync without a first frame** is the spec's biggest risk. The one paid 15-second test (spec step 0) decides whether Sung shots ship as designed, or fall back to "the Singer sings in B-roll style" (picture only, no lip-sync).
3. **Reel import of song ads** is left out (S1). Say if Reed wants it in this item.
