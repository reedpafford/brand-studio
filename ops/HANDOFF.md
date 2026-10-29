as of 90e952a · 2026-10-28 23:50 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 31 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #754 Clips: Change it's price is read again when a take is made; #751 Make clip says why it can't be pressed and marks Looks good for you; #752 the live deploy lock waits at most 20 minutes; #744 LIVE CHANGE: live's Caddy also answers on port 8443 for the test site; #747 Next rulings (language, styled looks); #739 rule 31 says which song-ad choices are per video; #730 failed take's line fits what happened; #728 refused take says why and offers a free reword.
- Starpop study (Reed, DECISIONS 2026-10-28): Phase 1 findings (#731, #732) and the Phase 2 spec (#733) are in; Reed approved the spec with changes (#734): House style stays the default and Starpop's styles are added (Disney Pixar, Song, Zack D, Skeleton first); other models at their real Replicate cost (rule 2); music behind one provider interface (MiniMax first, Suno only with real access); song ads are B-roll timed to the real track; built as a separate test site, Brand Studio Next, on branch `next` (ops/NEXT.md). Rule 20 now also allows the studied Starpop style guidance.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; done, see QA-Live 6 below), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs into main (2, not counting the Scribe's own; owners read from branch names)
- #760 Director: a shot that shows the brand's product attaches the real one | Director
- #761 Video: a finished video stays reachable after a breakdown edit | Builder-Screens-4

## Brand Studio Next (branch `next`, ops/NEXT.md; the Producer merges, and merges main into `next` regularly; nothing goes to main until Reed says so)
- Order: 0 infra + flow map (docs/next/flows.md) -> 1 song ads -> 2 styles -> 3 brand setup -> 4 video settings -> 5 organization -> 6 layout. Every flow is written before its screen is built, no dead ends. The test site runs as its own Compose project on the live server (#741); live's Caddy answers on port 8443 for it (#744).
- Merged into `next`: infra #741, flow map and data plan #740, style registry (House, Disney Pixar, Song, Zack D, Skeleton) #745, the rest of the styles and per-style sample tests #753, UX audit #749, deploy lock #756, Flow-QA checklist #736, song-ad screen plan #737.
- Open PRs into `next` (8; owners read from branch names): #742 screens.md follows flows.md, #759 Song ads (web): Story or Song, the Song step and the Takes step (Next-Screens); #743 flow map for styles, brand setup, video settings, organization, layout (Next-Lead); #746 music interface (Suno), free stand-in and free timing step, #748 song data and song takes for a script version, #750 a video's own song take (Next-Server); #755 song ads: two song directions, a breakdown timed to the song (Director); #758 Flow-QA checklist after the walks of #743, #746, #753 and #755 (Flow-QA).
- Team: Next-Lead, Next-Server, Next-Screens, Flow-QA; the Director works on prompts and styles; QA and QA-2 review PRs into `next`. Money: no paid call without the Producer and Reed approving that exact test; free stand-ins first; log in ops/SPEND.md.

## Who is on what (main)
- Builder-Screens-4: #761; #751 and #754 (Clips) were likely theirs; #726, #725, #722, #717 and #720 were theirs.
- Builder-Server-6: nothing open that I can see (#728, #715, #710 were theirs).
- Director: #760 on main (#727, #723, #716, #713 merged; #689 theirs); also #755 and #753 on `next`.
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: #760 and #761 on main, and PRs into `next`.
- QA-Live 6: three-video run done ($22.08 of the $35 cap; videos 27-29; report "Run 3" on branch qa/kel-faces-2026-10-27; logged in ops/SPEND.md).
- Reed: check-ins as the Next phases land; start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
