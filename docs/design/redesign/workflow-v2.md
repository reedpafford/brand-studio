# Workflow v2: scripts first, then videos (plan for Reed)

**Status:** approved by Reed (GO, 2026-10-25) with the defaults in section 6. Built; screen specs are in `workflow-v2/`. Source: Reed's decision and answers of 2026-10-25 in `ops/DECISIONS.md`. It maps the new workflow onto the approved structure (phase 1) and the Screening room design (phase 3). Map: `workflow-v2-map.png`.

## The idea in one paragraph
A brand's home becomes the **Script library**:
- **Reed** (or any editor) writes a script once.
- Claude suggests directions without touching the words.
- Reed adds up to two **variations** and **locks** the characters that must look the same everywhere.
- Reed can preview and adjust the shots, then **publishes**.

Each published version can be made into **one video**. An editor picks a version from the library, and the video page walks them through:
1. Breakdown
2. Assets
3. Storyboard
4. Clips
5. Downloads

Both flows use the same frame: header, step picker, one amber Next, and Back.

## 1. Where things live (the shell)
- The four brand sections stay four. **Scripts** replaces Videos as the brand's home: **Scripts · Quick clip · Cast & places · Brand**.
  - Each video belongs to a script version, so the library shows both. On phones it's still four tabs.
- The **Studio** area (Approvals, Team) doesn't change.
- Every step in both flows gets a **Back** (ghost, left) and **Next** (amber, right) pair:
  - Desktop: both in the step bar.
  - Phone: both in the action bar, Back as an icon button.
- A finished step shows a clear done state: a tick in the step picker, plus a one-line summary at the top of the step ("Approved · 2 variations · locked: Bo, Mia").

## 2. Script library (new, replaces Videos home)
```
IRON PAWS
Scripts                                          [Bulk create]  [＋ New script]
[Search scripts…]  Status ▾  Length ▾  Reference ▾  Versions left ▾     (filters as chips on phone, scroll inside)
┌ script row ─────────────────────────────────────────────────────────────────┐
│ ▌poster│ Bo tries salmon                     Reed · 2 days ago · 24–30 s        │
│        │ ref: "The altar reel"                                                 │
│        │ [A Original · Video done ✓] [B · In production (Sam)] [C · Ready to make] │
└──────────────────────────────────────────────────────────────────────────────┘
```
- **One row per script**, with up to three version chips. Each chip has a status in words:
  - Writing
  - Ready to make
  - In production (who)
  - Video done
  - Didn't finish
- A chip opens that version: the writing flow if it's yours and unpublished, otherwise the video.
- **Filters:** brand (the current brand by default; "All brands" for Reed), status, length (under 15 s / 15–30 s / 30–60 s / over 60 s), reference reel, and versions left (0, 1, 2, 3).
- **Search** matches the title, the description and the script text.
- **Bulk create** (Reed, editors too):
  - a sheet where you paste one description per line, or pick several reference reels
  - each line becomes a draft script ("Writing")
  - one optional priced button: **Write all scripts · N credits**
- **The editor's view:** the same library, with **Ready to make** as the default filter.
- **States:**

  | State | What shows |
  |---|---|
  | Empty | **No scripts for {brand} yet.** "Write a script once, make up to three videos from it." **＋ New script** |
  | Loading | Row skeletons |
  | Error | Banner with **Try again** |
  | No match | "Nothing matches these filters." **Clear filters** |

## 3. Writing flow (owner, and editors for their own scripts): 7 steps
The frame from #179 (header, step picker, one Next, Script panel), with these steps:

