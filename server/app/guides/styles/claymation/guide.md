name: Claymation
order: 5
on: no
image_model: auto
video_model: gemini-omni-1.2
blurb: Hand-sculpted plasticine on a miniature set: clay skin with thumbprints, real woven fabric, warm light, gentle handmade movement.
card: Handmade clay
broll: Clay props

<!-- Reed's claymation skill (docs/next/skills/claymation.md, #1095; first from Starpop's claymation-ads, docs/research/starpop-2026-10-28, rule 20), its "Cinematic" lane, the one it recommends for most ads. Its other lanes are their own looks: claymation-goofy, claymation-clean, claymation-puppet. Site rules win: adults keep adult faces (so no "young" skin), and the sheets carry each face. -->
<!-- Moved 2 Nov from server/app/prompts/styles/claymation.md and prompts/skills/claymation.md into one place. -->
<!-- Reed's skill file (was prompts/skills/claymation.md), its chat front matter: name: claymation-animation; description: "Activate when the user wants a video, ad, or B-roll in a claymation, clay, plasticine, or clay stop-motion look." -->

## sheet_look
Detailed cinematic claymation: a hand-sculpted plasticine character with a specific, characterful face and build and richly sculpted features — large almond eyes with prominent white sclera clearly visible around a deeply coloured iris, a dark sculpted upper lash line over sculpted upper and lower lids, thick sculpted brows above a defined brow ridge, defined cheekbones and a defined jaw, a neat sculpted nose, softly sculpted lips, clay skin carrying the lines, jowls and wrinkles the character's age gives them — matte clay skin showing thumb-worked smoothing and fine tool striations, sculpted hair with deep comb grooves, chunky rounded clay hands with softly tapered fingertips and no realistic fingernails. No photographic human skin, no real human hands, no fingernails, no photographic realistic faces. The body and face follow the character's age: an adult has an adult's height, build and face, never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit of real woven fabric with stitched seams, identical in every view, and one silhouette-defining item that reads at a glance.

## place_look
Detailed cinematic claymation: a physical miniature set in which every object is hand-sculpted plasticine with thumb-pressed surfaces and fine tool marks, densely dressed with tiny sculpted props, photographed with a macro lens at shallow depth of field with strong background bokeh, bright warm practical light with a soft rim light, real cast shadows, a rich harmonious terracotta, tan and amber palette.

## still_look
The Claymation look, unless the brand block says otherwise: "Detailed cinematic claymation scene — hand-sculpted plasticine characters with a specific, characterful face and build and richly sculpted features, matte clay skin carrying thumb-worked smoothing and fine tool striations, chunky rounded clay hands with softly tapered fingertips and no realistic fingernails, real woven fabric clothing with stitched seams, staged on a physical miniature set and photographed with a macro lens at shallow depth of field with strong background bokeh, warm practical lighting with a soft rim light, the scene filling the entire frame with the camera inside the miniature world. Faces and builds come from the character sheets, and outfits too unless this video gives its own. Everything in frame is hand-sculpted plasticine and real fabric, photographed on a physical miniature set — visible tool striations and thumb-worked clay surfaces, woven fabric weave, real cast shadows, the miniature scene filling the entire frame. No photographic human skin, no real human hands, no fingernails, no photographic realistic faces."

## clip_style
Handmade claymation throughout: matte plasticine, fine tool striations, gentle smooth motion with one action per shot, a calm camera. Every cartoon touch is sculpted in clay. Non CGI. Animation must start at the first frame

## fit_look
a hand-sculpted claymation look with large almond eyes and matte clay skin

