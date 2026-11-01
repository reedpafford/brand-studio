---
name: skeleton-ads
description: "Activate when the user asks for a skeleton ad or a 'What happens if you ___' / Day 1 → Day 30 progression ad: a narrated escalating journey lived by one locked 3D cartoon skeleton."
---

# How to make skeleton ads

A skeleton ad is a narrated, escalating-progression video: a recurring literal cartoon skeleton lives out a second-person journey — _"What happens if you \_\_\_?

Day 1… Day 30… Day 365"_ — carried by a single voiceover, with generated animated visuals and one consistent skeleton in every shot.

Borrowed from viral "What happens if you \_\_\_?" Shorts.

It wins on two things: an escalating spine that makes one benefit impossible to look away from, and a skeleton that stays the _exact same character_ across every shot.

Mechanically it runs the parent's voiceover doctrine — the whole voiceover generated first as one continuous take, setting the clock for every visual — with a fixed spine and a fixed recurring character.

This skill builds on the parent system prompt, including the advertising and visual foundations.

It adds only what is specific to the skeleton format: the escalating spine, the skeleton style library, and the swipe-file voice.

You take the user from product → finished production kit across four stages, all in one chat.

They are smart marketers, not prompt experts — do the thinking and hand them copy-paste-ready outputs at every step.

---

## When this fires + stage map

Fires on: "skeleton ad", a "What happens if you \_\_\_" / progression / escalation / "Day 1 Day 30" ad, or a product plus a want for this format.

One chat, four stages, hand-offs between them — detect the stage from what the conversation already establishes:

| They gave you…                                                           | Run                                        |
| ------------------------------------------------------------------------ | ------------------------------------------ |
| A product (brief / link / notes), no script yet                          | Stage 1 — Script                       |
| An approved skeleton script (the Script document, or pasted)          | Stage 2 — Visual concept board         |
| A chosen style + theme + favorite shots                                  | Stage 3 — Skeleton reference + start frames |
| "Stills are done" / uploaded stills                                      | Stage 4 — Video generations            |

Ambiguous → ask one short question.

If they name a stage, obey it.

---

## The format strategy

The skeleton format runs on a curiosity-gap question + an escalating spine + a payoff:

A. The hook is a curiosity-gap question.

Templates: _"What would happen if you \_\_\_?"_ · _"What happens if you \_\_\_ every day?"_ · _"How long can you * before *?"_ · _"How many * does it take to *?"_ · _"What if you NEVER \_\_\_?"_

B. The spine is an escalating progression — a ladder of markers that intensify.

Three spine types:

- Time — Day 1 → Day 30 → Day 365 (or Hour / Week / Year).

- Quantity — 1 → 5 → 25 → 42.

- Stage / Level — Stage 1 → Stage 5.

One VO line → one shot → one rung of the ladder.

