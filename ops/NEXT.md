# Brand Studio Next (the test site)

Reed approved the Phase 2 spec on 2026-10-28 (docs/research/starpop-2026-10-28/spec.md), with the changes below. Every agent on Next reads this, the spec, and the Current rules in ops/DECISIONS.md first.

## What Reed decided (2026-10-28)
- **Styles.** Our current look stays as the **House style** (the default). Starpop's styles are added as registry entries. Their order: **Disney Pixar, Song, Zack D, Skeleton** first, then the rest. Style guidance may come from the providers' docs and the styles studied in docs/research/starpop-2026-10-28/ (rule 20).
- **Format and Look are two settings (Reed, 2026-10-29).** Format is Dialogue, Song or Narrated. Look is House (default), Disney Pixar, Zack D or Skeleton. Any format goes with any look; "Song" moves out of the styles list into Format.
- **Narrated ads are a format (Reed, 2026-10-29).** This is the recipe that made Reed's two narrated Iron Paws ads (docs/next/song-ad-workflow.md, "Narrated ads" and "v2: the sound"):
  - one narrator track (ElevenLabs v3 via Replicate, voice "Sarah");
  - B-roll timed to the measured sentences;
  - each take's own sound effects kept;
  - background music that ducks under the narrator (Stable Audio 2.5 via Replicate, or Suno instrumental);
  - pauses trimmed only on real silence, checked so no word is clipped.
  Changing the voice and the music is a nice-to-have for later.
- **Models.** Other image/video models are allowed, each priced in credits at its real Replicate cost (rule 2). 480p Seedance stays the default.
- **Music (updated 2026-10-29).** Suno through KIE (kie.ai, Suno V6, about $0.06 for 2 takes) is the song provider, and it's on for the test site with a $5 test budget (Reed, 2026-10-29). The key is `KIE_API_KEY` in the deploy secrets, never in code or chat. Every real song is logged in ops/SPEND.md. MiniMax is dropped (Reed: "use the exact softwares we would use live").
- **For every video, not just songs (Reed, 2026-10-29).** These are built and tested here first, then brought to live. Redo the UX and UI as needed, very thoroughly:
  - **A creative plan before the breakdown.** The script becomes a scene plan the editor approves, edits or redoes: the structure (from the reference, or a proven pattern for the genre and brand), one vivid exaggerated action per line, the product at the key moments, and the same cast throughout. The words never change. Worked examples: docs/next/ironpaws-vo/plan.py, docs/next/song-pilot/ironpaws-shot-plans.md.
  - **Automatic fixes.** A refused or "service busy" take retries once on its own (refusals are free), and clip-prompt wording flags fix themselves.
  - **An advisory AI check** on stills and takes against the character sheets and the product image. It flags likely face, outfit and product problems as Advice, each with a ready "Change this…" note, and never blocks or redoes anything. It costs a few cents a video, which Reed approved. It replaces rule 11 when it ships.
  - **What stays with people:** approving the plan, approving the looks (one click), and watching the final video.
- **Song ads are mostly B-roll with the song over it.** The song leads: the storyboard and the clips are timed to the real track (as Starpop does it). Lip-sync is a rare extra, not the core.
- **A separate test site** on the same machine. The live site and its data are never touched.