## Stills
- Every character in frame keeps the whole clay design language from their sheet (the white of the eye clearly visible around a deeply coloured iris, the thick sculpted brows): cut short, a face turns generic and simplified.
- Name the clay on every major object ("a coiled clay towel", "clay plants with thumb-pressed leaves"), not only in the look. Glass, metal and flame are "sculpted as a professional clay imitation of an amber glass dropper bottle" (or a brass kettle). Liquids are glossy and wet against matte clay, in any shot. With a character in frame to anchor the clay, a hard prop may be its real material (clear plastic, metal); in a shot of objects alone, everything stays clay but the liquids and the product's real packaging.
- The product is its real packaging, set on a clay plinth or held in clay hands, its label exactly as in its image.
- Never call the clay smooth, polished or glossy: those words turn it into computer animation. Say matte, thumb-worked, tool-striated.
- Keep the light warm by default; a cold, grey or low-key look is allowed for the problem, as long as the fix turns warm and bright. A cold source (a fridge, a phone screen) keeps the skin warm against it: "cold blue light from the fridge while her warm terracotta clay skin keeps its own colour".
- Hands handling something are "sculpted like a clay figurine's: thick rounded fingers with plain blunt tips and no fingernails at all", or they come out as real human hands. A crowd names its faces ("each one a distinct sculpted clay face with the white of the eye clearly visible and thick sculpted brows"), or the background turns to mush.
- Name the feeling, then the brows, lids and mouth, and where the clay deforms: "his cheek squashed hard against his palm, eyelids heavy and half-lowered".

## Clips
- One gesture and one camera move per shot: stacked actions drift. Repeat the clay words in the action ("the clay dog's ears flop"), so the material survives the motion.
- Clay can turn into the next shot: the scene melts into a swirled plasticine pool while the product stays standing, kneads and reshapes into the next scene, rolls into a clay ball and unfolds as the next, or a clay smear wipes the frame; clay coils and pellets roll in and build the product. Name the one visible action that carries one shot into the next.
- The transitions the references use: hard cuts on the voice's phrases; into a hidden world, a push into the face or body and a cut, or a fly through a window frame; whip pans to link a quick routine; a warm light flash.

## lanes
This look has lanes, ways of making it; choose one for this video in `lane`:
- "" (the default, Cinematic claymation): hand-sculpted plasticine on a miniature set with real fabric and warm light; for most stories.
- "claymation-goofy": Goofy Claymation: oversized heads, huge googly eyes, wonky handmade sets; for slapstick and broad comedy.

Goofy clay creatures may live in a hidden world (inside a body, a head, a machine) inside a Cinematic video, while the people stay Cinematic.

## fixes
refused: Soften it, then Make another.
face: Make another first. If it drifts again, Change this… "the white of the eye clearly visible around a deeply coloured iris, thick sculpted brows, exactly as the sheet".
outfit: Change this… naming the real woven pieces in the shot, this video's outfit when it gives one, else the sheet's.
product: Change this… "the product as its real packaging, on a clay plinth or in clay hands, its label exactly as in its image".

## sample
A sculpted clay woman in her thirties with a bob of brown hair and visible thumbprints, in one knitted green jumper.

## pacing
Measured from Reed's five claymation reference videos (examples/*/notes.md):
- Voiceover over B-roll (4 of 5): 2.2–4.5 cuts per 10 seconds (3 of 4 at 4.0–4.5). Median shot 2.1–3.4 s; most shots 1.5–3.3 s. Longest hold 4.5–6 s (3 of 4); one video holds a single story beat for up to 11.4 s with one slow move.
- Character dialogue (1 of 5): 2.0 cuts per 10 seconds, median shot 4.3 s, most shots 3.2–6.1 s. Wides hold 5–8 s while the comedy plays; close-ups 2–5 s for each line; one 14 s shot carries the turn.
- Shortest holds are inserts and chapter cards: 0.2–0.5 s (4 of 5); calendar pages 0.5–1.1 s, a sculpted 3-2-1 countdown 3 s.
- Hook: a voice from the first frame and a face or character on screen by frame 1 (5 of 5 have a word at 0.00 s; 4 of 5 open on a face). The first cut comes at 2.2–5.2 s (5 of 5).
- Cuts land on the narrator's phrases or between lines, never on a beat (5 of 5: none has a beat to cut to).

