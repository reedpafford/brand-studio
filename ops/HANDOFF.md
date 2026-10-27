as of 6070b40 · 2026-10-27 21:30 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 28 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #640 one scene and about 12 s per clip, sheet sets the outfit; #642 QA-Live 6 fixes (outfit after a swap, hero in every montage shot); #633 editors never see the owner's name; #634/#638 Assets and stills fixes; #641 one-time seed repair steps removed; #643 clip prompts priced per Claude call; #645 looks are original characters; #646 deploys let the worker finish; #648 copyright-refused take says what to do; #649 DELETE apply endpoint removed; #650 and #644 Reed's montage screens, arc, and brand-name rules.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged; QA-Live 6 re-runs a free check on video #16's montage), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Size cap (rule 26): about 36,000 lines of app code (server/app plus web/src, no tests or generated files), no net growth; the Steward reports the count on every PR.

## Open PRs (none, not counting the Scribe's own)
- #633, #634, #638 merged; no other PR is open.

## Who is on what (Producer's assignments; confirm in the next note)
- Builder-Server-3 and Builder-Server-4: the remaining QA-Live 6 server bugs (redraw notes too weak, an unexplained restart at 19:57, the "First frame is the first frame" wording, Keep anyway on new versions); #633 and the clip_prompts charge (#643) are merged.
- Builder-Screens-3: editor-visible "Reed" text, the "$" title cut and the estimate.
- Director: the copyright refusals (they all involve the Goth GF look, not brand names, rule 30) and the montage trading-screen and arc rules (rules 14, 17).
- Steward: line count on every PR; more approved deletions.
- QA-Live 6: paid run done (video #16, 94 credits, $11.35); report on branch qa/kel-faces-2026-10-27; re-runs after the montage-screen change.
- Reed: refund Kel 95 credits; remove QA Editor from Team; verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
