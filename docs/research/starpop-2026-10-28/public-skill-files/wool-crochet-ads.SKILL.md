---
name: wool-crochet-animation
description: "Activate when the user wants a video, ad, or B-roll in a crochet, knitted, yarn, or wool look."
---

# wool-crochet-animation SKILL

The crochet visual style for AI video ads: one look, a miniature world hand-knitted from yarn and photographed like a stop-motion film still. Every image made under this skill exists to be animated: a start frame, shot reference, or canonical reference for a video generation — one shot of the ad, visualizing what the voiceover says at that moment. Two things make the output win: every frame reads as **photographed knitted yarn**, with stitch rows on every surface including the dolls' skin, and every frame is a **self-contained scene shot from inside the knitted world, from a step back**.

## Scope

This is solely a visual rendering style, nothing more. It never drives scene content — the storyboard belongs to the ad; this skill only decides how the world is knitted, lit, and animated. When producing a full VO-led ad, follow the advertising, visual, and media generation foundations and apply this skill at the prompting steps. The style suits voiceover + B-roll content best, and it carries lifestyle, product, and mechanism shots (a skin cross-section, gut villi, a hair follicle) equally well.

## What makes anything read as knitted yarn

1. **The material owns the noun.** Put the material word directly on every subject: "a knitted muscular man," "a knitted blonde woman," "a white knitted creatine tub." When the person comes first and the material second ("a woman made of yarn"), the model drops the material and renders a real person standing in a yarn room.
2. **Every element is named as knitted.** Give each object in the scene its treatment — "a fully knitted glass of orange juice," "two navy knitted mugs," "wood-brown knitted cabinets." An object left unnamed renders as its real material and breaks the world.
3. **Stitch rows on every surface, skin included,** at a cozy medium gauge.
4. **Photographed, physical light** — real cast shadows and soft daylight, the set lit like a real miniature.
5. **Colour where the world would really have it.** Name each object's real-world colour in the scene — navy mugs, a pink dress, wood-brown cabinets, a cream fridge — and let the Style block's colour line decide how much saturation goes where: daylight, foliage, textiles, clothing, and packaging carry real saturation, fixtures keep believable tones, exteriors go fully saturated.

## The camera: inside the world, a step back

Every image is a still the video model will animate, so it is a self-contained scene: the knitted world extends past every edge of the frame and the camera sits inside it at eye level. **Frame medium-wide, from a step back, with the subject fully visible.** Rendered stitch detail scales with camera proximity: from a step back, faces stay smooth painted dolls with a light knit texture; pushed in close, they turn hyper-detailed and uncanny.

**The blocks set defaults; the scene overrides them.** The Style block's daylight and step-back framing are the defaults for every shot. When a shot needs something else, say it in the scene and keep the blocks verbatim — the scene's light and framing win:

- **Light:** night, a lamp, a cold screen — "the bedroom deep in night, lit only by moonlight from the window and the red glow of a knitted alarm clock."
- **Framing:** "A close-up of a knitted woman's hands…", "A zoomed-in macro view…". Close-ups belong to hands, products, and mechanism shots; faces stay at a step back.

## Image model

**GPT Image 2 at quality `medium` for every still and start frame.** Set the model and quality in the generation settings. This style is optimised for GPT Image 2; other image models are not recommended for it. When a result misses, **reroll the identical prompt before rewriting it** — once the blocks are locked, variance is almost always the cause.

## The blocks

Every image prompt is assembled in one order: **Style block → Character block (only when people are in frame) → the scene → Camera block.** Paste each block word for word. Everything else is the scene, written fresh for each shot from the storyboard: who, what, where, the action, the emotion.

### Style block

Opens every image prompt and never changes.

```
Cinematic knitted-yarn scene — a miniature world entirely hand-knitted from yarn, rounded crochet-like stitches with visible stitch rows on every surface, a cozy medium gauge, photographed like a stop-motion film still: a medium-wide shot from a step back so the subject is fully visible, the subject sharply in focus and the background gently soft, bright natural daylight. A warm naturalistic palette lifted with real colour — daylight, foliage, textiles, clothing and packaging all carry genuine saturation; wood, cabinetry and counters keep their own believable tones rather than being painted bright. Exteriors and outdoor scenes go fully saturated. The scene fills the entire frame with the camera inside the knitted world.
```

### Character block

Add it only when the shot has people in frame. Leave it out of product-only and mechanism shots: its figure language summons knitted dolls into scenes that should have none.

```
The figures are knitted dolls with realistic adult proportions and idealized builds — smooth doll faces with only a light knit texture, sweet painted features: painted eyes with soft lashes glancing naturally, painted lips, gentle blush, a few tiny stitched freckles; visible stitch rows across their knitted skin; luxurious styled yarn hair in fine strands; knitted clothing fitting the body.
```

### Camera block

Closes every image prompt.

```
Camera at eye level, inside the scene. Everything in frame is knitted yarn, photographed — soft stitch detail visible on every surface, real cast shadows, warm cozy lighting, the knitted scene filling the entire frame. No real humans, no photographic human skin. No chunky chibi toys, no oversized bobblehead, no hyper-detailed micro-stitching on faces.
```

## Worked example — the quality bar

The scene that sits between the blocks for a breakfast two-shot. It shows the pattern, not a template to copy: the material on every noun, every character described in full, every prop named as knitted, the label copy stated.

