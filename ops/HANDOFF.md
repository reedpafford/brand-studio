as of 9a867af · 2026-10-27 18:30 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 28 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges: #625 "Save to Cast & places" removed (-372 lines), #626/#622 unused /usage endpoint and End card picker removed, #623 evals follow rule 17; #612/#613/#618/#621 clean-up (docs, endpoints, duplicate tests); #617/#620 clip shape repaired free, free fix capped once, then the priced rewrite; #615 no "Save to Cast & places" (rule 12); #616 prompts follow Current rules; #603/#604 character sheet owns the face, main character's sheet first; #601 app screens only need the logo right; #606 "Use the real image" cleared on replace; #605 clip prompts always finish, a few clips per answer, causes named; #607 size cap; #609 Current rules.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules in #603/#604; not done until the cast fix lands), 2 failing clip prompts (#605, #617, #620 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Size cap (rule 26): about 36,000 lines of app code (server/app plus web/src, no tests or generated files), no net growth; the Steward reports the count on every PR.

## Open PRs (1, not counting the Scribe's own)
- #614 Every speaker is a role at Assets, nothing is drawn without their look (cast completeness) | Builder-Server-3

## Who is on what
- Builder-Server-3: cast completeness (#614, open; plus the Marriage Rejection repair); the Producer adds the SPEND.md line for the #506 repair call after it runs on deploy.
- Builder-Server-4: Mary's #5 timing auto-repair (the free-fix cap landed in #617).
- Builder-Screens-3: screens for the 2026-10-27 decisions as the Producer assigns.
- Director: prompt clean-up against Current rules, free evals only; #623 merged.
- Steward: approved deletions (bloat clean-up, step 3; #622 and #626 merged); line count on every PR.
- QA-Live 6: phase 1 done; phase 2 after the fixes land.
- Reed: verdict on the altar reel-import video; picks test characters saved to the library to delete; tests the climbing-numbers montage rule live; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
