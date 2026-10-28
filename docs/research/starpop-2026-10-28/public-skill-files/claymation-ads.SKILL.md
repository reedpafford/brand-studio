---
name: claymation-animation
description: "Activate when the user wants a video, ad, or B-roll in a claymation, clay, plasticine, or clay stop-motion look."
---

# How to make claymation videos

The claymation visual style for AI video ads.

Every image made under this skill exists to be animated: a start frame, shot reference, or canonical reference for a video generation — one shot of the ad, visualizing what the voiceover says at that moment.

Two things make the output win: every frame must read as photographed physical clay (fingerprints or tool marks, soft clay sheen, real cast shadows — or the model drifts into a smooth CGI render), and every frame must be a self-contained scene shot from inside the miniature clay world.

## Scope

This is solely a visual rendering style, nothing more.

It never drives scene content — the storyboard belongs to the ad; this skill only decides how the world is sculpted, lit, and animated.

When producing a full VO-led ad, run the parent's flow (the gate, the voiceover doctrine, the storyboard) and apply this skill at the prompting steps.

The style suits voiceover + B-roll content best.

## What makes anything read as clay (apply to every sub-style)

1. Visible making-marks on every surface — fingerprints and thumb smudges (goofy, puppet) or fine tool striations (cinematic, clean). A clay world with no trace of hands reads as CGI.

2. Soft clay materiality — matte-to-satin plasticine sheen, slight subsurface warmth; never write "smooth," "polished," or "glossy" — those words trigger the CGI drift.

3. Clay imitations for hard materials. Glass, liquid, metal, and flame are clay's hardest cases — describe them as "sculpted as a professional clay imitation of [an amber glass dropper bottle / pouring water / a brass kettle]" and they hold. One tested exception, in the cinematic lane only: when a character is in frame anchoring the clay read, real materials for hard props (translucent plastic, metal, real liquid) look excellent and make the frame pop. In an object-only shot there is no anchor and real materials collapse the whole image into product photography — keep everything clay.

4. Handmade geometry — each lane sets how wonky or refined, but nothing is factory-perfect.

5. Real cast shadows and physical lighting — the scene is lit like a real miniature set.

6. Stop-motion cadence in motion — stepped 12fps judder, no motion blur (motion section below).

## The camera lives inside the miniature clay world

Every image is a still the video model will animate, so it is a self-contained scene: the clay world extends past every edge of the frame and the camera sits inside it at a named angle.

Unlike paper, clay tolerates — and gains charm from — miniature-scale cues when they come from the lens: macro feel and shallow depth of field read as a stop-motion film set, not an exterior view.

Never show set edges, workbench, or the room around the set.

## Image model

Canonical references and stills: Nano Banana 2.1 (`nano-banana-2.1`; recommendation `image.claymation`). The claymation style's choice for canonical references and stills, including start frames. Reroll an identical prompt before rewriting it. Use this model and no other image model for those assets.

Start frames are stills and follow that rule; storyboard batch canvases, when chosen, follow GPT Image 2 per multi-shot generation, switchable on the user's feedback.

When a result misses, reroll the identical prompt before rewriting it: once a lane's block is locked, variance is almost always the cause, and character face geometry is the highest-variance thing in the whole style.

## Sub-style menu (pick one per video; name it to the user)

Use the sub-style the user chooses.

One sub-style per video — the locked style block opens every image and video prompt in that video, verbatim.

A lane's character design language (eyes, proportions, hair treatment, geometry energy) is part of the style and stays fixed; the character's identity (face, outfit, coloring) is free per ad and holds via canonical references.

Show the visual menu by default before locking a sub-style, recommend the best fit, and wait for the user's choice. If the conversation has already settled the style, keep it without asking again. If the user explicitly asks you to choose, show the menu and name your pick in one line, then continue.

When presenting the sub-styles, include this exact markdown line in the reply, verbatim, as plain markdown (never inside a code block) — it renders the reference image directly in the chat: one identical scene in each style, numbered and named on each panel:

![Claymation styles 1 to 4](https://f.starpop.org/skill-refs/claymation-styles-v2.webp)

Unless the user has delegated the choice, ask: "Do you want style 1, 2, 3, 4 — or another type of claymation?" and recommend the best fit for the task in one line.

The numbers map to the sub-styles below, in order:

1 = Cinematic · 2 = Goofy · 3 = Clean & simple · 4 = Stop-motion puppet

The panels are named, so accept an answer by name ("the cinematic one") as readily as by number.

When the user asks for another type of claymation, have them describe it (or share a reference image), then build a custom style block from the clay fundamentals above and lock it for the video the same way.

### 1. Cinematic (detailed lane — recommended for most ads)

- Design language: appealing idealized builds with richly sculpted, characterful faces — large almond eyes with prominent white sclera clearly visible around a deeply coloured iris, a dark sculpted upper lash line over sculpted upper and lower lids, thick sculpted brows above a defined brow ridge, defined cheekbones and jaw, smooth unlined young clay skin. Real woven fabric clothing with stitched seams. Macro lens, strong background bokeh, warm practical light. Detailed, densely dressed sets.

- Best for: most ads. The broadest lane — premium brands, hero product shots, story shots, crowds, anything that wants to look like a film rather than a craft project.

- Style block: `Detailed cinematic claymation scene — hand-sculpted plasticine characters with an appealing idealized build and richly sculpted features, matte clay skin carrying thumb-worked smoothing and fine tool striations, chunky rounded clay hands with softly tapered fingertips and no realistic fingernails, real woven fabric clothing with stitched seams, staged on a physical miniature set and photographed with a macro lens at shallow depth of field with strong background bokeh, warm practical lighting with a soft rim light, the scene filling the entire frame with the camera inside the miniature world.`

- Character block: `a hand-sculpted plasticine [person] with an appealing idealized build and richly sculpted features — large almond eyes with prominent white sclera clearly visible around a deeply coloured iris, a dark sculpted upper lash line over sculpted upper and lower lids, thick sculpted brows above a defined brow ridge, defined cheekbones and a defined jaw, a neat sculpted nose, softly sculpted lips, smooth unlined young clay skin — matte clay skin showing thumb-worked smoothing and fine tool striations, sculpted [hair] with deep comb grooves, wearing [real woven garment] with stitched seams`

- Physicality block: `Everything in frame is hand-sculpted plasticine and real fabric, photographed on a physical miniature set — visible tool striations and thumb-worked clay surfaces, woven fabric weave, real cast shadows, the miniature scene filling the entire frame. No photographic human skin, no real human hands, no fingernails, no wrinkled realistic faces.`

### 2. Goofy (googly lane)

- Design language: oversized head; huge round googly cartoon eyes — white sclera, small dark pupils, thick sculpted lids; bold sculpted eyebrows; round blush-pink clay cheeks; wide open-mouthed grin; hand-sculpted clay hair, neatly shaped with a few playful strands out of place. Wonky handmade geometry — nothing perfectly straight; busy, cluttered sets; visible fingerprints everywhere.

- Best for: playful brands, comedic shots, high-energy hooks.

- Style block: `Goofy claymation scene — everything sculpted from plasticine with visible fingerprints and thumb smudges, wonky handmade geometry where nothing is perfectly straight, saturated teal and terracotta palette, the scene filling the entire frame with the camera inside the clay world.`

- Character block: `a goofy plasticine [person] with an oversized head, huge round googly cartoon eyes — white sclera, small dark pupils, thick sculpted lids — bold sculpted eyebrows, round blush-pink clay cheeks, a wide open-mouthed grin, and hand-sculpted clay hair, neatly shaped with a few playful strands out of place`

### 3. Clean & simple (soft matte lane)

- Design language: smooth-matte rounded forms with subtle tool marks, simple dot eyes, gently exaggerated cartoon proportions, tidy compositions.

- Best for: minimal brands, calm explainers, shots where the product should out-detail the world.

- Style block: `Polished claymation scene — everything sculpted from smooth matte modeling clay, clean rounded forms with soft even surfaces and subtle tool marks, gently exaggerated cartoon proportions, refined handcrafted stop-motion feel, the scene filling the entire frame with the camera inside the clay world.`

### 4. Stop-motion puppet (mixed-craft lane)

- Design language: clay figures detailed with tiny real craft materials — thread-wrapped hair, fabric scraps, wire-rimmed glasses, button details — on fully sculpted clay sets; cinematic film lighting, moodier palettes (deep teal shadows, warm amber light).

- Best for: story-driven ads, darker or more cinematic tones, premium narrative feel.

- Style block: `Stop-motion clay puppet scene — clay characters detailed with tiny craft materials: thread-wrapped hair, fabric details, wire accents, on a fully sculpted clay set, cinematic stop-motion film lighting with gentle shadows, the scene filling the entire frame with the camera inside the puppet world.`

## Prompt rules

- Style block first, verbatim — then the scene, then the physicality block. Consistency comes from the block plus canonical references, never "same style as before."

- The full character design language rides on EVERY character in frame. Write it out per character, however long the prompt gets. Abbreviating it to keep a two-character prompt readable is the single fastest way to ruin both faces — anything dropped gets dice-rolled into a generic, simplified face.

- Write emotion as face mechanics, never as an adjective. "Disappointed" and "slumped" produce pleasantly neutral faces. Name the muscles: "her inner brows pushed up and her mouth pulled flat," "his cheek squashed hard against his palm so it deforms, eyelids heavy and half-lowered." This is what makes a shot actually land.

- Keep scene lighting bright and warm. This style dies in low-key, dusk, and golden-hour-with-long-shadows lighting. If a scene genuinely needs a cold source (an open fridge, a monitor, a phone screen), keep it and pin the skin against it: "cold blue light spilling out of the fridge while her warm terracotta clay skin holds its own warm colour against it" — otherwise the clay skin itself turns blue.

- Weave the clay into every element. Name the material treatment on each major object — "a clay serum bottle sculpted as a professional clay imitation of an amber glass dropper bottle," "a coiled clay towel," "clay plants with thumb-pressed leaves" — not just in the block.

- Explicit palette in every prompt. Saturated and high-contrast by default; cinematic runs rich harmonious (sage/cream/terracotta family); puppet runs cinematic-moody (deep shadows, warm practicals).

- Camera inside the world, named angle — "camera at eye level, inside the scene." Tight framing is the cinematic lane's native look; it goes stiff and doll-like when the shot pulls wide.

- The product stays accurate. Attach the canonical product reference whenever the product appears. Sculpt the product in clay like everything else and give it a real printed paper label — that combination keeps the clay world intact while leaving the label legible and swappable for the customer's real packaging. State the label copy explicitly, because the material name leaks into rendered text otherwise ("CLAY PROTO," "CLAY CAFÉ").

- State identity deliberately. Ethnicity, age and build are dice-rolled when unstated, so a character will drift between generations. Either name them, or carry them on a canonical character reference — which is how consistency across shots is actually achieved: generate the character once, then attach that image to every following generation.

- Tasteful whimsy lives in the rendering. Enrich craft details — pressed textures, tiny sculpted props, densely dressed shelves — but the shot's content comes from the storyboard, never from the style.

## Motion (video prompts)

Clay dies in motion when the cadence goes unnamed — models interpolate to smooth organic movement and the material vanishes.

Every clip prompt, transitions included, carries the motion guard:

```
Handmade stop-motion claymation throughout — matte plasticine, visible fingerprints and tool marks, slightly stuttery 12fps stop-motion cadence, no motion blur. Non CGI. Non cartoon. Animation must start at the first frame.
```

(Swap "fine tool striations" for the fingerprint phrase in the cinematic lane.) One motion action per clip — stacked actions multiply drift.

In-scene shots stay simple: one gesture, one camera move.

## Clay shot types

- Tight character medium — the cinematic lane's native shot; strong background bokeh.

- Macro texture close-up — tool striations and fingerprints filling the frame.

- Clay-hands insert — chunky rounded clay fingers with blunt tips and no fingernails, handling the product. Say "sculpted like a clay figurine's hands" or the model renders real human hands.

- Crowd scene — a set packed with sculpted background characters (a train carriage, an audience, a class). A signature of the cinematic lane; name the crowd's faces explicitly ("each one a distinct sculpted clay face with prominent white sclera and thick sculpted brows") or the background turns to mush.

- Worm's-eye miniature — camera at clay-ankle height; the world feels giant.

- Fingerprint insert — a detail shot of an object visibly just-pressed by a thumb.

- Googly-eye extreme close-up — the goofy lane's charm shot.

- Hand-of-god cameo — real hands enter the miniature set mid-shot.

## Workflow (override)

- Recommend multi-shot generation executed as start frames per shot, for simplicity, speed, and cost: it delivers the clay look with far fewer video generations.

- The chained single-shot route is the higher-ceiling alternative; run it when the user names it or asks for the most striking result, and offer it in one line when they ask for the options: clay is the one material where continuous metamorphosis reads as native, and a chain of designed frames, each shot contributing one landing image, is how the most striking clay ads are built. It costs more, takes longer, and needs more expertise (single-shot generation).

- The transition vocabulary below serves either route: the seam rule inside a multi-shot batch, or the frame pairs of a chain.

## Clay motion and transitions

For any start/end-frame clip, build the frame pair by single-shot generation's pair-design rules — one shared anchor generated from the same references in both frames, one action, compositional continuity, explained fates.

Use these frame-pair techniques for motion within a shot or transitions between shots:

- Camera-bridge (anchor fixed, camera moves): push-in from mid shot to macro on the product; pull-back reveal into a new scene.

- World-bridge (camera fixed, clay transforms around the anchor): the scene melts into a swirled plasticine pool while the product stays standing; the scene kneads and reshapes into the next; the scene rolls into a clay ball and unfolds as the next; clay coils and pellets roll in and assemble the product (build-up reveal); a clay smear wipes the frame to the next shot; a real hand re-sculpts one object into another (hand-of-god); a recurring clay blob travels the whole ad, flowing scene to scene (carrier element).

The clip prompt names the bridge explicitly — the one concrete visible action that carries frame A into frame B, derived by diffing the frames (a camera move alone is not a bridge when the subject also changes) — plus the motion guard, and nothing else: the frames carry the style.

Chain end frame → next start frame for a continuously flowing sequence.

Model choice for start/end transition clips follows the central recommendation.

## Known limitations & workarounds

| Failure                                     | Fix                                                                                                                                                              |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Drifts to smooth CGI render                 | Never write "smooth/polished/glossy"; physicality block verbatim; reroll on Nano Banana 2.1                                                                        |
| Characters look generic and simplified      | The full design language was abbreviated — write it out per character, especially in multi-character scenes                                                      |
| The named emotion doesn't show on the face  | Emotion written as an adjective — rewrite it as face mechanics (brows, lids, mouth, where the cheek deforms)                                                     |
| Clay skin comes out blue / colour-stained   | A cold light source in the scene — keep it, but pin the skin's own colour against it                                                                             |
| Faces collapse to dot eyes                  | Specify "prominent white sclera clearly visible around a deeply coloured iris" — the eye line is load-bearing                                                    |
| Goofy hair goes insane                      | Keep "neatly shaped with a few playful strands out of place" — never "sticking out in every direction"                                                           |
| Hands render as real human hands            | "Sculpted like a clay figurine's — thick rounded fingers with plain blunt tips and no fingernails at all"                                                        |
| Glass/liquid renders realistic              | "Sculpted as a professional clay imitation of …" phrasing                                                                                                        |
| Object-only shots stop reading as clay      | Real materials with no character to anchor them — sculpt everything in clay, real printed label only                                                             |
| Product label reads as nonsense             | State the label copy explicitly; the material name leaks into rendered text                                                                                      |
| One character looks different between shots | Text descriptions do not reproduce a face — generate the character once and attach that image as a reference                                                     |
| Transition cuts instead of morphing         | The frame pair broke the pair-design rules — rebuild it per single-shot generation (identical anchor from same references, one action, similar composition) |
| Texture melts away mid-clip                 | Motion guard restated in every clip prompt, transitions included                                                                                                 |

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