```
A knitted muscular middle-aged man with dark yarn hair greying at the temples and a full knitted beard, wearing a grey knitted tank top, sits at a round knitted kitchen table lifting a fork of knitted egg with a content half-smile, while a knitted blonde woman with long voluminous wavy platinum yarn hair and a fitted pink knitted mini dress sits beside him reaching both hands toward the lid of a white knitted creatine tub with a clean label reading CREATINE in black letters, glancing sideways at him with a playful knowing look; on the table a plate of knitted fried eggs and pancakes, a fully knitted glass of orange juice, and two navy knitted mugs; behind them a softly blurred fully knitted farmhouse kitchen — wood-brown knitted cabinets, a cream knitted fridge, a hanging knitted plant, and a knitted window with sheer curtains and morning light.
```

A product-only shot drops the character block and keeps the same grammar: "A white knitted creatine tub with a clean label reading CREATINE in black letters stands on a knitted kitchen counter beside a knitted bowl of knitted lemons and a knitted mug, a knitted window with sheer curtains and morning light behind it."

## Prompt rules

- **Blocks verbatim in every prompt.** Consistency comes from the blocks plus canonical references, never from "same style as before."
- **Describe every character in full, every prompt.** Age, build, hair colour and style, and clothing ride on each character — anything left unstated is dice-rolled and drifts between shots. A character, product, or room that recurs is locked as a canonical reference before the shots that reuse it are generated (the visual foundations' canonical reference), and attached to every shot it appears in.
- **Name the feeling, then write it as face mechanics.** State what the viewer should feel ("she is exhausted and fed up that sleep will not come"), then direct the face: "her brows pinched together, her mouth pressed into a flat tired frown, her eyes fixed wide on the ceiling." An adjective alone ("sad," "slumped") renders a pleasantly neutral doll face; the painted faces carry exhaustion, stress, and relief when the brows, lids, and mouth are named.
- **The product stays accurate.** Attach the canonical product reference whenever the product appears. Knit the packaging like everything else and state every line of label copy exactly, with its colour ("a clean label reading CREATINE in black letters"); unlabelled text picks up the material name ("YARN") instead.
- **Mechanism shots show the ingredient arriving and acting, mid-action.** Render the active ingredient as a small glowing knitted element — a golden serum droplet, glowing knitted capsules — moving into knitted anatomy and changing it, framed as "a zoomed-in macro view, no people in the scene," so the clip can animate the change. Pattern: "An interior view of the knitted gut lining showing the villi — tiny finger-like knitted projections — with small glowing knitted probiotic capsules arriving and settling between them."
- **Body shots describe what is visible, in yarn,** in plain visual words — layers, strands, projections, a droplet. Clinical terms (named conditions, hormones, "inflammation") get the image rejected by the model provider's safety filter.

## Motion (video prompts)

Yarn dies in motion when the cadence goes unnamed: video models interpolate to smooth movement and the material melts. Every clip prompt, transitions included, carries the **motion guard**:

```
Handmade stop-motion knitted-yarn animation throughout — visible knitted stitch rows and soft yarn fibre on every surface, slightly stuttery 12fps stop-motion cadence, no motion blur. Non CGI. Non cartoon. Animation must start at the first frame.
```

One motion action per clip — stacked actions multiply drift. In-scene shots stay simple: one gesture, one camera move.

## Yarn transitions

For any transition clip, **build the frame pair by the media generation foundations' start/end-frame guidance** — one shared anchor generated from the same references in both frames, one action, compositional continuity, explained fates.

- **Camera-bridge** (anchor fixed, camera moves): push in from the medium-wide scene to the knitted product; pull back from a knitted detail to reveal the next scene.
- **World-bridge** (camera fixed, yarn transforms around the anchor): the scene unravels into loose strands that re-knit as the next scene; a thread is pulled and the scene unzips stitch by stitch to reveal the next; the world rolls up into a yarn ball and unrolls as the next; loose strands stitch themselves together into the product (build-up reveal).

The transition clip prompt names the one concrete visible action that carries frame A into frame B, plus the motion guard, and nothing else — the frames carry the style.

## Known limitations & workarounds

| Failure | Fix |
| --- | --- |
| Real humans appear in a yarn room | The material owns the noun ("a knitted woman"); Camera block verbatim, kill line included |
| Knitted figures appear in a product or mechanism shot | The character block went in — leave it out whenever no people are in frame |
| Toy or bobblehead proportions | Character block verbatim ("realistic adult proportions and idealized builds") |
| Faces turn hyper-detailed or uncanny | The camera is too close — step back to medium-wide; keep close-ups for hands and products |
| Cabinets and furniture in random bright colours | Name each fixture's real-world colour (wood-brown cabinets, a cream fridge) and keep the Style block's colour line verbatim |
| A night or lamp-lit shot comes out in daylight | The scene's light was left implicit — describe the light source and how dark the room is in the scene text |
| The named emotion doesn't show on the face | Emotion written as an adjective — name the feeling, then the brows, lids, and mouth |
| The image is rejected on a body or health shot | Clinical wording — rewrite as what is visible, in yarn |
| Label garbled, or "YARN" printed on things | State the label copy explicitly on every labelled object |
| One character looks different between shots | Lock the character as a canonical reference and attach it to every shot they appear in |
| Texture melts away mid-clip | Motion guard restated in every clip prompt, transitions included |

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