| # | Step | What happens | Done when |
|---|---|---|---|
| 1 | **Description** | Title, brand (preset), what it's for, optional reference reel (the compact list from New video), notes. No length field. | Title and description saved |
| 2 | **Script** | Write with Claude (drafts), paste, upload, or **Adapt the reference** (new card when a reel is picked). This is #185's step as built. | A working script exists |
| 3 | **Directions** | Claude suggests camera, movement, reaction and brand screens; Reed's words never change. Optional: **Skip** is allowed. This is #185's Suggest directions, moved to its own step. | Applied or skipped |
| 4 | **Variations** | Reed: pick **0, 1 or 2** alternates, written together at one price (**Write 2 variations · N credits**); each **Regenerate** is paid. Editors on their own scripts: the step is skipped by default, with a secondary **Add a variation** on Publish. Side by side: Original · Variation B · Variation C, each in the script font, with what changed highlighted. Each one has **Approve**, **Edit** and **Regenerate · N credits**. After approval, each shows "Approved · words locked". | Every variation kept is approved (or 0 chosen) |
| 5 | **Characters** | Each character in the script is a row: picture, name, and a **Lock look** switch with a sheet picker. Locked: "Used as-is in every version." Unlocked: "The editor makes or picks a look." | Every character is decided (locked or not) |
| 6 | **Breakdown** (optional) | Per version (tabs A / B / C): run the breakdown and edit timing, shots, splits and joins. This is #186's Shots step as built. It shows planned length and cost per version. **Skip** is allowed. | Saved for each version, or skipped |
| 7 | **Publish** | A summary card per version: words approved, characters locked, breakdown saved or auto, estimated length and credits, then **Publish to the library**. | Versions are "Ready to make" |

- **Side by side (step 4):**
  - Desktop: up to three columns, 360px or wider each, scrolling together. The changed lines are marked with the `mark` colour, using the same marks as Enhance.
  - Phone: segmented tabs **Original · B · C** and a "Changes" toggle.
- **After approval, no version's words change.** Edit and Regenerate disappear and a lock icon shows. To change them, start a new script (keep it simple).

## 4. Making a video (editor flow): 5 steps
A video is made **from one version**. It opens from a library chip ("Make this version"), which reserves the version for that editor ("In production (Sam)").

| # | Step | What happens | Done when |
|---|---|---|---|
| 1 | **Breakdown** | Reed's saved breakdown if there is one ("Planned by Reed"); otherwise it runs automatically on open. It shows length and credits. The editor can adjust it (the #186 editor). The montage check now counts hand and screen inserts, and **no check is a dead end**: every problem has **Go to** and a way past it. | No problems left |
| 2 | **Assets** (new) | One card per character, place and screen used. **Locked** characters show their sheet with "Locked", already approved. **Unlocked** ones get **Make look · N credits** (or "Pick a sheet"), then **Approve**. App screens are listed from the brand. | Every asset approved |
| 3 | **Storyboard** | As specced (frames plus stills in one press). | Every frame approved |
| 4 | **Clips** | **Write clip prompts**, then read each one (**Looks good** / **Edit**), then **Make the takes · N credits**. Review the takes: **Looks good**, or **Needs a change → Redo**. | Every clip approved |
| 5 | **Downloads** | Everything to take away. There's no upload (Reed, 2026-10-25). See the layout under the table. | Downloaded or made, then "Video done" |

- **Downloads (step 5):**
  - **All clips** (amber): the picked take of every clip, in order, as one .zip: "bo-tries-salmon-clips.zip".
  - **The whole video** (secondary): the stitched MP4, as today. It's made free the first time it's asked for.
  - **One per clip:** a list of clips, each with **Download** for its picked take and an **Older takes (2)** disclosure. Each older take has its own Download.
  - The version's chip becomes "Video done" once the video is made or the clips are downloaded.
- **No length up front.** The breakdown sets it. The $75 per-video cap is checked when the breakdown is made: "This version would cost more than one video can (729 credits). Shorten it in Breakdown, or ask Reed."
- **Credits, two kinds:**
  - **Reed's library versions** keep today's rules: the video budget, with spend past it going to Approvals.
  - **An editor's own script** uses their one weekly allowance, $15 (about 145 credits), shared with their Quick clips. The header shows "This week: 32 of 145 credits". Past it, a paid button is disabled with: "That's more than this week's 145 free credits. It resets on Monday." There's no "Ask Reed" on this path; it's declined, not sent for approval.

