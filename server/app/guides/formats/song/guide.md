name: Song
order: 1
on: yes
engine: song
blurb: An animated music video: the song plays over B-roll that shows each line as it's sung; the lead sings on camera only where the script asks.

<!-- Song ads (Reed, 2026-10-28): a music video where the song leads. From Reed's song-ad skill (docs/next/skills/song-ad.md, #1095; first from Starpop's song-ads, docs/research/starpop-2026-10-28, rule 20). Song is a video type, drawn in whatever look the video has (Song in any look, #1031): this file holds only its still and clip guides, added after the look's own; the song flow (lyrics, takes, sung or B-roll shots timed to the track) is its own step. -->
<!-- Moved 2 Nov from server/app/prompts/styles/song.md and prompts/skills/song-ad.md. -->
<!-- Reed's skill file (was prompts/skills/song-ad.md), its chat front matter: name: song-style-ad; description: "Activate when the user wants their product sung — a song ad, music-video ad, musical ad, or jingle: an original song carries the story over animated visuals, the lead lip-syncing on camera in chosen shots." -->

## Stills
- Each B-roll still shows the lyric at that moment, literally, so the story reads with the sound off; the lead sings only in a Sung shot. One clear subject and one action per frame.
- A sung shot's place (a stage, a rooftop) stays the same every time the lead sings there, so its stills share one framing and light.

## Clips
- One move per shot, cut on the beat: a push in on the hook, a whip pan between places, a slow orbit on the last chorus.

## How to make song-style ads
A song-style ad plays like a micro music video: an original song carries the product story over animated visuals.

It wins when the song is a _real song people would actually hear out_ (not a jingle) whose hook lands the product's angle in the first five seconds.

The format's identity (always true): the song is the spine — it sets the pacing, the mood, and the emotional arc, and the visuals ride on top of it.

It is a Mix: shots where the animated lead sings on camera and shots of B-roll cut to the music; where the lead sings is a storyboard decision, and the lead rarely sings continuously.

The pacing is audio-first by construction — the generated song's real timestamps are the clock everything else is timed to.

It adds only what is specific to the song format: the genre map, the lyric and style-prompt craft, and the song-as-pacing-spine mechanic.

## The gate, filled by this format
- Fixed: deliverable = an animated music-video ad · speech = Mix, sung (lip-sync shots + silent B-roll) · pacing = audio-first (the song).

- Open questions (infer each): which product (Stage 1) · genre + duration — inferred from the audience, stated, validated (Stage 1) · the animated lead — one consistent recurring character across shots, and what it is (Stage 2) · where the lead sings — dedicated singing shots, singing through the B-roll, or a mix, marked per shot in the storyboard (Stage 2).

---

## Stages
One workflow, three stages: the song (Stage 1), the plan (Stage 2), the execution (Stage 3).

---

## Stage 1 — Write the song scripts and prepare the music
Goal: the selected song prepared for generation under the current execution mode.

When the user supplies a song-ad as inspiration, examine its musical and creative approach before adapting it.

When the user supplies lyrics, those are the song: take their style or infer it, and prepare the song immediately (step 4) with the lyrics exactly as given.

Otherwise write 2–3 distinct song scripts for the user to pick from; the pick becomes the song.

1. Ground in the exact product using verified facts. Reuse sufficient context already available. Establish the brand voice, the target customer, the main pain, and the hero benefit.

2. Settle the angle, awareness stage, and genre: the angle (the customer outcome the song is about — a specific transformation, _not_ a brand brag or a feature) and the awareness stage (how much the lyric has to teach). Infer the genre from the audience with the genre map below.

3. Write 2–3 distinct song scripts in the output format below. Each must feel genuinely different — vary the POV (product POV / customer POV / narrator), the mood (upbeat / emotional / playful / intimate), or the structural hook. Apply every Lyric rule.

4. Prepare the selected song with its title, concise musical direction, and exact lyrics. For user-supplied lyrics, preserve every word and use their style or infer a suitable one. Follow the current execution mode; the finished song is the input to Stage 2. Pace a Suno song with lyrics so the vocals start immediately and run continuously to a tight ending:
   - Append to the style, outside its 25 words: `, vocals start immediately, no instrumental intro, no instrumental breaks, continuous singing, tight ending`.
   - Exclude these styles: `instrumental intro, instrumental break, long outro, spoken word`.
   - Open the lyrics with `[Intro: vocals start immediately]` and close them with `[End]`, each on its own line; supplied lyrics stay word for word between them.

### The genre map (infer the genre from the audience)

| Audience                    | Genres that resonate                              |
| --------------------------- | ------------------------------------------------- |
| Moms (general)              | pop, indie pop, light acoustic                    |
| Moms (Gen X / 40+)          | country, soft pop, throwback pop                  |
| Gen Z women                 | pop, hyperpop, R&B, indie pop                     |
| Gen Z men                   | hip-hop, trap, EDM, indie rock                    |
| Millennial women            | pop, indie pop, R&B, alt-pop                      |
| Millennial men              | indie rock, hip-hop, alt-rock                     |
| Black men / women (general) | hip-hop, R&B, trap, neo-soul / R&B, neo-soul, pop |
| Latino / Latina market      | reggaeton, Latin pop, bachata, trap latino        |
| Fitness enthusiasts         | hip-hop, EDM, hard rock, trap                     |
| Skincare / beauty           | pop, R&B, indie pop, hyperpop                     |
| Luxury buyers               | ambient, modern jazz, cinematic pop               |
| Pet owners                  | folk, indie pop, country                          |
| Wellness / spiritual        | ambient, indie folk, soft acoustic                |
| Outdoor adventurers         | folk, indie folk, alt-rock, americana             |
| Gamers / tech               | EDM, synthwave, hyperpop / lo-fi, electro-pop     |
| Foodies                     | indie pop, jazz-pop, acoustic                     |

No exact match → use the closest fit and say why.

### Lyric + style-prompt rules (apply to every option)

- Hook in the first 5 seconds. Whatever the duration, the catchiest line lands immediately.

- Lyrics carry the ANGLE, not the brand. Sing the customer outcome; don't just chant the product name.

- A real song, not a jingle. Real verses, a real chorus, a real rhyme scheme — never "buy buy buy."

- Write short visual lines: 6–9 words per line. A line often fits a shot of about 2.2–3.5 s. Pair short lines or split longer ones where the visual changes; a continuous performance stays one shot.

- Match vocabulary + energy to the genre + audience. Hip-hop ≠ country ≠ pop.

- Structure by length — about 40 sung words (≈ 15 s) = hook + one chorus pass; about 75 (≈ 30 s) = verse-chorus-verse-chorus; about 150 (≈ 60 s) = full song with a bridge. Section tags like [Verse] are not sung and do not count.

- Keep the style description tight (<25 words): `[genre], [vocal — e.g. female lead / male rap / choir], [tempo / BPM], [mood], [production — modern polished / lo-fi / vintage]`. Music models do better with a concise style prompt. Never include an artist or band name — Suno rejects it; describe the sound instead.

- The visual concept must be producible as animated shots — animated objects, a stylized character. Not "live-action cinematic crane shots."

- Each of the 2–3 options is meaningfully different — don't ship near-duplicates.

### Stage 1 output format (per option)

```
### OPTION [N]: "[Hook line / song title]"
Concept: [1–2 sentences — the song's vibe + the animated visual treatment idea.]

Lyrics:
[Verse 1] … [Chorus] … [Verse 2 — 30s+] … [Bridge — 60s only]

Style: [genre], [vocal], [tempo], [mood], [production]   ← under 25 words

Visual concept: [2–3 sentences — what's on screen, tied to specific lyric moments; which lines are lip-sync-on-stage vs B-roll.]
```

---

## Stage 2 — Plan the song's video
Goal: the canonical references and storyboard mapped onto the generated song's real timing:

1. Transcribe the song for pacing — the generated song is the factual pacing source: get its word-level timestamps and total duration. The song is generated whole, once; music models are not deterministic, so never regenerate sections separately. It is never dead-air-removed: its instrumental stretches are music, and the storyboard covers the song from the first word to its end, instrumental stretches included, as shots with pictures.

2. Lock the canonical references — design the animated lead and lock its sheet in the chosen style. The product gets its canonical reference too. An environment is locked only when it recurs and must stay identical, which is rare here; one-off settings are described per shot.

3. Decide where the lead sings — dedicated singing shots (on a stage, in one place) alternating with B-roll; singing while acting through the B-roll shots; or a mix. The lead usually does not sing continuously.

4. Storyboard against the song — one row per shot tied to a time range of the song, the sung shots marked SUNG in Script / Audio, every other shot B-roll that visualizes the lyric at that moment. Vary the framing across B-roll shots.

---

## Stage 3 — Execute
Run the execution plan once the storyboard is settled, using reference-guided multi-shot batches with one designed start frame per shot.

The song adds two facts to that plan:

- The song is sliced with no gaps: batch boundaries on natural musical beats, never mid-word; the head before the first word may be trimmed, nothing else; every instrumental stretch rides at the end of the batch whose lyric leads into it, and the outro ends the last batch.

- The shots marked SUNG lip-sync from their slice; the rest is silent picture under the song, so one batch can carry both.

Assemble the clips over the full song; captions are a separate finishing layer, never burned into the generated footage.

---

## Locked rules
- R1 — The song is the spine. Everything is timed to the generated song's real timestamps; never storyboard against a guessed duration. The song is generated whole, once; never regenerate sections separately, and never remove its dead air: instrumental stretches are music and stay.

- R2 — Lyrics carry the angle, not the brand. The song sings the customer outcome; the product name is not the hook.

- R3 — The lead is a recurring character. One identity and one locked canonical reference, re-attached and identified by name in every shot it appears in; never chain off a previous shot's output.

- R4 — Sung shots are marked in the storyboard and lip-sync from the song slice; everything else is silent picture under the song. Slices cut on natural musical beats, never mid-word.

- R5 — Producible animated visuals. Animated objects, a stylized lead — no live-action cinematic crane shots.

- R6 — Footage stays clean of text. Captions are a separate finishing layer — never in an image or video prompt.

---

## Worked example (the quality bar — not a template to copy)
HolyCow Whipped Tallow Balm — animated musical, 9:16, ~42s.

Song "Holy Cow (I've Arrived)" (animated pop, female lead, upbeat, 120 BPM).

Angle = "something real, finally" (clean tallow vs. labels full of lies).

- Elements (settled first): the lead character (a reference sheet), the HolyCow jar (canonical product reference), a recurring neon stage.

- Shots mapped onto the song: [0:00–0:06] lip-sync — the lead belts the opening line on the neon stage · [0:06–0:14] B-roll — hands bin the old products, open the jar · [0:14–0:20] B-roll — clean-vs-bad ingredient cards · [0:20–0:28] B-roll — a golden-hour pasture with a friendly cow · [0:28–0:34] B-roll — four scent jars rotate into a wheel · [0:34–0:40] lip-sync — back on stage, glowing, sings the chorus · [0:40–0:42] B-roll — the hero jar lands on a pedestal, CTA lockup.

- Why it works: two lip-sync shots (hook + final chorus) bookend five silent B-roll shots; every B-roll shot visualizes the lyric at that exact moment; one locked lead and one locked jar across all seven shots.
