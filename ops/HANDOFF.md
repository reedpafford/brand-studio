as of f2be1c8 · 2026-10-29 05:00 UTC
# Handoff (rewritten each refresh by the Scribe; under 60 lines)
Read first: ops/MISSION.md, ops/AGENTS.md, the **Current rules** at the top of ops/DECISIONS.md (#609: 31 numbered rules, newest wins; re-read before every task). Detail of what merged, when and why is in ops/LOG.md.

## Built (on main) - short summary, detail in LOG
- Foundation: server, accounts, invites, files, brands, libraries, jobs/worker/usage, credits, per-video cap.
- Generation: Replicate adapter, Claude client, Nano Banana and Seedance prompt rules (official docs only), house style, Quick clip.
- Video path, brief to final cut, works end to end: Brief, Script (Enhance, variations, Accept all), Cast/Assets (per-video looks, character sheets, merge roles), Breakdown, Storyboard, Clips (takes, pick, Approve all, Rewrite clip prompts), stitched download.
- Workflow v2: Script Library, owner/editor split, weekly allowances, reel import and Bulk create, In production view, Delete/Archive with Undo.
- Live: https://srv2091584.hstgr.cloud, auto-deploys on every merge to main (needs the server secrets), generation on. Free stand-ins: `BS_FAKE_PROVIDERS`, `scripts/fake_run.py`.
- Design: Screening room redesign docs in `docs/design/redesign/` (Reed picked direction B).
- Latest merges (older ones are in LOG): #827 a copyright refusal says to make it again first (it costs nothing); #824 an insert is a shot about a thing, never a person; #820 Iron Paws narrated ads spend ($32.62 of $40); #812 three false alarms from Reed's song pilot; #809 a changed Cast & places sheet marks the stills and takes made from the old one (N6); #808 Redo this frame stays "changing" until its still is drawn; #813 three push rules for agents.
- Starpop study (Reed, DECISIONS 2026-10-28): Phase 1 findings (#731, #732) and the Phase 2 spec (#733) are in; Reed approved the spec with changes (#734): House style stays the default and Starpop's styles are added (Disney Pixar, Song, Zack D, Skeleton first); other models at their real Replicate cost (rule 2); music behind one provider interface (MiniMax first, Suno only with real access); song ads are B-roll timed to the real track; built as a separate test site, Brand Studio Next, on branch `next` (ops/NEXT.md). Rule 20 now also allows the studied Starpop style guidance.

## Where we are: stabilization pass (Reed, DECISIONS #602, rule 25)
No new features until, in order: 1 faces (sheet rules #603/#604, cast fix #614, hotfix #628, one scene per clip #640 all merged, now reshaped by rule 29; QA-Live 6 runs a fresh paid fomo script end to end (Reed approved) now that the montage trading-screen change (#654, #656) is merged; done, see QA-Live 6 below), 2 failing clip prompts (#605, #617, #620, #643, #648 merged), 3 bloat clean-up by the Steward (line counts before and after; deletions merged: #612, #613, #618, #621, #622, #625, #626, #641, #649, #653), 4 QA-Live runs the full editor flow on the live site, including Kel's and Mary's broken videos.
- Code stays lean (rule 26, changed by Reed 2026-10-27): about 36,000 lines of app code (server/app plus web/src, no tests or generated files) is a guide, not a hard cap; the app can grow when needed, but nothing redundant, and each change deletes what it replaces. The Steward reports the count on every PR.

## Open PRs into main (3, not counting the Scribe's own; owners read from branch names)
- #803 Storyboard: an out-of-date frame has its own Redo this frame · N (LW3 screen); #822 Clips and Downloads: a take made from an older Cast & places look says Out of date, still approved, with Make another take or Keep anyway (N6 screen) | Builder-Screens-4
- #833 Spend log: narrated ads v2 audio (~$1.30) | Song-Producer

## Brand Studio Next (branch `next`, ops/NEXT.md; the Producer merges and merges main into `next` regularly; nothing goes to main until Reed says so)
- Test site is live at :8443. Order: 0 infra + flow map -> 1 song ads -> 2 styles -> 3 brand setup -> 4 video settings -> 5 organization -> 6 layout. Every flow is written before its screen is built, no dead ends.
- Merged into `next` since the last refresh: song takes and breakdown timed to the song #799, Suno's input from song_request #783, narrated Iron Paws ads scene plan and song_ad fixes #814, flow map for narrated videos #823, Director follows the workflow that made Reed's song ads plus the song-ad study #819, layout words #773, data.md notes #830, flow map: S3a's study job goes to Builder-Server-7 #836.
- Open PRs into `next` (11; owners read from branch names): song final cut #829 and Write 2 song directions #818 (Next-Server); song-ad web #816, #826 (Next-Screens); Director narrated videos #828 and only real names leave a style line #831; layout #777, #825 (Next-Layout); data.md n04 #837 (Next-Lead); narrated-ad sound mix #834 (Song-Producer); Flow-QA checklist #817.
- Team: Next-Lead, Next-Server, Next-Screens, Next-Layout, UX-Auditor, Flow-QA, Song-Producer, Builder-Server-7 (the S3a song-ad study job); the Director works on prompts and styles; QA and QA-2 review PRs into `next`. Money: no paid call without the Producer and Reed approving that exact test; free stand-ins first; log in ops/SPEND.md. Reed's two Iron Paws song ads are delivered ($39.47 of $60) and the narrated ads cost $32.62 of $40.

## Who is on what (main)
- Builder-Screens-4: #803 (the LW3 screen) and #822 (the N6 screen); #804 (the LW2 screen), #782, #784, #786, #789, #751, #754 and #761 are merged.
- Builder-Server-6: N6 (#809) and #808 are merged, along with LW2, LW3 and LW9 (#788, #790, #792); nothing open that I can see.
- Director: #760 merged; song directions #755 and styles #753 are in `next`; rule 30 says brand names are fine, the copyright refusals were another cause.
- Writer (Reed talks to it directly): turns Reed's ideas into ready-to-paste Script Library scripts, following rule 29; never touches the app, repo or live site; no paid calls.
- Steward: line count on every PR (clip_prompts.py audit done, nothing safe to cut).
- QA and QA-2: #803, #822 on main, and PRs into `next`.
- QA-Live 6: three-video run done ($22.08 of the $35 cap; videos 27-29; report "Run 3" on branch qa/kel-faces-2026-10-27; logged in ops/SPEND.md).
- Reed: check-ins as the Next phases land; start an Iron Paws video (#670 is live); upload a fomo wordmark logo to the Brand kit (the current one is the icon alone); verdict on the altar reel-import video; makes video B (Iron Paws Pitbull 1) himself.

## Definition of done (Reed, ops/MISSION.md)
- An editor on the live site makes both videos from brief to final cut without agent help, and Reed signs off: (A) fomo altar-rejection reel, dialogue word for word, fomo logo right, live action replaced by the CTA; (B) Iron Paws Pitbull 1, script word for word, right bag.
- Test spend: 15-30 s excerpts at 480p inside the $15/week cap, estimate first; every paid call is in ops/SPEND.md (the full spend history lives there, not here).

## Blocked / needs Reed
- Reed's sign-off on videos A and B is the finish line.
- Replicate: video inputs to the reel-read model fail at the provider; the reel read falls back to frames (retry once, then frames).
