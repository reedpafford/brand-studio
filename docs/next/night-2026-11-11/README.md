# The night of 11 Nov 2026: making the one-pass site hold up

Reed left the workflows chat running overnight: "your job is to perfect the site. It should be fully capable, no matter what I throw at it when I wake up... the site and its outputs should compete with higgsfield." This folder is the record. The working files (ledger, tools, downloaded cuts, frame sheets) stay in the skopje workspace under `.context/` (`NIGHT-LEDGER.md`, `night/`, `pgtest/`).

## What was wrong at the start of the night
Six Palace Guard test videos were started on the live site, one per style. Four of the six stopped and waited for a person, the picture service went down for an hour, and the site's API hung for ten minutes. Reed's verdict on what did finish: movies weak ("camera direction, scenes, acting"), too much B-roll on the talking head, no Zack D voice.

## What shipped (all merged into `next` and live, unless marked)
| PR | What it does | Seen on |
|---|---|---|
| #1546 | Five stops removed: the cut needs no clip approved; a narration with a word more is used; the song's style card fits; blank brand places are left out; every clip is made at once | 370, 377, 379, 373, 383 |
| #1547 | Talking head: the presenter stays on screen, B-roll under half | 370 |
| #1550 | The plan places every shot: where the camera is, where each person stands and faces, thoughts as closed lips, one person a role | 366 |
| #1551 | Nano Banana pictures go straight to Google (about $0.14 a Pro picture) | the 07:00Z outage |
| #1552 | Zack D videos are read in the Zack D narrator's voice | 383 |
| #1549 | Several videos can be planned at once (off until `BS_CLAUDE_WORKERS` is set); file downloads give their database connection back | the 04:39Z hang |
| #1553 | A narration longer than its voice reads at once is read in parts and joined; Carry on keeps the video's voice; one short shot no longer fails a long plan | 384, 391 |
| #1554 | Stops say the real reason; a failed Replicate run no longer counts as money spent | 370, 384 |
| #1555 | A look that failed while the picture service was down is drawn again after Carry on | 379 |
| #1557 | A presenter the plan names as the script describes them is still the presenter (the talking-head plan stops failing) | 370, 390 |
| #1558 | Two people who share their clips are never taken for one person | 377, 379, 383 |
| #1559 | The UI stack in one: Home as a studio, the director's live thinking, one clean frame, the polish pass (#1543, #1544, #1545, #1556) | |
| #1560 | Words a take adds to the script are silenced, free, before the cut; a talker's piece ends on its line | 390 |
| #1561 | Stop also cancels the video's paid work that hasn't started | 391 |
| #1562 | A sheet the video model takes for a real person is left out and the character said in words | 392 |
| #1548 | NOT merged, needs Reed's Approve (a guide file): Movie makes a whole scene one clip, with an early wide | 366, 389 |
| #1563 | NOT merged (into `main`): the night's spend log, $53.10 | |

## What the tests showed
Full table: `results.md`. In short, after the fixes:
- Delivered with no stop: Movie re-test (389), talking head re-test (390, once #1557 was in), Narrated in Skeleton (393) and Claymation (394).
- Delivered after the fixes unblocked them: Pixar song (377), Narrated House (379).
- A 12-minute script (391): narration read in parts, timed, and planned in one answer (58 clips, 270 shots) in about 15 minutes for $3.22. Not filmed (its price was $61).
- Zack D re-test (392): narration in the Zack D voice; stopped when Seedance 2.0 refused the man's sheet as a real person (#1562 is the fix; not re-run yet).
- RP8 (JC42 look), three hooks: `~/Desktop/Palace Guard Ads/RP8 – v1.mp4`, `– v2.mp4`, `– v3.mp4`, $1.11 of narration.

## Why the movie was weak, and what is still open
`movie-theory.md`. Short version: the storyboard used to carry the staging; one-pass sends only words, and the words said what happens, never where anyone stands or where the camera is. #1550 puts that in the plan and 389 shows it working (over-the-shoulder shots, the men small at the far end, three different men). The other half, one clip a scene so the room stops changing, is #1548 and waits for Reed.

## Waiting for Reed
1. Approve #1548 on GitHub (the Movie guide).
2. Talker pieces are sized at 2.6 words a second plus a second (his UGC playbook rule). Tonight's Omni talkers spoke at 3.4 to 4.5, so pieces run 3 to 5 seconds long and the model fills the gap (390's made-up sentence). Suggest 3.3.
3. Should "Make without asking" also approve the cast and places? Today a look redrawn after Make it asks again.
4. Turn on several plans at once (`BS_CLAUDE_WORKERS: "3"` on the Claude worker in `deploy/next/compose.yml`)? It is tested but has never run for real.

## Known gaps (not fixed)
- Zack D is three or more separate clips, not one continuous camera chained from each last frame. The pieces exist (start frames in quick clips, #1542; the one-still mechanism in `one_frame.py`); the one-pass run does not use them yet.
- A long narration is read again, whole, when the brand's name is misheard once. On 391 both re-reads failed (free) after two minutes each.
- Google pictures are made about four at a time (a picture is one blocking call), so 17 looks take about 7 minutes.
- The first price on Home counts B-roll over every second of a talking head ($8.75 shown, $4.62 planned).
- A Presenter video over 10 minutes stops after its narration and plan are paid (HeyGen's limit).
- `robustness.md` lists every way a one-pass run can stop and what was decided for each.

## How to pick this up
- Site reads and presses from a terminal: `.context/night/run.py` (state, makeit with a $6 cap, carry, castok, new), `review.py` (download, cost, transcript, frame sheet), `spend.py`, `bs.py`. They use the sanaa runner kit's owner session.
- A job's real error and cost: `/api/jobs/{id}/detail` (owner). A video's real spend: `/api/usage/videos/{id}`.
- Guide files (`server/app/guides/`) need Reed's own Approve on GitHub; prompts and code do not.
