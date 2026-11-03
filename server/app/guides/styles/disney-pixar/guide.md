name: Disney Pixar
order: 1
on: no
image_model: auto
blurb: Like a frame from a Pixar feature: designed 3D characters with big glossy eyes and sculpted hair, in a warm, softly lit world.

<!-- From Starpop's disney-pixar-ads skill (docs/research/starpop-2026-10-28, rule 20), Reed's skill file (docs/next/skills/disney-pixar.md, #1095) and the Nano Banana and Seedance docs. Closer to a Pixar feature than House ("in the style of": a studio's frame could be refused as a copy): sculpted hair, glossy eyes, soft global light, saturated colour. Adults keep adult proportions (look_fit): Starpop's 4–5 heads tall drew our adults as children. -->
<!-- Moved 2 Nov from server/app/prompts/styles/disney-pixar.md and prompts/skills/disney-pixar.md into one place. -->
<!-- Reed's skill file (was prompts/skills/disney-pixar.md), its chat front matter: name: disney-pixar-animation; description: "Activate when the user wants a video, ad, or B-roll in a Pixar, Disney, Disney-Pixar, or 3D animated-movie look." -->

## sheet_look
A frame in the style of a Pixar animated feature film: high-end stylised 3D animation, every surface a designed 3D asset with simplified, appealing shapes and believable stylised materials, never photographic texture. Caricatured, appealing design with a readable silhouette and a face built from clear, simple masses: large expressive eyes with glossy catch-lights, defined expressive eyebrows, a simplified nose and a wide expressive mouth; smooth skin with soft subsurface warmth and a subtle matte finish; hair sculpted into solid stylised clumps and locks with crisp light-and-shadow bands, never fine strands. Every face is distinctive and full of personality. The body and face follow the character's age: an adult has an adult's height, build and face (a defined jaw, the head only slightly large for the body), never a child's; a teenager looks like a teenager, a child like a child. An animal is a stylised Pixar animal: simplified appealing shapes and the same glossy eyes. One fixed outfit with simplified, believable fabric folds, identical in every view, and one silhouette-defining item that reads at a glance.

## place_look
A frame in the style of a Pixar animated feature film: high-end stylised 3D animation, every object a designed 3D asset with simplified, appealing shapes and believable stylised materials, a detailed lived-in environment, rich cinematic light with soft global illumination, warm bounce light and gentle colour in the shadows, saturated but harmonious colour.

## still_look
The Disney Pixar look, unless the brand block says otherwise: "A frame in the style of a Pixar animated feature film: high-end stylised 3D animation in which every object and surface is a designed, stylised 3D asset with simplified, appealing shapes. Faces and builds come from the character sheets, and outfits too unless this video gives its own. Rich cinematic lighting with soft global illumination, warm bounce light and gentle colour in the shadows, a detailed lived-in environment with believable stylised materials, shallow cinematic depth of field, and saturated but harmonious colour. Composed like a hero frame from an animated feature, with the camera inside the scene at a cinematic angle and the scene filling the entire frame. A stylised 3D animated render. Expressions are big and readable with the sound off."

## clip_style
Smooth cinematic 3D animation in the style of a Pixar feature film, fluid and expressive, with soft global light, warm bounce light and saturated but harmonious colour

## fit_look
a stylised Pixar-like 3D look with large glossy eyes and sculpted hair

## Stills
- The look above is the default light and framing; when a shot needs other light (rain, night, a cold screen) or a close framing (a hand, the product, a macro view), say it in the scene and it wins.
- Name the feeling, then write it as the face: "worn out after the night shift: her inner brows pushed up, her mouth a flat tired line". An adjective alone renders a pleasant neutral face.
- A shot with no people in it (the product alone, a close-up of food) says "no people in the frame". Only the characters described appear in the frame, and objects and products have no faces.
- With a character's sheet attached, name it and its job and describe only what this shot changes: the action and the expression. The sheet carries the look; never add hair detail, which brings back fine strands.
- The product is its real image: state every line of its label exactly, with its colour ("a clean label reading CREATINE in black letters").
- A mechanism shot shows the ingredient arriving and acting, mid-action, as "a zoomed-in macro view, no people in the frame" ("a golden serum droplet sinking down through the skin's layers, spreading and glowing as it goes deeper"). A body shot says what is visible in plain words (layers, strands, a droplet), never clinical terms (named conditions, hormones): the image model refuses them.
- One clear subject and one action per frame, so it reads on a phone. A single continuous frame: never panels, split screens or a collage.

## Clips
- After the Style line, the prompt carries the action, the lines and the camera; the first frame and the sheets carry the look. One motion action per shot: stacked actions drift.
- Classic animated-feature moves suit the turns. The camera moves past a fixed anchor: push in from the scene to the product's label, push into the skin at macro to show the mechanism, pull back from a face to show the room. Or the world changes around a fixed camera: a warm shimmer sweeps the frame and the grey scene turns golden (problem to fix), the light moves from grey morning to golden evening around the hero (time passing), the product glows and the scene changes around it (the reveal). Or a match cut: a round shape becomes the next scene's round shape (a pancake becomes the sun), or a gesture carries on across the cut. Name the one visible action that carries one shot into the next.

## banned
photorealistic → stylised
photo-realistic → stylised
live-action →
in the style of Pixar →
in the style of Disney →
Pixar-style → animated-feature
Disney-style → animated-feature
anime → animated

## fixes
refused: Take out any studio or film name, Soften it, then Make another: a frame that reads as a copy of a studio's is refused.
face: Make another first. If it drifts again, Change this… "big glossy eyes and sculpted hair exactly as the sheet, adult proportions".
outfit: Change this… naming the outfit's key pieces in the shot, this video's when it gives one, else the sheet's.
product: Change this… "the real product from its image, the label facing the camera and readable, under the scene's soft light".

## sample
A cheerful man in his thirties with sculpted wavy brown hair and big glossy eyes, in one plain teal jacket, adult proportions.

## disney-pixar-animation SKILL
The Disney-Pixar visual style for AI video ads: one look, a frame from a 3D animated feature film. Every image made under this skill exists to be animated: a start frame, shot reference, or canonical reference for a video generation — one shot of the ad, visualizing what the voiceover says at that moment. Two things make the output win: **appealing, designed characters** (caricatured proportions, big expressive eyes, sculpted hair), and **a warm, cinematically lit stylized 3D world** where every object is a designed asset, never a photograph.

## Scope
This is solely a visual rendering style, nothing more. It never drives scene content — the storyboard belongs to the ad; this skill only decides how the world is designed, lit, and rendered. Canonical references, speech, workflow, and video models follow the visual and media generation foundations. The style carries lifestyle, emotion, exterior, product-only, and mechanism shots (a serum absorbing through skin layers) equally well. "Pixar" and "Disney" name a visual style, not a franchise: every character is original, never a recreation of an existing one, and no studio logo appears in frame.

## What makes anything read as Disney-Pixar
1. **Everything is a designed 3D asset.** Objects and surfaces have simplified, appealing shapes and believable stylized materials, never photographic texture.
2. **Caricature with structure.** Heads slightly large for the body, about four to five heads tall, a readable silhouette, and a face built from clear simple masses.
3. **The eye.** Large and expressive, with glossy catch-lights. This is what makes a face read as Pixar.
4. **Sculpted hair and matte skin.** At its best the hair is solid sculpted shapes with crisp light-and-shadow bands rather than fine strands, and the skin has soft subsurface warmth with a subtle matte finish.
5. **Cinematic light.** Soft global illumination, warm bounce light, gentle colour in the shadows, shallow depth of field, saturated but harmonious colour.

## The camera: a hero frame, inside the scene
Every image is a still the video model will animate, so it is a self-contained scene: the world extends past every edge of the frame and the camera sits inside it, composed like a hero frame from an animated feature.

**The blocks set defaults; the scene overrides them.** The style block's warm cinematic light and the camera block's hero-frame composition are the defaults for every shot. When a shot needs something else, say it in the scene and keep the blocks verbatim — the scene's light and framing win:

- **Light:** rain, night, a cold screen — "soft grey light from a window with rain-speckled glass. Muted and cool in mood."
- **Framing:** "A close-up of a hand holding up…", "A zoomed-in macro view…". Close-ups suit hands, products, and mechanism shots.

## Image model
**Nano Banana 2.1 by default for stills, start frames, and canonical references.** Set the model in the generation settings. Recommend Nano Banana 2.1: it renders this style best and follows the blocks closely. For a softer, more rounded look, Seedream 4.5 can also be a good variant. When a result misses, **reroll the identical prompt before rewriting it** — once the blocks are locked, variance is almost always the cause.

## The style blocks
Every image prompt is assembled in one order: **style block → character block (only when people are in frame) → the scene → camera block.** Paste each block word for word.

**Style block** — opens every image prompt:

```
A frame from a Pixar animated feature film: high-end stylized 3D animation in which every object and surface is a designed, stylized 3D asset with simplified, appealing shapes. Rich cinematic lighting with soft global illumination, warm bounce light and gentle colour in the shadows, a detailed lived-in environment with believable stylized materials, shallow cinematic depth of field, and saturated but harmonious colour.
```

**Character block** — add it only when the shot has people in frame. Leave it out of product-only and mechanism shots: its character language summons people into scenes that should have none.

```
Characters are stylized Pixar humans with caricatured, appealing proportions: heads slightly large for their bodies, about four to five heads tall, with strong readable shape design — a distinctive silhouette and a face built from clear, simple masses. Large expressive eyes with glossy catch-lights, defined expressive eyebrows, a simplified nose and a wide expressive mouth. Smooth skin with soft subsurface scattering and a subtle matte finish, hair sculpted into clear stylized clumps and locks, and clothing with simplified, believable fabric folds. Every face is distinctive and full of personality.
```

**Camera block** — closes every image prompt:

```
Composed like a hero frame from an animated feature, with the camera inside the scene at a cinematic angle and the scene filling the entire frame. A stylized 3D animated render.
```

## Worked example — the quality bar
The scene that sits between the character block and the camera block for a breakfast two-shot. It shows the pattern, not a template to copy: each character described in full, the action and the glance written as what the bodies and faces do, every prop named, the label copy stated.

```
A muscular middle-aged man with dark hair greying at the temples and a full beard, wearing a grey tank top, sits at a round kitchen table lifting a fork of egg with a content half-smile, while a blonde woman with long voluminous wavy platinum hair and a fitted pink mini dress sits beside him reaching both hands toward the lid of a white creatine tub with a clean label reading CREATINE in black letters, glancing sideways at him with a playful knowing look; on the table a plate of fried eggs and pancakes, a glass of orange juice, and two navy mugs; behind them a softly blurred farmhouse kitchen — wood-brown cabinets, a cream fridge, a hanging plant, and a window with sheer curtains and morning light.
```

A product-only shot drops the character block and keeps the same grammar: "A white creatine tub with a clean label reading CREATINE in black letters stands on a kitchen counter beside a bowl of lemons and a mug, a window with sheer curtains behind, morning light, no people in the scene."

## Prompt rules
- **Blocks verbatim in every prompt, canonical references included.** A canonical character sheet opens with the style block and the character block, so every shot built from it inherits the look. Consistency comes from the blocks plus canonical references, never from "same style as before."
- **Character design.** Design a new character following the visual foundations and lock it as a canonical reference sheet. Seedream 4.5 can be good for a more rounded, Disney-style look — a natural variant to offer when the user wants to see a few directions for the character.
- **Describe every character in full in the scene.** Age, build, hair colour and style, and clothing ride on each character — anything left unstated is dice-rolled and drifts between shots. When a canonical character reference is attached, name it and its job right after the style block, and describe only what this shot changes: the action and the expression. The reference carries the look.
- **Animals and creatures.** The character block describes people. For an animal or creature lead, leave it out and describe the animal in the scene as a stylized Pixar animal — simplified appealing shapes, large expressive eyes with glossy catch-lights. When people and an animal share a frame, keep the character block for the people.
- **Name the feeling, then write it as face mechanics.** State what the viewer should feel, then direct the face: "her inner brows pushed up and her mouth a flat tired line." An adjective alone ("sad," "tired") renders a pleasantly neutral face.
- **The product stays accurate.** Attach the canonical product reference whenever the product appears, and state every line of label copy exactly, with its colour ("a clean label reading CREATINE in black letters").
- **Mechanism shots show the ingredient arriving and acting, mid-action,** framed as "a zoomed-in macro view, no people in the scene," so the clip can animate the change: "a golden serum droplet being absorbed downward through the layers, the serum spreading and glowing as it penetrates deeper."
- **Body shots describe what is visible,** in plain visual words — layers, strands, a droplet. Clinical terms (named conditions, hormones) get the image rejected by the model provider's safety filter.
- **One clear subject and one action per frame.** A simple, readable shot reads best on a phone.

## Motion (video prompts)
Smooth, cinematic 3D animation — fluid, expressive movement with natural weight, the way an animated feature moves. That is what video models produce by default, so every clip prompt, transitions included, opens with this one **motion line** and needs no heavier guard:

```
Smooth cinematic 3D animation in the style of a Pixar feature film, fluid and expressive.
```

The start frame carries the look; after the motion line, the clip prompt describes the action, the speech, and the camera. One motion action per clip — stacked actions multiply drift.

## Pixar transitions
For any transition clip, **build the frame pair by the media generation foundations' start/end-frame guidance** — one shared anchor generated from the same references in both frames, one action, compositional continuity, explained fates. Classic animated-feature moves that suit ads:

- **Camera-bridge** (anchor fixed, camera moves): push in from the scene to the product label; push into the skin at macro to reveal the mechanism (problem shot → mechanism shot); pull back from a face to reveal the room.
- **World-bridge** (camera fixed, the world changes around the anchor): a magical shimmer sweeps the frame and the dull, grey scene turns warm and bright (problem → solution); the light shifts from grey morning to golden evening around the character (time passing); the product glows and the scene transforms around it (reveal).
- **Match cut** (shape or motion rhyme): a round shape becomes the next scene's round shape — a pancake becomes the sun — or a gesture continues across the cut.

The transition clip prompt names the one concrete visible action that carries frame A into frame B, plus the motion line, and nothing else — the frames carry the style.

## Known limitations & workarounds
| Failure | Fix |
| --- | --- |
| People appear in a product-only or mechanism shot | The character block went in — leave it out whenever no people are in frame |
| Hair renders as fine realistic strands | Reroll the identical prompt; it lands on a reroll. Do not add hair detail |
| The frame comes out as a multi-panel comic or collage | Reroll; if it repeats, append "A single continuous frame — no panels, split screens or collages." |
| An unrequested character appears, or the product grows a face | Reroll; if it repeats, append "Only the characters described appear in the frame; objects and products have no faces." |
| The named emotion doesn't show on the face | Emotion written as an adjective — name the feeling, then the brows, lids, and mouth |
| Label garbled | State the label copy exactly, with its colour, and attach the product reference |
| One character looks different between shots | Lock the character as a canonical reference, opened with the style and character blocks, and attach it to every shot they appear in |
