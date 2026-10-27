as of 5b4bfe0 · 2026-10-27 22:35 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 30 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #654 montage trading beats attach the brand logo, not the chart screenshot (rules 14, 17); #656 Director prompts: invented trading screens, montage arc, reactions that name the feeling; #653 nextTheme removed; #652 Builder-Server-5 replaces -3 and -4 in the session table; #651 refresh; #650/#644 Reed's montage and brand-name rules; #648 copyright-refused take says what to do; #640 one scene and about 12 s per clip, sheet sets the outfit; #642 QA-Live 6 fixes.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Size cap (rule 26): about 36,000 lines of app code (server/app plus web/src, no tests or generated files), no net growth; the Steward reports the count on every PR.

## Open PRs (1, not counting the Scribe's own)
- #655 A role named another way is the locked role, never a second one | Builder-Server-6

## Who is on what
- Builder-Server-5: the code side of the montage trading screens (#654 merged: brand logo instead of the Token chart and Desktop trading screenshots; the real Home screen only at payoff/CTA).
- Builder-Server-6 (new): #655.
- Director: the prompt side of the same (#656 merged: invented climbing charts, the montage arc, reactions naming feeling and reason). The Goth GF redraw is approved by Reed (very similar, original character, very curvy) and QA-Live 6 is doing it.
- Builder-Server-3 and Builder-Server-4: finished and retired for context; all their PRs are merged.
- Builder-Screens-3: nothing open.
- Steward: more approved deletions (nextTheme done in #653; clip_prompts.py dead paths next); line count on every PR.
- QA and QA-2: queues empty.
- QA-Live 6: doing the Goth GF redraw and retrying #12 c2 once; then the fresh fomo run now that the montage-screen change is merged (cap $15, logged in ops/SPEND.md). Video #16 run done: 94 credits, $11.35; report on branch qa/kel-faces-2026-10-27.
- Reed: say where the Goth GF's picture came from; verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