## camera
- A calm camera: mostly locked off or a slow push in (about 2–8% of the frame a second); faster moves are saved for travelling into or through a hidden world (5 of 5).
- The camera stays inside the miniature world; the set's edges and the workbench are never seen (5 of 5).
- Inside a hidden world (inside a body, a mind, a machine) the camera moves more and faster than around the people (4 of 5).
- Keep framing fairly tight and inside the world ("camera at eye level, inside the scene"): wide shots go stiff and doll-like, though a symmetrical wide of a small set can hold for a comic beat. Never show the set's edges, the workbench or the room around the set. A worm's-eye camera at clay-ankle height makes the world feel giant.
- Camera inside the world, named angle — "camera at eye level, inside the scene." Tight framing is the cinematic lane's native look; it goes stiff and doll-like when the shot pulls wide. A symmetrical wide of a small set can hold for a comic beat.

Every image is a still the video model will animate, so it is a self-contained scene: the clay world extends past every edge of the frame and the camera sits inside it at a named angle.

Unlike paper, clay tolerates — and gains charm from — miniature-scale cues when they come from the lens: macro feel and shallow depth of field read as a stop-motion film set, not an exterior view.

Never show set edges, workbench, or the room around the set.

## must keep
- Clay that shows it was made by hand: fingerprint whorls, pores and fine tool striations, readable in every close-up (5 of 5).
- Macro lens and shallow depth of field: soft, blurred backgrounds behind every close-up and insert (5 of 5).
- Warm practical light as the base: lamps and windows, real cast shadows; the average colour of every reference is warm (5 of 5).
- The fix or payoff is the brightest, warmest, sunniest part of the video: golden window light (5 of 5).
- Graphics are sculpted props in the scene, never flat overlays: calendar pages with sculpted letters, sculpted countdown numbers, checklists on clay cards, glowing clay marks, arrows, charts on clipboards (4 of 5).

## safe to vary
- How much of the world is clay: fully sculpted rooms (4 of 5) or realistic, film-like rooms around clay people (1 of 5).
- Music: none at all (2 of 5) or a quiet tonal bed 11–25 dB under the voice, no drums (3 of 5).
- Sound effects: none, or literal effects on clay events (a thump when something lands, a whoosh on a fly-through or whip, alarms, ticks on a countdown).
- Aspect: 9:16 (4 of 5) or 4:5 (1 of 5). Length: 1 to 4 minutes seen.
- The character: any age and walk of life, held the same across the video (the sheet carries the face).

## combines with
- Formats seen: voiceover over B-roll (4 of 5) and character dialogue (1 of 5). Reed: "this can be used with other formats as well."
- A person and a hidden world (4 of 5): a relatable clay person in ordinary rooms, cut against a clay world that shows what can't be seen (inside the body, inside the head, a little machine). The way in is a push into the face or body, then a cut (2 of 5), or a fly-through a window frame (1 of 5).
- Clay anatomy and sculpted diagrams for explaining (2 of 5): organ cutaways, cells, tiny clay factories with switches, side-by-side clay dioramas.
- Clay chapter cards for a timeline or a list (2 of 5): a tear-off calendar page per week, a sculpted 3-2-1 countdown between sections.
- A live-action end card after the clay (1 of 5).

## measured from the references
- Average colour (one frame a second): #906c5e, #896c5a, #866b55, #7c593f, #544737; brightness 77–113 of 255; hue 17–33°, warm (red above blue) in 76–100% of seconds. Inside-the-body scenes run more saturated (coral, maroon, orange) than the rooms.
- Transitions seen: hard cuts on phrases (5 of 5), a push into a face then a cut into the hidden world (2 of 5), a fly-through a window into the next world (1 of 5), a warm light flash (2 of 5). No reference melts, kneads or smears clay between shots.
- Expression is big and readable: knitted brows, heavy lids, wide open mouths, tears, a sweat drop (5 of 5).
- Voice: 2.6–3.7 words a second while speaking for a narrator, pauses under about half a second (3 of 4 narrated); dialogue is slower, 1.8 words a second, with comic pauses up to 6 s.
- Loudness −14.2 to −16.9 LUFS; narration is very even (loudness range 1.2–4.3 LU), the dialogue piece much more dynamic (12.8 LU).

