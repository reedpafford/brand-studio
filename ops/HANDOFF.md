as of 5b0e3c9 · 2026-10-27 23:35 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 30 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #655 a role named another way is the locked role, never a second one; #658 eval-only checks moved from the app to server/evals; #659 flagged roles get no look by themselves and never hold Assets up, an automatic merge's Undo always stays; #660/#662 Reed's rule 26 change and the Writer agent; #654/#656 montage trading screens in code and prompts; #640 one scene and about 12 s per clip; #642 QA-Live 6 fixes.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; the run is under way), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs (1, not counting the Scribe's own)
- #661 Adding a missed speaker is safe when two requests do it at once | Builder-Server-6

## Who is on what
- Builder-Server-6: #661 (follow-up to #655, Girl/Brad duplicate roles); #658 and #659 merged.
- Builder-Server-5: montage trading screens, code side (#654 merged).
- Director: montage prompts (#656 merged).
- Writer (new, Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts; never touches the app, repo or live site; no paid calls.
- Steward: audit of clip_prompts.py done, nothing safe to cut; line count on every PR.
- QA: #661. QA-2: queue empty.
- QA-Live 6: running Reed's reel De49GvzS76f end to end (cap $15, logged in ops/SPEND.md). Goth GF redraw done as a new character, "Goth GF 2"; the original is untouched. Earlier video #16 run: 94 credits, $11.35; report on branch qa/kel-faces-2026-10-27.
- Builder-Screens-3, Builder-Server-3 and -4: nothing open (the last two are retired).
- Reed: verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
