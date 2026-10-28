# Phase 2 spec: what we borrow from Starpop

For Reed. Docs only: nothing gets built until you approve it. The scope is yours (2026-10-28). Background is in [findings.md](findings.md), [README.md](README.md) (Starpop) and [ours.md](ours.md) (us).

**Sizes:** S = one PR, about a day. M = 2–4 PRs. L = 5 or more PRs, or a new screen flow.

## At a glance

| # | Feature | What changes for you | Size | Build order |
|---|---|---|---|---|
| 1 | Song ads | A new script kind: your lyrics are sung word for word over a Pixar music video | L | 1st |
| 2 | Style registry | Pixar is a setting; 11 more looks wait as switched-off entries | M | 2nd |
| 3 | Brand setup | One place for everything a brand must always get right, used by every step | M | 3rd |
| 4 | Video settings | Style, video model, picture model and language per video; Auto by default; price first | M | 4th |
| 5 | Organization | Projects, a shared media library, "Preferred", going back to an earlier version, a cost log | L | 5th |
| 6 | Cleaner layout | Three columns everywhere and one cost bar | L | Designed alongside 1–5, built last |

**Out of scope** (as you said): the dialogue check, and Premiere/CapCut export.

**Two rule changes this needs, said plainly:**
- **Rule 20 (prompting follows only the official Seedance and Nano Banana docs).** Feature 2 uses style guidance from Starpop's public skill files. You've effectively granted this. Proposed wording: *"Style guidance (how a look is described) may also come from the style registry, which is built from Starpop's public skill files and our house style. How to prompt each model still follows only the official docs."*
- **Rule 2 (videos stay 480p; 1 credit = 1 second of 480p Seedance).** Feature 4 lets a video use another model. Proposed: *1 credit stays $0.1028. Each model is priced in credits at its real cost. 480p Seedance 2.5 stays the default.*

---

## 1. Song ads (first)

**The idea.** Starpop's song flow, run our way. Your lyrics are the script, and they never change (rules 19 and 31). The song is made first; the storyboard follows its real timing. The hero lip-syncs the hook and the last chorus, and every other shot is silent picture under the song.

**What you see (owner, writing a script)**

