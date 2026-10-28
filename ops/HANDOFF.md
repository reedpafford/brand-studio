as of a330c3f · 2026-10-28 22:50 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 31 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #730 Clips: a failed take's line fits what happened since, Change it says what it does; #728 a take the video model refuses as unsafe says why and offers a free reword; #727 Director: never read as sexual; #726 an Approve's re-read keeps the counts; #725 no counts from a list read before the step opened; #723 first clip-prompt part asked alone and writes the cache; #722 role-words box full width on a phone; #720/#715 role words follow the approved look.
- Starpop study (Reed, DECISIONS 2026-10-28): Phase 1 findings (#731, #732) and the Phase 2 spec (#733) are in; Reed approved the spec with changes (#734): House style stays the default and Starpop's styles are added (Disney Pixar, Song, Zack D, Skeleton first); other models at their real Replicate cost (rule 2); music behind one provider interface (MiniMax first, Suno only with real access); song ads are B-roll timed to the real track; built as a separate test site, Brand Studio Next, on branch `next` (ops/NEXT.md). Rule 20 now also allows the studied Starpop style guidance.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; done, see QA-Live 6 below), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs into main (none, not counting the Scribe's own)
- #726, #727, #728 and #730 merged; no other PR into main is open.

## Brand Studio Next (branch `next`, ops/NEXT.md; the Producer merges, and merges main into `next` regularly; nothing goes to main until Reed says so)
- Order: 0 infra + flow map (docs/next/flows.md) -> 1 song ads -> 2 styles -> 3 brand setup -> 4 video settings -> 5 organization -> 6 layout. Every flow is written before its screen is built, no dead ends.
- Open PRs into `next` (owners read from branch names): #736 Flow-QA: living checklist of song-ad flows and states (Flow-QA); #737 Next: song-ad screen plan, draft for Next-Lead to check against flows.md (Next-Screens).
- Team: Next-Lead (test-site infra, data model, flows.md), Next-Server, Next-Screens, Flow-QA; the Director works on prompts and styles for `next`; QA and QA-2 review PRs into `next`. The Researcher finished Phases 1 and 2; a second Researcher on Reed's Mac covered Starpop's in-app findings.
- Money: no paid call without the Producer and Reed approving that exact test; free stand-ins first; log in ops/SPEND.md.

## Who is on what (main)
- Builder-Screens-4: #726 merged; #725, #722, #717 (owner edit of a published script), #720 (the card) and #711 were theirs; the Clips failure-line and price-label PR they were preparing may be #730.
- Builder-Server-6: #728 merged; #715 and #710 were theirs.
- Director: #727 merged (and #723, #716, #713; #689 theirs); now also on `next`.
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: queues empty on main.
- QA-Live 6: three-video run done ($22.08 of the $35 cap; videos 27-29; report "Run 3" on branch qa/kel-faces-2026-10-27; logged in ops/SPEND.md).
- Reed: check-ins as the Next phases land; start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
