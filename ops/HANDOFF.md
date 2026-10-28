as of b5ec3fb · 2026-10-28 17:40 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 30 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #697 a word the image model may refuse is Advice (Draw it as is, or Soften it); #694 an Assets role card shows its look whenever it has one; #691 Reed: editors may see his name (rule 4); #687 New script in one press; #686/#689 clips split by scene or action (rule 29); #683/#684/#685 Reed's rule 29; #681 budget stops at the per-video cap; #680 credits meter; #679 project budget twice the whole estimate.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; the run is under way), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs (6, not counting the Scribe's own; owners read from branch names)
- #693 Names show plainly to everyone: owner-name masking removed | Builder-Server-6
- #695 Storyboard: a still whose job is lost stops saying Drawing... | Builder-Screens-4
- #696 Director: image-model word list drops "crust" and "lap", which over-flag | Director
- #698 A job running past its time limit fails plainly; a waiting one says why | Builder-Server-6
- #699 Claude gets its own worker lane, so stills never wait behind it | Builder-Server-6
- #700 Director: the story agrees with the real payoff balance; variations take a requested length | Director

## Who is on what
- Builder-Server-6: #693, #698, #699 (owner-name masking removed, job time limit, Claude worker lane). Builder-Server-5 is done.
- Builder-Screens-4 (new): #695. Builder-Screens-3 is retired for context (#687 was theirs); the next web batch goes to a fresh session.
- Director: #696 and #700 (#689 was theirs, rule 29 in the prompts).
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: the open PRs above.
- QA-Live 6: paid run of three fomo videos from reel Dcwkj6NSO7r (cap $35, waiting on Reed's approval in its session; log in ops/SPEND.md). Earlier: video #17 (Reed's reel De49GvzS76f, cap $15) and video #16 (94 credits, $11.35); Goth GF 2 is a new character, the original untouched.
- Reed: approve the three-video run (cap $35); start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