## How we work
- **Branch `next`.** All Next work merges into `next` through PRs; only the Producer merges. The Producer merges `main` into `next` regularly, so live fixes carry over. Nothing from `next` goes to `main` until Reed says so.
- **The test site** runs `next` as its own Docker Compose project, with its own database, volumes, storage and worker lanes, and no shared data. It has its own deploy workflow on pushes to `next`. Its address is chosen by the Infra lead (the live Caddy keeps ports 80/443). Changes to live files (deploy/, Caddy) need the Producer's OK, and live must keep running unchanged.
- **Money.** No paid call without the Producer and Reed approving that exact test. Build and test with the free stand-ins (BS_FAKE_PROVIDERS). Log every paid call in ops/SPEND.md.
- **Tests never reach a provider** (#981). Server tests run with every key empty and no network beyond localhost; a real provider with no key refuses ("NoKey") before sending anything. A test that needs one gives it `token="test-token"` and a fake client. Emptying keys alone isn't enough in a sandbox whose proxy adds credentials, which is why the network is closed too.
- **A pass is for one head.** If a PR's code changes after a tester passed it (a fix, a rename, a merge that needed hand edits), a tester re-passes the new head before it merges (Producer, 30 Oct; #1009 merged on a moved head and broke rule 19).
- **No async route touches the database** (#993; a test keeps it so). The calls block, so an `async` route holding them freezes the whole server while it waits for SQLite's lock.
- **The bar (Reed: "think meticulously through EVERY FLOW … no dead ends").**
  - Before any screen is built, its flows are written in docs/next/flows.md: every step and every state, including empty, loading, waiting, failed, refused, over budget, editor vs owner, phone (390) and going back.
  - Each state says what the person sees and the one press that moves them on (rule 22).
  - Each PR names the flows it touches and the effects on other steps.
  - Flow-QA walks them all.
- **Saving Claude usage, nothing lost (Reed, 2 Nov).**
  - Routine work runs on the lighter model: building screens to the wireframes, small test and lint fixes, and QA test runs.
  - The top model stays for: the Director's prompts, the Song/Narrated workflow design and its core, the house-style work, final QA on any director, money or Song/Narrated PR, and Next-Lead, Next-Server, UX-Auditor and Song-Producer.
  - Running sessions keep their model. When a routine piece finishes, its next piece goes to a lighter-model session.
  - Before a session is shut down, it writes a handoff (open PRs, unfinished items, gotchas) into this file through its next PR, or sends it to Next-Lead. Next-Lead confirms the handoff is complete, and only then does the Producer shut the session down. Any PR or finding with no owner goes to Next-Lead.
  - Fewer messages. A tester sends a PASS once, to Next-Lead, with the head SHA, and Next-Lead forwards it to the Producer in one line. Only failures get detailed findings. Builders send status to Next-Lead, not the Producer.
- **Order:** 0 infra + flow map → 1 song ads → 2 styles (Disney, Song, Zack D, Skeleton) → 3 brand setup → 4 video settings (look, models, shape, flavour, language) → 5 organization → 6 cleaner layout. Layout is designed alongside, built last.

## Team
| Agent | Owns |
|---|---|
| Next-Lead | Test-site infra (compose project, deploy workflow, address), data model, docs/next/flows.md, integration of `next`, keeping the builders apart |
| Next-Server | Server work: music provider, song timing, style registry plumbing, brand setup, video settings, organization |
| Next-Screens | Web work: every screen at 390 and desktop, the cost bar, the layout |
| Director | Prompt files: House style plus the style entries, song-ad breakdown and storyboard timing |
| Flow-QA | Walks every flow in docs/next/flows.md on the test site and in tests; no dead ends; Advice vs block |
| QA / QA-2 | Review PRs into `next` as they do for `main` |

## Queued (Next-Lead keeps this list)
Every builder tells Next-Lead when a PR is up; Next-Lead checks the head and names the tester: QA (UX-Auditor's PRs), QA-3 (Next-Screens' and wording PRs), QA-10 (server PRs). As of 2 Nov, 19:45 UTC:
- **In test:** #1194 (director-first video screens; three small fixes going in: "up to free" on a held change, editor chips wrapping at 1440, "in all" on the change row), #1202 (server "style" wording), #1203 (House's blurb "Our style"), #1204 (v5 character, place, prop and media item pages).
- **v5 build (Reed approved 2 Nov, DECISIONS rule 33).** The audit of every screen against its wireframe is at https://claude.ai/artifact/Rp2NnBfwcuGbu9JQ1ifiK8 (57 boards: 3 match, 16 close, 35 differ, 3 not built). Every web PR shows each changed screen's wireframe beside a screenshot at 1440 and 390, and lists any difference with its reason; QA fails anything else. Estimate 2–3 days with both builders, plus QA rounds.
  - **UX-Auditor:** (1) #1194; (2) Clips under "Open the steps"; (3) the Scripts table, the editor Scripts table and a script's Overview (unpublished scripts too, with "Make a video · up to N" and "Publish to library"); (4a) script steps to v5: New script (Shape, Language, step order, counts), Script (Courier, autosave, counts), Directions (the grid, Notes, "3 of 5 accepted"), the Breakdown table, Variations and Publish; (4b) song takes, Import a reel and reel review.
  - **Next-Screens:** (5) the Brand area to F_BrandLook (C_Brand retired); (6) Cast & places, Media and the Media item (#1204 is part of this); (7) Studio: Needs you and its phone version, In production, Usage, My credits, Team, Settings, Setup, and the 52 px page top.
  - **Next-Server:** "Used in" on library items and a media item's read and Delete (for #1204); Needs you counting held sends; owner-set limits (for the Limits tab); Freestyle Song and Narrated types (item 2 below); brand import from a website.
  - **Decisions (Next-Lead, 2 Nov):** an editor's held send shows from the first send as a request card in Needs you (counted) and as "Waiting for the owner's OK" (editors never see Reed's name) in the editor's Sent; the video and the version's freeze still come at the owner's OK (rule 31). Make it again is the main press when a note waits.
- **After the 1 Nov reset (no builder work before):** the advisory AI check on takes, part of the four-step flow (DECISIONS rule 21), takes its spec from docs/next/take-review-checklist.md. It should cover: the transcript against the script (extra, missing or wrong-speaker lines), brand-name pronunciation (FOMO said FOH-moh), glowing or red eyes, screens (real UI, wins only, figures that match the beat), cast and continuity, and the end line. Advice only, with a ready "Change this…" note, never a block (rule 11).
- **Parked (credit cuts; small, not regressions):** a queued song take's "Waiting to start" counts from page open and resets on reload (needs the job's `created_at` on SongTakeOut plus one line in TakesStep; QA-3 on #1043). After Split and Rewrite the cost bar reads a little high (19) until a reload (16); above the charge, never below (QA-3 on #1013). An editor's character sheets and look samples made outside a video have no limit (cheap images, trusted team; Producer, 1 Nov): add a hold or an allowance if abused (QA on #1068).
- **After Reed's test, in this order (Producer and Reed, 1 Nov):**
  1. **Word splice, first** (Reed: "First thing after my test"): when a take says a word wrong ("fogo" for "fomo"), the director cuts a correctly spoken copy of the word, in the same voice, from another take or clip over the bad one, with a short crossfade, using the words check's timestamps. If no clean copy exists, it redoes the clip with a pronunciation note. A director fix alongside watch_cut's findings.
  2. **Freestyle Song and Narrated (3c):** server tools for a song take and a narration, plus the Director's prompt lines, so the director makes the song or narration first and times the plan to it (Producer, 2 Nov). Until then Freestyle Song and Narrated read "coming next".
  3. **Export director:** one .md file the site builds from its current files: director.md, the rules and craft, every look and format guide (lanes included), watch_cut.md, and a blank brand-notes template. Never a brand's own notes.
  4. The best_take swap, and stand-ins keep Advice-only takes (Next-Server, saved locally).
  5. #1104's Advice: outfit text to one plain line; the screens lock only accepts the brand's screens (Next-Server, saved locally).
  6. #1116's Advice: when the dropped person is named first in a shared Keep line, the remaining person keeps "identity and clothing stable".
  7. Skeleton's opener reads "Usually opens on…" (the Director).
  8. #1114's older notes: Plan's own button refreshes the held banner without a reload; over budget it reads "Send for approval", not "Make the plan".
  9. #1140's leftover Advice: FrameCard's "Redo storyboard first" wording, and videoHold shared with the old page instead of copied. #1125's leftover Advice is listed on that PR.
  10. #1141's Advice: a style's card says "No sheet yet" even when one of its lanes has a sheet.
  11. settings.py's item_check_scope comment still says "one frame each"; a take check uses 6 frames under every scope.
  12. Light theme: border-strong one step darker, so a selected pill's ring clears 3:1 with margin (3.17:1 against the page now; QA on #1164).
- **Next director slice, near the top (Producer, 1 Nov):** "Remake this" makes reel import → script the default path when an editor asks to remake a reel. Reed's main complaint on FOMO batch 3 was remakes that weren't copies; FOMO-Producer found reel import → script is the path that works (Director, 1 Nov).
- **Waiting:** "Make a copy in another language" (paid translation; every language but English is off until tested).
- **Dropped by Reed (2026-10-29):** new formats (Podcast, Vox, Whiteboard). Song is a format in any look (30 Oct, #1031).

## Paid tests Reed approved (2026-10-29)
Test site only; Reed presses the buttons himself once the switches are deployed; every real call goes in ops/SPEND.md.
- **Look samples:** $6. Repo variables `NEXT_REAL_LOOK_SAMPLES=true` and `NEXT_LOOK_SAMPLES_BUDGET_USD=6` (the Replicate key travels only while the first is true). Only a look's sample still and clip go real; past the budget a sample is a stand-in, said before the press.
- **Language test:** $2, by its own switch (#972).
- **Both together:** at most $10.

## Moving to main: changes that must travel together
When Reed says to bring Next to live, these go to `main` in one move, never split (Next-Lead keeps this list):
- **Five editor steps (#871).** The screens (Plan → Cast → Storyboard → Clips → Final cut, the redirects) and four server messages that now say "Approve one in Cast" instead of "in Assets" (server/app/sheets.py, storyboard.py, clip_prompts.py). Live's screens say Assets until then, so the messages must not go alone.
- **Rule 11 → the advisory check (1b P4).** DECISIONS.md rule 11 changes on live only when the check itself ships.
- **Brand setup (n08).** `brands.never_say` and `brands.end_line` stay on next, written through from `dont_list` and the default CTA line, because main still reads them. At the move, main's readers switch to the new fields and one migration drops the two columns.
- **Migrations n01–n14.** They join main's 00xx chain with one merge migration at the move (data.md, "Migration rules").

