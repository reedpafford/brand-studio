as of 12e92b4 · 2026-10-29 02:58 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 31 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #801 Redo this frame names the way on when the script moved; #798/#793/#788 lists, Videos, In production and Usage say Finished · changes waiting when a finished video's clips changed since (LW2); #792 a version's length is its video's once it has a breakdown (LW9); #790 Redo this frame: an out-of-date still is written again, then drawn (LW3); #789 a failed take's line and the server's error agree; #769 Iron Paws song-ad pilot spend log.
- Starpop study (Reed, DECISIONS 2026-10-28): Phase 1 findings (#731, #732) and the Phase 2 spec (#733) are in; Reed approved the spec with changes (#734): House style stays the default and Starpop's styles are added (Disney Pixar, Song, Zack D, Skeleton first); other models at their real Replicate cost (rule 2); music behind one provider interface (MiniMax first, Suno only with real access); song ads are B-roll timed to the real track; built as a separate test site, Brand Studio Next, on branch `next` (ops/NEXT.md). Rule 20 now also allows the studied Starpop style guidance.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; done, see QA-Live 6 below), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs into main (2, not counting the Scribe's own; owners read from branch names)
- #803 Storyboard: an out-of-date frame has its own Redo this frame · N, or says why not with Redo storyboard (LW3 screen); #804 Usage says Finished · changes waiting too, and In production's count of them links to Usage (LW2 screen) | Builder-Screens-4

## Brand Studio Next (branch `next`, ops/NEXT.md; the Producer merges and merges main into `next` regularly; nothing goes to main until Reed says so)
- Test site is live at :8443. Order: 0 infra + flow map -> 1 song ads -> 2 styles -> 3 brand setup -> 4 video settings -> 5 organization -> 6 layout. Every flow is written before its screen is built, no dead ends.
- Merged into `next` since the last refresh: song ads web (Story or Song, Song and Takes steps, who sings, trimming, Suno's limits) #759, #775, #783; Director song ads #755 and the Iron Paws song pilot flows #795, #796, #797; Song-Producer pilot directions #763; flow map LW3/M16 #780; prices hold their place #778; UX audit part 6 #772.
- Open PRs into `next` (13; owners read from branch names): song takes and breakdown #799, #802 (Next-Server); song-ad web #781 (Next-Screens); Director song pilot #794; data.md song sidecar #800 (Next-Lead); words and layout #766, #771, #773, #777, #779 (Next-Layout, from the UX audit); UX audit 6.12 #787 (UX-Auditor); Flow-QA checklist #776. Next-Lead's merge of main into `next` (#785) is with QA.
- Team: Next-Lead, Next-Server, Next-Screens, Next-Layout (layout and wording PRs from the UX audit), UX-Auditor (owns docs/next/ux-audit.md and the wireframes), Flow-QA, Song-Producer (helping Reed hand-make two Iron Paws song ads; spend in #769); the Director works on prompts and styles; QA and QA-2 review PRs into `next`. Money: no paid call without the Producer and Reed approving that exact test; free stand-ins first; log in ops/SPEND.md.

## Who is on what (main)
- Builder-Screens-4: #803 and #804, the screens for LW2 and LW3; #782, #784, #786, #789, #751, #754 and #761 are merged.
- Builder-Server-6: LW2, LW3 and LW9 merged (#788, #790, #792); standing by for the next batch.
- Director: #760 merged; song directions #755 and styles #753 are in `next`; rule 30 says brand names are fine, the copyright refusals were another cause.
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: #803 and #804 on main, and PRs into `next` (#785 first).
- QA-Live 6: three-video run done ($22.08 of the $35 cap; videos 27-29; report "Run 3" on branch qa/kel-faces-2026-10-27; logged in ops/SPEND.md).
- Reed: check-ins as the Next phases land; start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