## 5. Which redesign work stands
| PR / spec | Status | Why |
|---|---|---|
| 1 Tokens and fonts (#175), 2 Shared parts (#176), 3 Shell (#178) | **Stands** | Design system and frame. The nav label "Videos" becomes "Scripts" (one line, in the library PR). |
| 6 Video frame (#179) | **Stands, reused** | The same frame for both flows. The steps list becomes per-flow (7 and 5). |
| 7a Script (#185), 7b Shots (#186) | **Finish and merge** | They become writing step 2 and the shared Breakdown editor (writing step 6 and video step 1). Directions moves to its own step later. |
| 10 Quick clip (#183) | **Stands** | Untouched by the workflow. |
| 11 Cast & places | **Stands, plus one line** | The character page shows "Locked in 3 scripts" and which sheet. Locking happens in the writing flow. |
| 12 Brand, 13 Studio and auth | **Stand** | No change. |
| 4 Videos home (#180) | **Re-spec** | Becomes the Script library (section 2). The poster card style is reused in library rows. |
| 5 New video | **Re-spec** | Becomes writing step 1, Description: no length, no cast or flavour picking (characters come from the script). |
| 8 Storyboard, 9 Clips and Final video | **Re-spec (small)** | Same screens. Add Assets before Storyboard and the version context in the header. Final video becomes **Downloads** (all clips as .zip, the whole video, older takes per clip). |
| New | **Spec** | Script library, Variations side by side, Characters (locks), Publish, Assets, Bulk create. |

## 6. Decided (Reed, 2026-10-25)
| | Decision | What it means on screen |
|---|---|---|
| a | Downloads only, no upload | Video step 5 is **Downloads**: all clips as .zip, the whole video as MP4, and each clip with its older takes. |
| b | Clip prompts are reviewed before takes are paid for | Clips keeps **Write clip prompts** → Looks good / Edit → **Make the takes · N credits**. |
| c | A version is reserved for the editor who starts it | Its library chip reads "In production (Sam)". Others see it, but can't start it. |
| d | Variations are written together at one price; each Regenerate is paid | The Variations step shows **Write 2 variations · N credits** (or 1), and **Regenerate · N credits** per version. |
| e | One locked look per character | The Characters step shows one sheet picker per character. |
| f | Editors' scripts are private until published; editors can make variations and locks on their own scripts | The library's "Mine" filter shows drafts. Other editors only see it once it's published; Reed sees every draft. |
| g | Bulk create takes titles, descriptions and an optional reel. Nothing is written until **Write all** | Bulk create makes drafts. **Write all scripts · N credits** shows its estimate first. |
| h | The budget is set at Breakdown: twice its estimate, at most $75 | There's no length up front. The cap message shows at Breakdown. |
| i | A published version is final; duplicate to change it | Published versions show a lock and **Duplicate script**. Nothing can be edited. |
| j | Editors only produce published scripts | "Make this version" appears only on published versions. An editor publishes their own script first. |
| k | The video keeps its own copy of the breakdown | Editing in the video's Breakdown step never changes the saved version. |
| l | One shared 145-credit weekly allowance per editor, covering Quick clips and their own scripts | One line everywhere: "This week: N of 145 credits". Past it, declined. Reed's library versions use the video budget and Approvals instead. |

## 7. What the server needs
This is for the Producer to scope; the web can't do it alone.
- Script and version records, separate from videos: description, reference, notes, status, author and brand. Versions A/B/C each have their own approved words.
- Variations: a paid Claude call that writes B and C from A, plus approve and regenerate per version.
- Character locks per script: character → sheet.
- A saved breakdown per version, copied into the video when it's made.
- The library list with filters and search, plus bulk create.
- A video linked to a version, a version reserved by an editor, and length taken from the breakdown (no `planned_seconds` needed).
- The Assets step: the list of assets a version needs, and approval per asset per video.
- Downloads: one .zip of a video's picked takes, and older takes listed per clip (the files exist; the list needs an endpoint or field).
- A weekly allowance for editors' own scripts ($15, about 145 credits). Past it the call is **declined** with a reason, not held for approval. Reed's library versions keep the video budget and Approvals.
- The breakdown check fix: hand and screen inserts count for montage shots.

## 8. Order and ETA
1. **Now:** finish and merge #185 and #186 (their must-fixes are small). They're reused as they are.
2. **Re-specs, now that Reed has decided** (about 5–6 hours of design, handed over one at a time, library first):
   - Script library and bulk create: 1.5 h
   - Writing flow steps 1, 3–5 and 7: 2 h
   - Assets, plus the small Storyboard, Clips and Final changes: 1.5 h
   - one updated map with all states: 1 h
3. **Build order** once the server pieces exist:
   - library (read-only first)
   - writing flow
   - Variations and Characters
   - Publish
   - video flow on versions (Assets)
   - bulk create

   Each is one screen group per PR, as before.
