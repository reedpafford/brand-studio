as of 7e078ad · 2026-10-28 00:35 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 30 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #661 adding a missed speaker is safe when two requests do it at once; #664 the cast backstop runs one request at a time per video; #666 invented screens spell the fomo word and never recreate a famous scene; #668 a take the video service was too busy to finish says to try again; #655 a role named another way is the locked role; #659 flagged roles never hold Assets up; #658 eval-only checks moved to server/evals; #660/#662 rule 26 is a guide, the Writer agent added.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; the run is under way), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs (4, not counting the Scribe's own)
- #665 Clips: after Change this... on a clip with no take, say what to press next | Builder-Screens-3
- #667 QA-Live video #17: a changed sheet refreshes prompts and flags old stills; long prompts editable; full price quoted | Builder-Server-5
- #669 Director: the grind shows the trading; phone beats play for drama | Director
- #670 Director: the "opening the app" bridge is only for an app brand (Iron Paws must-fix) | Director

## Who is on what
- Builder-Server-5: #667 (QA-Live video #17 fixes). Builder-Server-6: #661 and #664 merged; nothing open that I can see.
- Builder-Screens-3: #665.
- Director: #669 and #670 (montage grind and the app-only bridge).
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: the open PRs above.
- QA-Live 6: ran video #17 (Reed's reel De49GvzS76f end to end, cap $15, logged in ops/SPEND.md); fixes in #667. Goth GF 2 is a new character; the original is untouched. Earlier video #16 run: 94 credits, $11.35; report on branch qa/kel-faces-2026-10-27.
- Reed: verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.
(Assignments after 5b0e3c9 are read from the PR branch names; the Producer corrects where wrong.)

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