## How to make claymation videos
The claymation visual style for AI video ads.

Every image made under this skill exists to be animated: a start frame, shot reference, or canonical reference for a video generation — one shot of the ad, visualizing what the voiceover says at that moment.

Two things make the output win: every frame must read as photographed physical clay (fingerprints or tool marks, soft clay sheen, real cast shadows — or the model drifts into a smooth CGI render), and every frame must be a self-contained scene shot from inside the miniature clay world.

## Scope
This is solely a visual rendering style, nothing more.

It never drives scene content — the storyboard belongs to the ad; this skill only decides how the world is sculpted, lit, and animated.

The style suits voiceover + B-roll content best.

## What makes anything read as clay (apply to every sub-style)
1. Visible making-marks on every surface — fingerprints and thumb smudges (goofy, puppet) or fine tool striations (cinematic, clean). A clay world with no trace of hands reads as CGI.

2. Soft clay materiality — matte-to-satin plasticine sheen, slight subsurface warmth; never write "smooth," "polished," or "glossy" for the clay — those words trigger the CGI drift (liquids are the one glossy thing).

3. Clay imitations for hard materials. Glass, liquid, metal, and flame are clay's hardest cases — describe them as "sculpted as a professional clay imitation of [an amber glass dropper bottle / pouring water / a brass kettle]" and they hold. One tested exception, in the cinematic lane only: when a character is in frame anchoring the clay read, real materials for hard props (translucent plastic, metal, real liquid) look excellent and make the frame pop. In an object-only shot there is no anchor and real materials collapse the whole image into product photography — keep everything clay but the liquids and the product's real packaging. Liquids are glossy and wet against matte clay, in any shot.

4. Handmade geometry — each lane sets how wonky or refined, but nothing is factory-perfect.

5. Real cast shadows and physical lighting — the scene is lit like a real miniature set.

6. Gentle, smooth motion — one action per shot, the clay named in the motion (motion section below).

## When a result misses
When a result misses, reroll the identical prompt before rewriting it: once a lane's block is locked, variance is almost always the cause, and character face geometry is the highest-variance thing in the whole style.

## Sub-style menu (pick one per video)
One sub-style per video — the locked style block opens every image and video prompt in that video, verbatim. Goofy clay creatures may still live in a hidden world inside a Cinematic video.

A lane's character design language (eyes, proportions, hair treatment, geometry energy) is part of the style and stays fixed; the character's identity (face, outfit, coloring) is free per ad and holds via canonical references.

### 1. Cinematic (detailed lane — recommended for most ads)

- Design language: characterful builds and richly sculpted faces, lined and older where the character is — large almond eyes with prominent white sclera clearly visible around a deeply coloured iris, a dark sculpted upper lash line over sculpted upper and lower lids, thick sculpted brows above a defined brow ridge, defined cheekbones and jaw, clay skin carrying the lines, jowls and wrinkles the character's age gives them. Real woven fabric clothing with stitched seams. Macro lens, strong background bokeh, warm practical light. Detailed, densely dressed sets.

- Best for: most ads. The broadest lane — premium brands, hero product shots, story shots, crowds, anything that wants to look like a film rather than a craft project.

- Style block: `Detailed cinematic claymation scene — hand-sculpted plasticine characters with a specific, characterful face and build and richly sculpted features, matte clay skin carrying thumb-worked smoothing and fine tool striations, chunky rounded clay hands with softly tapered fingertips and no realistic fingernails, real woven fabric clothing with stitched seams, staged on a physical miniature set and photographed with a macro lens at shallow depth of field with strong background bokeh, warm practical lighting with a soft rim light, the scene filling the entire frame with the camera inside the miniature world.`

