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
- **The bar (Reed: "think meticulously through EVERY FLOW … no dead ends").**
  - Before any screen is built, its flows are written in docs/next/flows.md: every step and every state, including empty, loading, waiting, failed, refused, over budget, editor vs owner, phone (390) and going back.
  - Each state says what the person sees and the one press that moves them on (rule 22).
  - Each PR names the flows it touches and the effects on other steps.
  - Flow-QA walks them all.
- **Order:** 0 infra + flow map → 1 song ads → 2 styles (Disney, Song, Zack D, Skeleton) → 3 brand setup → 4 video settings (style, model, language) → 5 organization → 6 cleaner layout. Layout is designed alongside, built last.

## Team
| Agent | Owns |
|---|---|
| Next-Lead | Test-site infra (compose project, deploy workflow, address), data model, docs/next/flows.md, integration of `next`, keeping the builders apart |
| Next-Server | Server work: music provider, song timing, style registry plumbing, brand setup, video settings, organization |
| Next-Screens | Web work: every screen at 390 and desktop, the cost bar, the layout |
| Director | Prompt files: House style plus the style entries, song-ad breakdown and storyboard timing |
| Flow-QA | Walks every flow in docs/next/flows.md on the test site and in tests; no dead ends; Advice vs block |
| QA / QA-2 | Review PRs into `next` as they do for `main` |