| Step | Screen |
|---|---|
| New script | A new choice next to Story: **Song**. |
| Song (replaces Script) | Two boxes. **Lyrics**: paste them; `[Verse]` and `[Chorus]` tags are fine. **Style**: one line, e.g. "pop, female lead, 120 BPM, upbeat, modern polished", pre-filled from the brand's music style. Plus a button **"Write 2 song directions for me"** (about 3 credits). It shows two options side by side (concept, lyrics, style, visual concept), one marked Recommended. Picking one copies its lyrics into the box, and from then on they're yours and locked. With no lyrics and no pick, nothing can be made. |
| Make the song | "Make 2 takes · N credits". Two players; **Preferred** on one, switchable. "Make 2 more". Each take shows its length (the song decides the video's length). |
| Cast, Breakdown, Publish | As today. The breakdown is built from the preferred take's real word timings. Each shot gets a time range of the song and a **Sung** or **B-roll** mark. Default: the hook and last chorus are Sung, everything else B-roll. You can flip any shot. |

**What an editor sees (making the video):** the same five steps. Breakdown shows the song's waveform with the shots under it. Storyboard is as today. In Clips, Sung clips show "lip-syncs 0:00–0:06". Downloads lays the full song under the stitched video (free).

**How it's made**
- **Music model.** Suno, which Starpop uses, isn't on Replicate. From a free check of Replicate's catalogue: **MiniMax Music 2.6** takes the lyrics as their own field and has an "auto-write lyrics" switch, which we keep off so the words are sung as written. That makes it the pick. ElevenLabs Music has no lyrics field, so it can't lock words. Lyria 3 Pro only takes lyrics inside its prompt. The price per song isn't confirmed yet; a free price check comes first, then you approve one paid test.
- **Timing.** Our local Whisper already gives word timings, so it's free.
- **Lip-sync.** Seedance 2.5 accepts an audio slice for lip-sync. However, its first-frame setting can't be combined with audio. On Sung clips, the storyboard still and the character sheets therefore go in as reference pictures instead of the first frame. B-roll clips stay exactly as today, with sound off.
- **Slicing.** The song is cut only on musical beats, never mid-word.

**Data changes**

| Where | Change |
|---|---|
| Scripts | A `kind` (story or song). |
| Script versions | Lyrics stay the version's text, plus a `style_line`. |
| New: song takes | Version, file, word timings, length, preferred. |
| Breakdown shots | `start`/`end` in the song, and `sung` yes/no. |
| Clips | The song slice they lip-sync, if any. |
| Final video | The song file laid underneath. |

**Reuses:** the script flow, the cast read, looks, Breakdown/Storyboard/Clips, Approve all, Undo, takes, the free stitch, Whisper and the job queue.

**New:** the song step, the music-model adapter, song takes, sung/B-roll shots, audio slices for Seedance, and laying the song under the stitch.

**Risks**
- **Rule 29 (one scene or action per clip):** a fast B-roll run could cross places. Clips still split by scene; the song is sliced to match each clip, never the other way round.
- **Rule 18 (end line):** the last sung line or a short spoken tag names the brand and where to find it. Advice only.
- **Rule 22 (no dead ends):** a failed song shows the reason, gives the credits back and offers Try again. On Starpop it failed silently with no retry.
- **Lip-sync quality:** dropping the first frame on Sung shots may loosen faces. One paid test of a 15-second song excerpt before anything else.
- **Cost:** 2 song takes per request, plus Sung clips at normal video prices. The estimate includes the song.

## 2. Style registry

**What you see:** a **Style** picker on a script, defaulting to the brand's style, with cards showing one sample still each. Pixar is on. The others (claymation, anime/comic, paper, watercolor, wool/crochet, whiteboard, skeleton, Vox, podcast, Zack D) show "Off" for editors until you switch them on. Song is a format, not a look (feature 1).

**How it works:** one config file per style, not code. Each file holds:
- a style paragraph, plus a character paragraph used only when people are in frame
- a camera paragraph and a motion line
- the default picture model
- a failure/fix list ("hair as fine strands: make another, don't add detail")
- banned words, and whether it's a look or a format (podcast and whiteboard need their own flows, so they stay off)

The Pixar entry = our house style (the @nateassets line) plus Starpop's blocks where they agree. The Director merges them and runs one A/B test (paid, needs your approval).

**Data changes:** a `styles/` folder of config files. A `style` on scripts and videos. Character sheets are per style: a Pixar sheet can't be used in claymation, so a library character gets one sheet per style, as a new version on the item (versions already exist).

**Reuses:** the house-style line, the prompt builders and sheet making. **New:** the config loader, the picker and per-style sheets.

**Risks:** rule 20 (above). Sheets per style double the look cost for a non-Pixar video, so it's shown before making. Other looks are untested on our pipeline, so each one is switched on only after a sample you've approved.

## 3. Brand setup

**What you see:** a Brand page with clear sections. Each says where it's used ("Used in: script, stills, clips").

| Section | Today | Adds |
|---|---|---|
| Logo, colours, fonts, style board | ✔ | — |
| Products and bags (variants) | ✔ (Products tab) | A short description and the main claim per product, used in scripts |
| App screens and their moments | ✔ | — |
| Voice and tone | One notes box | Audience; how the brand talks; a **Do** list and a **Don't** list (today's "never say" becomes Don't) |
| CTA lines | One end line | Several, one marked default; adapted per video (rule 18) |
| Default cast | — | Library characters preloaded into every new script for this brand |
| Music style | — | A genre/style line for song ads |
| Default style and language | — | The starting point for new scripts |
| Import from website (nice-to-have) | — | Paste a URL: logo, colours, description and products are pre-filled for review (about 3 credits; owner only). Nothing is saved until you press Save. |

**How "every step uses them":** one brand summary is built in code from these fields and given to every writing and prompting step: script, enhance, variations, breakdown, frames, clips and lyrics. It replaces the scattered pieces each prompt reads today. It's never left to the AI to fetch.

**Data changes:** new columns on brands (`audience`, `do_list`, `cta_lines`, `default_cast`, `music_style`, `default_style`, `default_language`); `never_say` moves into `dont_list`; a product description and claim go on the product records.

**Risks:** prompts get longer, so the summary is kept short. Rule 26: the shared summary must delete the per-prompt copies it replaces.

## 4. Video settings: style, model, language

**What you see:** a small **Video settings** row at the top of every video. It also shows on the script's "Make this version".

| Setting | Choices | Default |
|---|---|---|
| Style | From the registry (switched-on ones) | Brand's style |
| Video model | Auto, Seedance 2.5, Seedance 2.0, plus any you add | Auto = Seedance 2.5 at 480p |
| Picture model | Auto, Nano Banana 2.1, Nano Banana Pro | Auto = Nano Banana 2.1 |
| Language | English, Spanish, and others you switch on | Brand's language |

Each choice shows its price in credits (per second or per still). The budget estimate updates before anything runs. Editors see credits only (rule 4).

**Language:** the script is written in that language, and every spoken line in a clip prompt says "in Spanish". Today it's hard-coded "in English". The checks that assume English (the end line, word-for-word lines) follow the chosen language.

**Data changes:** `video_model`, `image_model` and `language` on videos, next to `style`. The model catalogue gets each model's credit price.

**Risks:** rule 2 (above). Switching model mid-video makes earlier takes "Out of date" (they're kept, as today). Non-English lip-sync quality is unknown, so each language gets a sample test before it's switched on.

## 5. Organization

**What you see**
- **Projects:** a brand holds projects (e.g. "Iron Paws, November launch"). A project holds scripts, videos and quick clips. Everything works without one ("No project").
- **Media:** one page with every still, sheet, take, song and final video across brands. Filters: brand, project, kind, who made it. Each item links back to the step that made it ("Open in Clips").
- **Preferred:** the picked take already exists. The same mark goes on stills, looks and song takes, and later steps use the preferred one.
- **Go back:** each step keeps its versions (breakdowns already do; storyboards and clip prompts keep the earlier ones). "Versions" lists them with **Go back to this**, with Undo.
- **Cost log:** the Usage page adds per-project and per-video rows (dollars for the owner, credits for editors).

**Data changes:** a new grouping table. The database already calls a video a "project", so it gets another internal name; you only ever see "Project". There's a `folder` link on scripts, videos and quick clips, a `preferred` mark on stills, looks and song takes, and a version list on storyboards and clip prompts.

**Risks:** rule 26 (the media page should reuse the existing lists, not copy them). Going back to an old breakdown marks later steps out of date (as today, never a dead end, rule 22).

## 6. Cleaner layout

**What you see:** the same three columns on every page.
- **Left:** brands → projects → scripts and videos, with a status on each ("Making", "Needs you").
- **Centre:** the work.
- **Right:** this video's media (takes, stills, song).

There's one bottom **cost bar** that says what's about to run and its price before any paid press. On phones (390 wide) the side columns become tabs, with no sideways scroll and buttons at least 44px.

**How:** the Designer draws it first, building on the Screening room redesign you picked, and you approve it. Then it's built page by page, each PR deleting the old layout it replaces.

**Risks:** it touches every screen, so browser tests change. It's built last so it wraps the finished features instead of being redone.

---

## Build order

| Order | Work | Why here |
|---|---|---|
| 0 | Free price check of MiniMax Music 2.6; one paid 15-second song + lip-sync test (asks you first, logged in SPEND.md) | Proves the song idea before building |
| 1 | Song ads | Your top pick |
| 2 | Style registry (Pixar only on; others as off entries) | Small, and lifts the look of every video |
| 3 | Brand setup (website import last) | Feeds the songs' music style and every prompt |
| 4 | Video settings | Needs the registry and the brand defaults |
| 5 | Organization | Biggest data change; easier once the features above are settled |
| 6 | Layout | Designed during 1–5, built last |

Stabilization (rule 25) is still on. None of this starts on the live site until you say stabilization is done, or you choose (b) below.

## Where it gets built

| | (a) On the live site, behind an owner-only switch per feature | (b) A separate test site on the same machine |
|---|---|---|
| What it is | Every feature merges to main, hidden from editors until you turn it on | A second copy (its own database, files and web address, e.g. test.srv2091584…), deployed from a test branch |
| Good | Real brands and data; no second deploy; switching on is instant | Editors on the live site are never affected while stabilization runs; risky data changes (organization, song shots) are tried on a copy first |
| Bad | Unfinished code and switches sit in the live app (rule 26 says delete when done); database changes hit live data; a bug can still reach editors | A second database and deploy to keep running; its data drifts from live (we copy brands across); paid tests still spend real money |
| Cost | None extra | A little more server memory; the Release agent runs it |

**Recommendation: (b), a test site.** Editors are still hitting breakages on live, so new features should prove themselves elsewhere first. The Release agent's job already says "staging then live". Each feature moves to live once you've tried it on the test site. You decide at approval.
