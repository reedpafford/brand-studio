name: Skeleton
order: 4
on: no
own_sample: yes
image_model: auto
video_model: seedance-2.0
blurb: "What happens if you ___?": one lovable cartoon skeleton climbs Day 1, Day 30, Day 365.
card: Glass-body skeleton
broll: Inside the body

<!-- Reed's skeleton-ad skill (docs/next/skills/skeleton-ad.md, #1095; first from Starpop's skeleton-ads, docs/research/starpop-2026-10-28, rule 20): its Bare-Bones Cinematic skeleton, the default (Dressed is this look with an outfit in the description); X-Ray and Cute Mascot are their own looks (skeleton-xray, skeleton-cute). A look usable on any story script (flows Q4): "What happens if you ___?" told as an escalating ladder (Day 1, Day 30, Day 365) lived by one lovable cartoon skeleton, under one narrator. -->
<!-- Reed, 3 Nov (S1–S6, F6; from his six reference videos, examples/*/notes.md): the clear glass body shell is the default look; bare bones is the lane skeleton-bare; X-Ray folded into the glass shell (old videos on skeleton-xray read as Skeleton); Mascot in warm real homes; shots without the skeleton allowed; cool or neutral clean sets allowed, inside the body always warm; hard cuts as the base, music none or a low bed; the dive goes into the object named in a non-body script; the picture changes per sentence or phrase. -->
<!-- Moved 2 Nov from server/app/prompts/styles/skeleton.md and prompts/skills/skeleton-ad.md into one place. -->
<!-- Reed's skill file (was prompts/skills/skeleton-ad.md), its chat front matter: name: skeleton-ads; description: "Activate when the user asks for a skeleton ad or a 'What happens if you ___' / Day 1 → Day 30 progression ad: a narrated escalating journey lived by one locked 3D cartoon skeleton." -->

## sheet_look
Cinematic 3D animated render. A skeleton character (the description says so) is a full anatomical skeleton with natural adult human proportions, tall and lanky, smooth ivory-cream bones with realistic bone detail (not toy-smooth, not chibi, not scary), and large expressive cartoon eyes with white sclera and dark pupils set in the eye sockets: an emotive, lovable face. It stands inside a clear, glossy, glass-like body shell in a human silhouette (clear, never tinted), through which the bones show; organs inside are soft natural pinks and browns, shown only when the description asks. When the description gives it one identity accessory or outfit, it wears that, the same in every view, with the skull and hands still showing. Anyone else is a stylised 3D cartoon human whose body and face follow their age: an adult has an adult's height, build and face, never a child's. One fixed look, identical in every view.

## place_look
Cinematic 3D animated render of a photoreal, richly dressed environment, warm colour grade, soft volumetric light with drifting atmosphere (steam, dust, haze), shallow depth of field; or a clean set (a white room, a flat blue gradient, a bright medical lab) in cool or neutral light, soft and even with a gentle rim. Inside the body is always warm: glossy reds, golds and ambers.

## still_look
The Skeleton look, unless the brand block says otherwise: "Cinematic 3D animated render: a photoreal environment for the story's world with a warm colour grade, soft volumetric light with drifting atmosphere and shallow depth of field, or a clean set (a white room, a flat blue gradient, a bright medical lab) in soft, even cool or neutral light. The skeleton and everyone else come from the character sheets: the same ivory, cartoon-eyed skeleton in its clear glass body shell in every shot of its world. Its eyes and posture carry the feeling, big and readable with the sound off. The skeleton is the only cartoon element: the place is photoreal, never a cartoon set or a toy. A shot inside its body is a glossy macro 3D render of the part the line names, in warm reds, golds and ambers with wet highlights and a soft glow, never gory."

## clip_style
Cinematic 3D animation, the same ivory cartoon-eyed skeleton in its clear glass body shell in every shot of its world, its bones moving with natural weight, a photoreal room or a clean set, soft light, inside the body always warm

## fit_look
a cinematic 3D cartoon look (a skeleton character is an ivory cartoon skeleton with big expressive eyes inside a clear glass body shell)

## Stills
- The skeleton is in every shot of its world and is always the same character, from its sheet: never change its eyes, bones or proportions. A shot inside its body (a macro of the part the line names) or of the product needs no skeleton.
- Each shot shows one rung of the ladder, literally (Day 1: the first try, in an ordinary place; later rungs: bigger reactions, a grander place), so the climb reads with the sound off: the picture is the proof of the line. Vary the framing: a wide of the world, a medium on the skeleton, a two-shot with someone reacting, a close-up of the product in its bony hands, a hero shot for the payoff. People who react (townsfolk, coworkers, a crowd) make the climb bigger, from a stare to awe.
- Describe the body gently and dry: bones and glow, never wounds or anything gory.

## Clips
- Each shot shows what the line says at that moment. When the video is narrated, the narrator's voiceover carries it and no one on screen speaks.
- One move and one camera move per shot. Hard cuts are the base; for the big moments a dive (a push through) goes into what the line names.

## Breakdown
- One shot per sentence, or per phrase when a sentence runs over about 2.5 s, so a rung of the ladder can take several shots; never two ideas in a shot. The skeleton is in every shot's `character_ids`, except a shot inside its body or of the product alone.

## Script
- Open on a curiosity-gap question: "What would happen if you ___?", "What happens if you ___ every day?", "How long can you ___ before ___?", "How many ___ does it take to ___?", "What if you NEVER ___?". Then 5 to 7 escalating rungs, each one line: by time (Day 1, Day 30, Day 365; or hour, week, year), by amount (1, 5, 25, 42) or by stage (Stage 1 to Stage 5). Then the payoff, a triumph (transformed, unstoppable, crowned) or a catastrophe (a system failure, ruin), with the end line. About 110–160 words.
- Think about the product before the arc; transformation is one option, not the default. A product that compounds with daily use suits "use it for 30 days" (time, triumph); one that replaces a painful, worsening status quo suits "what if you never fix this" (time, catastrophe); one that fixes an overdone old way suits "how far the old way goes before it breaks" (amount, catastrophe); one that is vivid dropped into another world or era suits "what if you had this in ___" (time or stage, triumph). Two can fuse. Pick the one that makes the product's benefit most vivid, open the question in the first line, bring the product in on one clean turn, and answer the question at the payoff.
- Second person, present tense, short punchy sentences, one concrete physical picture per line, each rung more intense than the last. Say what physically happens; never corporate words ("revolutionary", "seamless").
- In a Narrated script the narrator is the only voice; in a Dialogue one, the skeleton speaks its own rungs.
- This shapes a new draft or a variation. A script that already exists keeps every line word for word, dialogue included: Enhance adds pictures, never lines, and a narrator speaks only lines the script gives a narrator (to have one voice read it all, the editor makes the script Narrated).

## lanes
This look has lanes, ways of making it; choose one for this video in `lane`:
- "" (the default, Glass shell): one lovable cartoon skeleton in a clear glass body shell; for most stories, and for anything about what happens inside the body (health, food, sleep).
- "skeleton-bare": Skeleton Bare-Bones: the bare skeleton, no shell; for origin, scenario and transformation stories that never go inside the body.
- "skeleton-cute": Skeleton Mascot: a cute chibi skeleton mascot; for a playful brand or a younger audience.

## banned
gory →
gore → glow
blood → glow
bloody → glowing
wound → crack
wounds → cracks
corpse → skeleton
rotting → dusty

## fixes
refused: Soften it: bones and glow, never wounds, blood or anything gory. Then Make another.
face: Change this… "the skeleton exactly as its sheet: same eyes, bones and proportions".
outfit: Change this… naming what the skeleton wears, this video's outfit when it gives one, else its sheet's.
product: Change this… "the real product from its image in the skeleton's hand, the label facing the camera".

## sample
One friendly anatomical skeleton, tall and lanky, ivory-cream bones inside a clear glass body shell, large expressive cartoon eyes in its sockets, smiling in a warm, softly hazy real kitchen.

## The videos
The videos are animated with AI video models: stylized 3D characters.

## pacing
Measured on Reed's six skeleton references (narrated, 99–161 s each; studies in examples/*/notes.md):
- Shot length: median 1.8–2.45 s (6 of 6); shortest real shot 0.4–0.9 s; longest hold 4.3–6 s (5 of 6).
- Cuts per 10 s: 3.8–5.2 (5 of 6 measured; the sixth about 3.8–4 once its hidden jump cuts and dissolves are counted). In a dive run (see camera), 7–10 cuts per 10 s for 5–15 s (3 of 6).
- Hook: the first shot holds 0.9–4.0 s (6 of 6); the second picture arrives by 1–4 s.
- The picture changes on the phrase: a median of 5–8 spoken words per shot (6 of 6).
- Timing: cuts are hard cuts on the voice's phrases, not on the music's beat (5 of 6 at or below chance on the beat). Cuts land on a word's start more often than chance in 3 of 6 and at chance in the rest.

