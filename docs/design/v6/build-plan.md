# v6 build plan: small PRs

For Reed, the lead (kuala-lumpur) and Next-Lead. Reed approved the v6 boards on 3 Nov and answered the open items (see `review.md`).

Every web PR follows rule 33: it shows each changed board beside a screenshot at 1440 and 390, lists any difference and why, and deletes what it replaces (rule 26).

## Who builds what, and when

- **The lead builds the server side.** It's already in his director brief (asking, watching, models, the cut, organisation). Pieces A–F below say what the screens need from each, so it's built once. Each is a few routes plus data on top of what exists.
- **Next-Lead's builders build the screens**, after the v5 PRs that touch the same files have merged. The table at the end lists those files.
- **Rules for the Producer to update** (Reed's answers, 3 Nov):
  - Rule 11: the director watches every take and redoes what's weak within the budget, and says so. This replaces "never redoes on its own".
  - Rule 21: no per-item approval lists, so no Approve all; the video page is chat plus panel.
  - Rule 33: v6 replaces v5 for the screens drawn here.
  - New: a story choice with no answer gets the director's pick after a set wait.
  - Rule 12 stays as it is: generated looks are never saved, and uploads in a chat aren't added to the brand for now.

## Server (the lead)

| # | Piece | What the screens need | Boards | Size |
|---|---|---|---|---|
| A | Nested folders | `parent_id` on folders (today they're flat "projects"), move a folder, Unsorted = no folder (as "No project" is now). A tree read: folders with counts plus each idea's status. Delete moves ideas to Unsorted with Undo (exists). | S0-01, S1, P-01 | S |
| B | The ask move | An ask record: kind, question, why, saved options, state (open, answered, answered by the owner, no longer needed, failed, held). Answers: pick saved, upload, reply, or generate options with an up-to price; generated items stay with the video. A story choice carries a default pick and a time; after it passes, the director takes its pick. | S4-01 to S4-04, S3-05, S9-01 | M |
| C | One live progress record per run | Scenes with each clip's state (done, making, to do, redone, changed and not yet seen) and the step list. A "seen" mark per person, so changed clips stay outlined until watched. | S3-03, S3-04, S3-12, S3-13 | M |
| D | The delivery note | Structured fields: made, watched and redid (with timecodes), unsure of, needs from you, real cost. | S3-09, S3-10 | S |
| E | Cut edits | Cut versions (Cut 1, Cut 2), with the old one playable until the new one is ready. Trim, re-time to the words (word times), presenter side, size or hidden per span, swap B-roll, music quieter by an amount, sound effects per clip (#1291 has these). Each director edit is logged with Undo. Re-making the cut is free. | S7-01 to S7-07 | M |
| F | Per-clip model and why | The model each clip used and one line on why. The prompt can be read and changed (mostly exists). | S6-02, S6-03 | S |

## Screens (Next-Lead's builders, in this order)

| # | PR | Boards | Needs | Replaces (delete) | Wait for |
|---|---|---|---|---|---|
| 1 | Folder tree in the rail | S0-01, P-01 | A | The "Project ▾" picker (`folders/Projects.tsx`) | #1253, #1264 |
| 2 | Brand home: an open folder (idea cards, list view for 100+, select, move, archive) | S1-01 to S1-08, P-02 | A | The Videos table's grouping (`videos/VideosPage.tsx`, `VideoRows.tsx`) | #1253 |
| 3 | Video page: chat plus preview panel, with today's panes inside the panel | S3-01, S3-09, S3-15, S3-16, P-04, P-05 | — | The tab row and `DirectorPanel` | #1185, #1269 |
| 4 | Progress card with the filmstrip; the delivery note | S3-03, S3-04, S3-08, S3-11, S3-12, S3-13 | C, D | One-message-per-step rows in `DirectorChat` | 3 |
| 5 | Ask cards, the pinned bar, and the start-of-run and budget cards | S3-02, S3-05 to S3-07, S4-01 to S4-04, P-06, P-07, P-15 | B | — | 3 |
| 6 | Needs you lists asks, money and stuck videos across brands | S9-01, P-14 | B | — | 5 |
| 7 | New video: one message box, format and style picture cards with sample clips and a B-roll line | S2-01 to S2-07, P-03 | — | The Freestyle form (`freestyle/Composer.tsx`, `FreestylePage.tsx`) | — |
| 8 | Clips tab: grouped by scene, filters, one clip open | S6-01 to S6-06, P-10, P-11 | C, F | `ClipsPane`, `ClipsStep` | 3 |
| 9 | Cast and presenter tab | S5-01 to S5-04, P-09 | — | The old cast step inside the video | 3, #1269 |
| 10 | Cut editor | S7-01 to S7-07, P-12 | E | `FinalPane`'s card | 3 |
| 11 | Library: Presenters & voices, Products, new-item states | S8-01 to S8-08, P-13 | — | — | #1259, #1265, #1267, #1266 |

Pieces 1, 2 and 7 can start as soon as their wait-for PRs merge. Pieces 3–10 go in order. Each one leaves the test site working.

**Style sample clips (piece 7).** These need one short clip per style. Use the 3 Nov test samples already on disk, so nothing paid is needed. Reed swaps in his own clips later.

## Files to leave alone until their PR merges

| Open PR | Files |
|---|---|
| #1253 (Videos to v5) | `web/src/folders/Projects.tsx`, `web/src/videos/VideosPage.tsx`, `VideoRows.tsx`, `components/Badge.tsx` |
| #1259 (Cast & places) | `web/src/library/LibraryPage.tsx` |
| #1264 (Usage, Team, rail account row) | `web/src/shell/Shell.tsx`, `AccountMenu.tsx`, `usage/*`, `team/TeamPage.tsx` |
| #1265, #1267 (Media) | `web/src/media/MediaPage.tsx`, `server/app/routes/media.py`, `routes/project_clips.py`, migration n25 |
| #1266 (Brand unsaved changes) | `web/src/brand/*`, `web/src/main.tsx` |
| #1269 (Cast lock) | `web/src/scripts/CastStep.tsx`, `LockPanel.tsx`, `ScriptFlowPage.tsx`, `projects/RoleFacts.tsx` |
| #1185 (director moves) | `server/app/director.py`, `director_tools.py`. Piece B also edits `director_tools.py`, so it goes after #1185. |
| #1260, #1268, #854 | Script steps, a words test, the Flow-QA checklist: no overlap with v6 |
