as of 2c9e106 · 2026-10-28 21:50 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 31 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #725 Assets, Storyboard and Clips show no counts from a list read before the step opened; #723 the first clip-prompt part is asked alone and writes the shared prompt's cache; #722 the Assets role-words box takes the card's full width on a phone; #720 a role whose words contradict its approved look says so, with Update to match; #715 a role's words follow its approved look; #717 the owner can still edit a published script's title, about and notes (rule 31); #716 a clip prompt run's parts are asked at the same time (up to 4); #721 Starpop comparison, our side (Phase 1).
- Starpop study (Reed, DECISIONS 2026-10-28): findings, then spec, then a separate test site on the same machine (own database, no shared live data), three phases with Reed's check-in after each; a separate site, so rule 25 doesn't block it. Test budget up to 75% of the credit balance at the start. The Researcher (Phase 1 done on our side, #721) studies through Reed's own logged-in browser, read-only on live sites.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; done, see QA-Live 6 below), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs (3, not counting the Scribe's own; owners read from branch names)
- #726 Assets: an Approve's re-read keeps the counts (no "Loading assets..." flash) | Builder-Screens-4
- #727 Director: never read as sexual (no bodily sounds beside a person in bed) | Director
- #728 A take the video model refuses as unsafe says why and offers a free reword | Builder-Server-6

## Who is on what
- Builder-Screens-4: #726; #722 merged; #717 (owner edit of a published script's title, about and notes), #720 (the card) and #711 were theirs.
- Builder-Server-6: #728; #715 (server side of role words following the look) and #710 were theirs.
- Director: #727 (#723, #716 and #713 merged; #689 was theirs).
- Researcher (new): Starpop comparison, Phase 1 (our side done, #721); studies through Reed's own logged-in browser, findings for Reed; read-only on live sites. A second Researcher will run on Reed's Mac for Starpop's in-app findings, since cloud sessions can't reach his Mac.
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: #726, #727 and #728.
- QA-Live 6: three-video run done ($22.08 of the $35 cap; videos 27-29; report "Run 3" on branch qa/kel-faces-2026-10-27; logged in ops/SPEND.md).
- Reed: check-in after Starpop Phase 1; start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