## camera
Measured on the six references; this is the "visuals zooming in and showing whatever is being said" (Reed).
- The creep-in (must keep): a slow, steady push-in through most shots: 51–64% of shots, 54–66% of the runtime, a new push every 2.4–3.8 s (4 of 6; the other two hold more and keep the eye busy with acting and glows). Speed 2–7 %/s (median per video; full range 1.6–15 %/s), the same from the shot's first frame to its last, no ease, ending about 5–35% tighter.
- The dive (must keep): when the line names a body part, the camera dives into it, through the ribs or the skin, and lands on a glossy macro of the inside (5 of 6). It runs 20–67 %/s for 0.4–2.5 s, ends 1.5–2.5x tighter and often speeds up. It starts on the word and lands by the next word. Used 1–3 times a video, or once as a chain of 5–9 shots, each one level deeper. In a script that isn't about the body, the dive goes into the object the line names (Reed, 3 Nov).
- What the camera goes to: the named body part, organ, object or product, not the face for emphasis (5 of 6; one video has a single crash push onto the face). Showing what is said is mostly done by cutting to it: the next shot is already framed on the named thing (6 of 6).
- The moves are made in the clip (parallax shows), not added as a zoom in the edit (6 of 6). Edit-made zooms are rare extras: a quick zoom-blur into the next shot (2 of 6).
- Rare: the reverse pull back out of the body, about 27–56 %/s (2 of 6); an orbit of 160–180° for a "spreading" beat (1 of 6); a short tilt-drop from the whole body to the legs or feet (2 of 6).
- Shot sizes: medium and medium close-up on the skeleton; close-ups on the named body part from the top, low or front; macros inside. Full-body wides are rare and short. No handheld feel.

