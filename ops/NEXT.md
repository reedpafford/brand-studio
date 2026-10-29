# Brand Studio Next (the test site)

Reed approved the Phase 2 spec on 2026-10-28 (docs/research/starpop-2026-10-28/spec.md), with the changes below. Every agent on Next reads this, the spec, and the Current rules in ops/DECISIONS.md first.

## What Reed decided (2026-10-28)
- **Styles.** Our current look stays as the **House style** (the default). Starpop's styles are added as registry entries. Their order: **Disney Pixar, Song, Zack D, Skeleton** first, then the rest. Style guidance may come from the providers' docs and the styles studied in docs/research/starpop-2026-10-28/ (rule 20).
- **Models.** Other image/video models are allowed, each priced in credits at its real Replicate cost (rule 2). 480p Seedance stays the default.
- **Music.** Reed asked about a Suno API key. Suno has no official public API (only unofficial wrappers), so the music step sits behind one provider interface. MiniMax Music on Replicate (exact lyrics) comes first, with a slot for Suno if Reed gets real access. Any key goes in the server's environment through the deploy secrets, never in chat or code.
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

## Moving to main: changes that must travel together
When Reed says to bring Next to live, these go to `main` in one move, never split (Next-Lead keeps this list):
- **Five editor steps (#871).** The screens (Plan → Cast → Storyboard → Clips → Final cut, the redirects) and four server messages that now say "Approve one in Cast" instead of "in Assets" (server/app/sheets.py, storyboard.py, clip_prompts.py). Live's screens say Assets until then, so the messages must not go alone.
- **Rule 11 → the advisory check (1b P4).** DECISIONS.md rule 11 changes on live only when the check itself ships.
- **Migrations n01–n07.** They join main's 00xx chain with one merge migration at the move (data.md, "Migration rules").