- Character block: `a hand-sculpted plasticine [person] with a specific, characterful face and build and richly sculpted features — large almond eyes with prominent white sclera clearly visible around a deeply coloured iris, a dark sculpted upper lash line over sculpted upper and lower lids, thick sculpted brows above a defined brow ridge, defined cheekbones and a defined jaw, a neat sculpted nose, softly sculpted lips, clay skin carrying the lines, jowls and wrinkles the character's age gives them — matte clay skin showing thumb-worked smoothing and fine tool striations, sculpted [hair] with deep comb grooves, wearing [real woven garment] with stitched seams`

- Physicality block: `Everything in frame is hand-sculpted plasticine and real fabric, photographed on a physical miniature set — visible tool striations and thumb-worked clay surfaces, woven fabric weave, real cast shadows, the miniature scene filling the entire frame. No photographic human skin, no real human hands, no fingernails, no photographic realistic faces.`

### 2. Goofy (googly lane)

- Design language: oversized head; huge round googly cartoon eyes — white sclera, small dark pupils, thick sculpted lids; bold sculpted eyebrows; round blush-pink clay cheeks; wide open-mouthed grin; hand-sculpted clay hair, neatly shaped with a few playful strands out of place. Wonky handmade geometry — nothing perfectly straight; busy, cluttered sets; visible fingerprints everywhere.

- Best for: playful brands, comedic shots, high-energy hooks.

- Style block: `Goofy claymation scene — everything sculpted from plasticine with visible fingerprints and thumb smudges, wonky handmade geometry where nothing is perfectly straight, saturated teal and terracotta palette, the scene filling the entire frame with the camera inside the clay world.`

- Character block: `a goofy plasticine [person] with an oversized head, huge round googly cartoon eyes — white sclera, small dark pupils, thick sculpted lids — bold sculpted eyebrows, round blush-pink clay cheeks, a wide open-mouthed grin, and hand-sculpted clay hair, neatly shaped with a few playful strands out of place`

## Prompt rules
- Style block first, verbatim — then the scene, then the physicality block. Consistency comes from the block plus canonical references, never "same style as before."

- The full character design language rides on EVERY character in frame. Write it out per character, however long the prompt gets. Abbreviating it to keep a two-character prompt readable is the single fastest way to ruin both faces — anything dropped gets dice-rolled into a generic, simplified face.

- Write emotion as face mechanics, never as an adjective. "Disappointed" and "slumped" produce pleasantly neutral faces. Name the muscles: "her inner brows pushed up and her mouth pulled flat," "his cheek squashed hard against his palm so it deforms, eyelids heavy and half-lowered." This is what makes a shot actually land.

- Keep scene lighting warm by default; a cold, grey or low-key look is allowed for the problem, as long as the fix turns warm and bright. If a scene genuinely needs a cold source (an open fridge, a monitor, a phone screen), keep it and pin the skin against it: "cold blue light spilling out of the fridge while her warm terracotta clay skin holds its own warm colour against it" — otherwise the clay skin itself turns blue.

- Weave the clay into every element. Name the material treatment on each major object — "a clay serum bottle sculpted as a professional clay imitation of an amber glass dropper bottle," "a coiled clay towel," "clay plants with thumb-pressed leaves" — not just in the block.

- Explicit palette in every prompt. Saturated and high-contrast by default; cinematic runs rich harmonious (terracotta/tan/amber family); puppet runs cinematic-moody (deep shadows, warm practicals).


- The product stays accurate. Attach the canonical product reference whenever the product appears. Show the product as its real packaging, set on a clay plinth or held in clay hands. State the label copy explicitly, because the material name leaks into rendered text otherwise ("CLAY PROTO," "CLAY CAFÉ").

- State identity deliberately. Ethnicity, age and build are dice-rolled when unstated, so a character will drift between generations. Either name them, or carry them on a canonical character reference — which is how consistency across shots is actually achieved: generate the character once, then attach that image to every following generation.