## must keep
- The creep-in and the dive (see camera), and cutting to what the line names.
- The hook shows the problem in the body (a glowing belly, swollen feet, red ribs); the face can come later (6 of 6 show the problem first; 4 of 6 hold the face back).
- Everything inside the body is glossy, tactile and friendly: beads, syrup, sludge, crystals, glow (6 of 6).
- Inside the body is warm and saturated: reds, golds and ambers, warmth +20 to +45, saturation 49–72 (6 of 6). Contrast stays low and soft, 17–22 (6 of 6).
- When narrated, the voice runs wall to wall: 3.2–3.7 words a second, pitch variability 4.2–5.8 semitones (animated, never flat), pauses no longer than about 0.5–0.65 s, voice mixed at about −14 LUFS (6 of 6).

## safe to vary
- How much the camera pushes: from most shots (66% of the runtime) down to a few dives in a mostly held video (16%).
- How many dives: none to a 9-shot chain.
- How the inside shows on the body: a glow or coloured fluid that marks the problem, organs always visible, or organs that glow when the line names them.
- The skeleton's identity accessory or outfit (a cap, headphones, a headband, a beanie, hair): one, never changing (4 of 6).
- The place: a warm, lived-in real room (2 of 6: brightness about 47, warmth +12 to +21) or a clean cool or neutral set (4 of 6: a white room, a flat blue gradient about #4A657E, a lab; warmth −3 to +9).
- Light on the body as meaning: red for pain, orange for bloat, gold for healing or the product working.
- Music: none (2 of 6) or a low bed 11–33 dB under the voice (4 of 6), a soft pulse in the middle third, rising or dropping out for the close. Music is added in post: the site makes the video's own sound, the voices, the room and the effects, never a music bed, and a cut with none is right. Sound effects are nearly absent: no whoosh on the dives (6 of 6); one whoosh and one riser in all 12 minutes.

## combines with
- Narrated scripts: all six are one narrator over the pictures.
- Ladder scripts: 3 of 6 count days; a 0.7–1.1 s locked-off desk-calendar page or big day number marks each rung (2 of 6).
- Problem-to-fix explainers: 3 of 6 aren't ladders at all; the look carries any script about the body or how something works inside.
- Real product footage: 4 of 6 close on product shots or real phone footage (allowed, Reed 3 Nov: shots without the skeleton).

## How to make skeleton ads
A skeleton ad is a narrated, escalating-progression video: a recurring literal cartoon skeleton lives out a second-person journey — _"What happens if you \_\_\_?

Day 1… Day 30… Day 365"_ — carried by a single voiceover, with generated animated visuals and one consistent skeleton in every shot of its world.

Borrowed from viral "What happens if you \_\_\_?" Shorts.

It wins on two things: an escalating spine that makes one benefit impossible to look away from, and a skeleton that stays the _exact same character_ across every shot.

Mechanically: the whole voiceover generated first as one continuous take, setting the clock for every visual, with a fixed spine and a fixed recurring character.

It adds only what is specific to the skeleton format: the escalating spine, the skeleton style library, and the swipe-file voice.

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

One VO sentence → one shot (or one per phrase when it runs over about 2.5 s) → one rung of the ladder.

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
The same skeleton appears in every shot of its world (a shot inside its body or of the product needs none) — protecting its visual consistency is the single most important production rule.

It is a recurring character; this skill supplies a _pre-made_ skeleton design (the Style Library below) instead of designing from scratch.

Lock one canonical character reference, then re-attach it and re-state its description in every still it is in — never chain off a previous shot's output.

Fill each style's `[THEME]`, palette, and (for Dressed) wardrobe to the ad's world; never change the character-defining wording between shots.

### Style Library — pick one; the chosen block becomes the skeleton's character reference sheet

Recommend the best style for the product with a one-line reason.

Default to the Glass Shell unless the product points elsewhere (an origin/scenario story that never goes inside the body → Bare-Bones Cinematic; wearable/identity/lifestyle → Dressed Skeleton; a brand that is intentionally playful → Cute Mascot). Health/body/supplement → the Glass Shell, which also carries what X-Ray did.

Never silently default to the cute look.

1. Glass Shell — _default (Reed, 3 Nov: five of his six reference videos); X-Ray folded into it._ Best for health, body, supplement and "what happens inside you" angles, and most others.

> CHARACTER: A full anatomical skeleton with natural adult human proportions, tall and lanky, smooth ivory-cream bones with realistic bone detail (NOT toy-smooth, NOT chibi, NOT scary), and large expressive cartoon eyes with white sclera and dark pupils set in the eye sockets, inside a clear, glossy, glass-like body shell in a human silhouette (never tinted); organs show inside only when the story needs them, glowing on the line that names them.

Same character in every shot of its world.

STYLE: cinematic 3D animated render, photoreal [THEME] environment with a warm [palette] grade and soft haze, OR a clean set (white room, flat blue gradient, medical lab) in soft cool or neutral light; inside the body always warm.

2. Bare-Bones Cinematic — _the lane skeleton-bare (the default until 3 Nov)._ Best for origin/scenario and transformation ads.

> CHARACTER: A full anatomical skeleton with natural adult human proportions, tall and lanky, smooth ivory-cream bones with realistic bone detail (NOT toy-smooth, NOT chibi, NOT scary), and large expressive cartoon eyes with white sclera and dark pupils set in the eye sockets, giving an emotive, lovable face.

No clothing.

Same character in every shot.

STYLE: cinematic 3D animated render, photoreal [THEME] environment, warm [palette] color grade, soft volumetric light with drifting steam/atmosphere, shallow depth of field.

3. Dressed Skeleton — the same skeleton (Glass Shell or Bare-Bones) wearing a full themed outfit. Best for wearable, fashion, lifestyle, or identity products.

> CHARACTER: The same friendly skeleton (ivory bones, large expressive cartoon eyes with white sclera and dark pupils) wearing a complete [THEME-appropriate wardrobe, e.g. tailored suit / cowboy attire / varsity jacket and cap]; skull, hands and any exposed bones still visible.

Same character in every shot.

STYLE: cinematic 3D animated render, photoreal [THEME] environment, warm [palette] color grade, soft volumetric light, shallow depth of field.

4. Cute Mascot — chibi, toy-like, friendly. Best for playful, fun, or lighthearted brands only.

> CHARACTER: A cute chibi cartoon skeleton with an oversized round skull, big adorable eyes, a small rounded body, and smooth toy-like bones; bright, friendly, non-scary.

Same character in every shot.

STYLE: playful 3D animated render, a warm, lived-in real home in the [theme], lamp or window light, soft depth of field, glossy finish.

(Aspect ratio and resolution are generation settings — never write them into the prompt.)

---

## The pipeline — four stages, native generation
The whole voiceover is generated first and becomes the factual pacing source; the shots are generated as silent animated B-roll and laid over the VO in the editor.

### Stage 1 — Write the script

1. Ground in the exact product using verified facts. Reuse sufficient context already available. Establish what it is, who it's for, the core transformation, the painful status quo, proof, the offer.

2. Pick the angle + spine with the strategy above. State the chosen angle + spine in one line with a one-line rationale.

3. Write the script in the swipe-file voice: a curiosity-gap question, then 5–7 escalating shots, then the payoff + a soft CTA tied to the offer. ~110–160 words (≈30–60s of VO), one shot per sentence, or per phrase when a sentence runs over about 2.5 s. Open the question in the first line, land the product on one clean turn, and answer the question at the payoff.

4. The full script and the same script as a numbered VO line list (one line = one sentence, one clip's worth of narration each; a long sentence takes a shot per phrase).

```
Angle: [angle + spine] — [one-line rationale]
Loop → turn: [the question the hook opens] → [the shot where the product enters]

## Script — "[Hook title]"
[Full script: hook question + 5–7 escalating shots + payoff/CTA, swipe-file voice.]

## Voiceover line list (one line = one sentence)
1. [hook question]
2. [shot 1] …
N. [payoff + CTA]
```

### Stage 2 — Visual concept board

First, generate the voiceover (one calm, dramatic narrator): the whole final script in one take.

The board needs only the lines; the take's word timings, analyzed in Stage 4, set every shot's duration and the batching.

1. Pick the skeleton style from the Style Library with a one-line reason.

2. Lock the world — recommend the recurring theme/setting that dramatizes the angle, plus 1–2 alternative theme directions (modern office, 1940s, the product's literal industry, post-apocalyptic…).

3. Map every VO line to a shot in a grid — one row per line. The skeleton is in every row of its world; what changes is its situation, the setting rung, and the props. Vary the framing across shots (wide establishing → medium → two-shot with a reacting human → close product handling → hero/triumph), and use reaction characters (period townsfolk, coworkers) to amplify the arc.

```
## Visual concept board — "[Hook title]"
Style: [one of the library] — [why it fits]   Theme: [world] — [why]   Alternatives: [B] · [C]

| # | VO line | Skeleton's situation & emotion | Setting (the spine rung) | Props / product | Join (editor only) |
|---|---|---|---|---|---|
| 1 | [line] | [pose, expression, action] | [where] | [props] | [cut or dive into the shot] |

The last column is a note for the editor — it never goes into a prompt (generated footage stays clean of text).
```

### Stage 3 — Lock the skeleton reference + per-shot start frames

1. Establish the canonical skeleton reference FIRST as the character reference sheet, opened with the chosen style block. This is the source of truth every shot points back to.

2. One start frame per shot — re-attach the canonical character reference and identify it. Attach the product reference in any shot the product appears.

3. No text in any still.

### Stage 4 — Video generations, synced to the voiceover

1. Time the shots from the voiceover generated in Stage 2: analyze its word timings; they are the pacing source, so each batch's duration follows the lines it carries.

2. Batch the shots into multi-shot video generations (start frames per shot) — group consecutive shots up to the 15s cap, role-label each shot's start frame ("image N is shot N's start frame"), describe each shot's motion + one camera move + the transition to the next, and keep the clips silent (no dialogue — the VO is overlaid in the editor). Tell the model the pacing so the visuals land with their lines.

3. Assemble the clips over the voiceover in the editor with the board's joins — hard cuts as the base, a dive into what the line names for the big moments — and no music or a low bed well under the voice; nothing is burned into the footage.

---

## Locked rules
- R1 — The skeleton is the constant. One canonical character reference; re-attach it and identify it in every still it is in; never chain off a previous shot's output. The Style Library block is locked once chosen — don't drift the eyes, bones, or proportions mid-ad.

- R2 — One VO sentence = one shot (one per phrase when it runs over about 2.5 s) = one rung of the spine. Cramming two ideas into a shot kills the rhythm and the loop.

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