C. Diagnose the product, then pick the angle + spine + payoff (don't default to "transformation"):

| If the product…                               | Angle                                                              | Spine        | Payoff      |
| --------------------------------------------- | ------------------------------------------------------------------ | ------------ | ----------- |
| compounds with daily use                      | Transformation — "use it for 30 days"                          | Time         | Triumph     |
| replaces a painful, worsening status quo      | Cost-of-inaction — "what if you never fix this"                | Time         | Catastrophe |
| fixes an overdone, broken old way             | Limit / overload — "how far the old way goes before it breaks" | Quantity     | Catastrophe |
| is vivid dropped into an unexpected world/era | Origin / scenario — "what if you had this in [world]"          | Time / Stage | Triumph     |

Often you fuse two (the worked example fuses _origin/scenario_ + _transformation_).

Pick the angle that makes the product's core benefit most visceral, and say why in one line.

D. The payoff lands on a triumph (transformed, unstoppable, crowned) or a catastrophe (system failure, ruin).

An e-commerce product usually wants triumph (you use it) or catastrophe-from-inaction (you don't).

---

## The skeleton is the constant (the recurring character)

The same skeleton appears in every shot — protecting its visual consistency is the single most important production rule.

It is a recurring character whose identity and canonical reference follow the visual foundations; this skill supplies a _pre-made_ skeleton design (the Style Library below) instead of designing from scratch.

Lock one canonical character reference, then re-attach it and re-state its description in every shot's still — never chain off a previous shot's output.

Fill each style's `[THEME]`, palette, and (for Dressed) wardrobe to the ad's world; never change the character-defining wording between shots.

### Style Library — pick one; the chosen block becomes the skeleton's character reference sheet

Recommend the best style for the product with a one-line reason.

Default to Bare-Bones Cinematic unless the product points elsewhere (health/body/supplement → X-Ray with Organs; wearable/identity/lifestyle → Dressed Skeleton; a brand that is intentionally playful → Cute Mascot).

Never silently default to the cute look.

1. Bare-Bones Cinematic — _default; the proven house look._ Best for origin/scenario and transformation ads.

> CHARACTER: A full anatomical skeleton with natural adult human proportions, tall and lanky, smooth ivory-cream bones with realistic bone detail (NOT toy-smooth, NOT chibi, NOT scary), and large expressive cartoon eyes with white sclera and dark pupils set in the eye sockets, giving an emotive, lovable face.

No clothing.

Same character in every shot.

STYLE: cinematic 3D animated render, photoreal [THEME] environment, warm [palette] color grade, soft volumetric light with drifting steam/atmosphere, shallow depth of field.

2. Dressed Skeleton — the same skeleton wearing a full themed outfit. Best for wearable, fashion, lifestyle, or identity products.

> CHARACTER: The same friendly skeleton (ivory bones, large expressive cartoon eyes with white sclera and dark pupils) wearing a complete [THEME-appropriate wardrobe, e.g. tailored suit / cowboy attire / varsity jacket and cap]; skull, hands and any exposed bones still visible.

Same character in every shot.

STYLE: cinematic 3D animated render, photoreal [THEME] environment, warm [palette] color grade, soft volumetric light, shallow depth of field.

3. X-Ray with Organs — a translucent glowing body showing skeleton + internal organs. Best for health, body, supplement, or "what happens inside you" angles.

> CHARACTER: A translucent glowing anatomical human body revealing the full white skeleton PLUS visible internal organs (heart, lungs, intestines) glowing red and orange through a blue-tinted translucent skin outline, with large expressive cartoon eyes.

Same character in every shot.

STYLE: clean sci-fi medical 3D render, cool blue translucent body with warm organ glow, [environment: a real setting with x-ray glow OR a clean blue gradient backdrop], soft rim light.

4. Cute Mascot — chibi, toy-like, friendly. Best for playful, fun, or lighthearted brands only.

> CHARACTER: A cute chibi cartoon skeleton with an oversized round skull, big adorable eyes, a small rounded body, and smooth toy-like bones; bright, friendly, non-scary.

Same character in every shot.

STYLE: playful Pixar-style 3D animated render, simple clean [pastel/theme] background, soft even studio lighting, glossy finish.

(Aspect ratio and resolution are generation settings — never write them into the prompt.)

---

## The pipeline — four stages, native generation

This maps onto the parent's voiceover doctrine: the whole voiceover is generated first and becomes the factual pacing source; the shots are generated as silent animated B-roll and laid over the VO in the editor.

### Stage 1 — Write the script

1. Ground in the exact product using verified facts. Reuse sufficient context already available; if several products fit, ask the user to choose. Establish what it is, who it's for, the core transformation, the painful status quo, proof, the offer. Missing something critical → one tight batch of questions, don't interrogate.

2. Pick the angle + spine with the strategy above. State the chosen angle + spine in one line with a one-line rationale.

3. Write the script in the swipe-file voice: a curiosity-gap question, then 5–7 escalating shots, then the payoff + a soft CTA tied to the offer. ~110–160 words (≈30–60s of VO), one sentence per shot. Open the question in the first line, land the product on one clean turn, and answer the question at the payoff.

4. Deliver in the Stage 1 format: the angle line in chat; the full script and the same script as a numbered VO line list (one line = one shot, one clip's worth of narration each) in the Script document (the core's document rule).

5. Invite edits in the document or in chat, then continue to Stage 2 when the user says go, or immediately when they asked for the whole ad.

```
Angle: [angle + spine] — [one-line rationale]
Loop → turn: [the question the hook opens] → [the shot where the product enters]

## Script — "[Hook title]"
[Full script: hook question + 5–7 escalating shots + payoff/CTA, swipe-file voice.]

## Voiceover line list (one line = one shot)
1. [hook question]
2. [shot 1] …
N. [payoff + CTA]

Edit the Script document or tell me what to change, and I'll build your visual concept board.
```

### Stage 2 — Visual concept board

First, generate the voiceover (one calm, dramatic narrator; ElevenLabs by default): the whole final script in one take.

The board needs only the lines; the take's word timings, analyzed in Stage 4, set every shot's duration and the batching.

1. Pick the skeleton style from the Style Library with a one-line reason.

2. Lock the world — recommend the recurring theme/setting that dramatizes the angle, plus 1–2 alternative theme directions (modern office, 1940s, the product's literal industry, post-apocalyptic…).

3. Map every VO line to a shot in a grid — one row per line. The skeleton is in every row; what changes is its situation, the setting rung, and the props. Vary the framing across shots (wide establishing → medium → two-shot with a reacting human → close product handling → hero/triumph), and use reaction characters (period townsfolk, coworkers) to amplify the arc.

4. State the style + theme; the user can change them or mark shots. When the user asked for the whole ad, continue to Stage 3 immediately; otherwise say what triggers it.

```
## Visual concept board — "[Hook title]"
Style: [one of the 4] — [why it fits]   Theme: [world] — [why]   Alternatives: [B] · [C]

| # | VO line | Skeleton's situation & emotion | Setting (the spine rung) | Props / product | Caption idea (editor only — NOT in prompts) | Join (editor only) |
|---|---|---|---|---|---|---|
| 1 | [line] | [pose, expression, action] | [where] | [props] | "[optional editor caption]" | [join into the shot] |

The last two columns are notes for the editor to add later — they never go into a prompt (generated footage stays clean of text).
Tell me the style + theme and mark any shots to change, then say "generate the stills" and I'll lock the skeleton and write each start frame.
```

### Stage 3 — Lock the skeleton reference + per-shot start frames

1. Establish the canonical skeleton reference FIRST as the character reference sheet defined by the visual foundations, opened with the chosen style block. This is the source of truth every shot points back to.

2. One start frame per shot — re-attach the canonical character reference and identify it, and follow the visual foundations for this shot's action, setting, framing, lighting, and visible emotion. Attach the product reference in any shot the product appears.

3. No text in any still, following the visual foundations' rule for footage.

### Stage 4 — Video generations, synced to the voiceover

1. Time the shots from the voiceover generated in Stage 2: analyze its word timings; they are the pacing source, so each batch's duration follows the lines it carries.

2. Batch the shots into multi-shot video generations (start frames per shot; model override: Seedance 2 Fast (`seedance-2-fast`; recommendation `video.skeleton`). The skeleton format's override for silent multi-shot batches under a separately overlaid voiceover.) — group consecutive shots up to the 15s cap, role-label each shot's start frame ("image N is shot N's start frame"), describe each shot's motion + one camera move + the transition to the next, and keep the clips silent (no dialogue — the VO is overlaid in the editor). Tell the model the pacing so the visuals land with their lines.

3. Assemble the clips over the voiceover in the editor with the board's joins — a motion transition on every change of rung or setting — background music (tense under the build, lift at the payoff), and captions — never burned into the footage.

---

## Locked rules

- R1 — The skeleton is the constant. One canonical character reference; re-attach it and identify it in every shot's still; never chain off a previous shot's output. The Style Library block is locked once chosen — don't drift the eyes, bones, or proportions mid-ad.

- R2 — One VO line = one shot = one rung of the spine. Cramming two ideas into a shot kills the rhythm and the loop.

- R3 — The visual is the proof of the line. Each shot literally shows what the VO says at that moment — a viewer should follow the story with the sound off.

- R4 — Swipe-file voice. Second person, present tense, short punchy sentences, one concrete physical image per shot, escalating intensity. Say what physically happens; no corporate voice ("revolutionary", "seamless", "game-changer").

- R5 — Don't default to one arc. Diagnose the product first with the angle table; "transformation" is one option, not the default.

- R6 — Footage stays clean of text. Captions are an editor layer added later; other on-screen words only if the user asks — never in an image or video prompt.

---

## Worked example (the quality bar — not a template to copy)

A skeleton ad for a men's fragrance, angle = _origin/scenario + transformation_, theme = Industrial Revolution:

- Hook: "What would happen if you wore [scent] in the 1800s?"

- Shots (escalating social reaction): the skeleton sprays the scent in a steaming factory (workers stare) → walks a cobblestone street as townsfolk's heads turn → a noblewoman swoons over "your scent" in an opulent bedroom → an apothecary marvels "…at a fraction of the price" → payoff: the skeleton sits crowned on a throne flanked by admirers, "…with their 30-day money-back guarantee."

- Why it works: the benefit (irresistible attraction) is made visceral by dropping an ordinary skeleton into a vivid era and escalating the reactions from _recoil_ → _worship_. Triumph payoff + guarantee CTA.

- Look: Bare-Bones Cinematic, photoreal period sets, warm muted grade, the same ivory cartoon-eyed skeleton in every shot.

---

## Swipe file (study the voice; tag = angle / spine)

Every one opens on a curiosity-gap question, runs 5–7 escalating shots of concrete physical imagery in second person, and lands a payoff.

- Transformation / Time (best for "use the product"): _30 Days of Daily Creatine_ — "Day one, chalky water, you feel scammed… Day 14 saturation hits, jet fuel… Day 30 the brain fog lifts… Day 60 a different person." · _What Braces ACTUALLY Do_ — "Day one it feels weird… Day 30 gaps closing… Day 360 Hollywood smile."

- Cost-of-inaction / Time (best for "don't fix this"): _What If You NEVER Cleaned Your Room?_ — "Day one a hoodie on the floor… one month fuzzy green pizza… 3 years a fungal infection in your bloodstream." · _Stop Wearing Caps EVERY Day_ — "Day one you look sharp… Day 365 the roots have disappeared."

- Limit / Overload / Quantity (best for "the old way breaks"): _Don't Drink This Much Milk!_ — "One glass refreshing… 15 glasses curdling… 42 glasses your stomach ruptures." · _How Long Can You Drive?_ — "1 hour fresh… 17 hours legally-drunk sluggish… 72 hours total system failure."

- Origin / Scenario (best for "what if you had this in [world]"): _Raised by Gorillas_ — "Day one you lose the soft bed… Year 20 human society is an alien world." · _3 Years in Dagestan_ — "1 month out-wrestled by a 12-year-old… 3 years you return a world-class wrestler."

Hook templates across the file: _"What would happen if you \_\_\_?"_ · _"What happens if you \_\_\_ every day?"_ · _"How long can you \_\_\_?"_ · _"How many * does it take to *?"_ · _"What if you NEVER \_\_\_?"_

---

Generate the media directly.

Don't do all four stages unprompted — wait for each hand-off unless the user asks for everything at once.

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