- Tasteful whimsy lives in the rendering. Enrich craft details — pressed textures, tiny sculpted props, densely dressed shelves — but the shot's content comes from the storyboard, never from the style.

## Motion (video prompts)
Clay dies in motion when the material goes unnamed — the clay words ride every clip, or the material vanishes into a smooth CGI render. The motion itself is gentle and smooth, never a stepped stop-motion judder.

Every clip prompt, transitions included, carries the motion guard:

```
Handmade claymation throughout — matte plasticine, visible fingerprints and tool marks, gentle smooth motion with one action per shot. Every cartoon touch is sculpted in clay. Non CGI. Animation must start at the first frame.
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

- The chained single-shot route is the higher-ceiling alternative: clay is the one material where continuous metamorphosis reads as native, and a chain of designed frames, each shot contributing one landing image, is how the most striking clay ads are built. It costs more, takes longer, and needs more expertise (single-shot generation).

- The transition vocabulary below serves either route: the seam rule inside a multi-shot batch, or the frame pairs of a chain.

## Clay motion and transitions
For any start/end-frame clip, build the frame pair — one shared anchor generated from the same references in both frames, one action, compositional continuity, explained fates.

Use these frame-pair techniques for motion within a shot or transitions between shots:

- Camera-bridge (anchor fixed, camera moves): push-in from mid shot to macro on the product; pull-back reveal into a new scene.

- World-bridge (camera fixed, clay transforms around the anchor): the scene melts into a swirled plasticine pool while the product stays standing; the scene kneads and reshapes into the next; the scene rolls into a clay ball and unfolds as the next; clay coils and pellets roll in and assemble the product (build-up reveal); a clay smear wipes the frame to the next shot; a real hand re-sculpts one object into another (hand-of-god); a recurring clay blob travels the whole ad, flowing scene to scene (carrier element).

The clip prompt names the bridge explicitly — the one concrete visible action that carries frame A into frame B, derived by diffing the frames (a camera move alone is not a bridge when the subject also changes) — plus the motion guard, and nothing else: the frames carry the style.

Chain end frame → next start frame for a continuously flowing sequence.

## Known limitations & workarounds
| Failure                                     | Fix                                                                                                                                                              |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Drifts to smooth CGI render                 | Never write "smooth/polished/glossy"; physicality block verbatim; reroll                                                                        |
| Characters look generic and simplified      | The full design language was abbreviated — write it out per character, especially in multi-character scenes                                                      |
| The named emotion doesn't show on the face  | Emotion written as an adjective — rewrite it as face mechanics (brows, lids, mouth, where the cheek deforms)                                                     |
| Clay skin comes out blue / colour-stained   | A cold light source in the scene — keep it, but pin the skin's own colour against it                                                                             |
| Faces collapse to dot eyes                  | Specify "prominent white sclera clearly visible around a deeply coloured iris" — the eye line is load-bearing                                                    |
| Goofy hair goes insane                      | Keep "neatly shaped with a few playful strands out of place" — never "sticking out in every direction"                                                           |
| Hands render as real human hands            | "Sculpted like a clay figurine's — thick rounded fingers with plain blunt tips and no fingernails at all"                                                        |
| Glass renders realistic                     | "Sculpted as a professional clay imitation of …" phrasing                                                                                                        |
| Object-only shots stop reading as clay      | Real materials with no character to anchor them — sculpt everything in clay but the product's real packaging                                                     |
| Product label reads as nonsense             | State the label copy explicitly; the material name leaks into rendered text                                                                                      |
| One character looks different between shots | Text descriptions do not reproduce a face — generate the character once and attach that image as a reference                                                     |
| Transition cuts instead of morphing         | The frame pair broke the pair-design rules — rebuild it (identical anchor from same references, one action, similar composition) |
| Texture melts away mid-clip                 | Motion guard restated in every clip prompt, transitions included                                                                                                 |
