# Look tells (Reed's references, 2026-10-29)

Reed: tonight's real look samples didn't hit their looks; several read as generic Pixar. This note records what each look must show (its tells), what the references were, and what changed in `server/app/prompts/styles/`.

## Why the samples read as generic Pixar

Two causes. The second one affected most looks.

1. **Zack D was described wrongly.** We took it from Starpop's zack-d skill, which draws a Pixar-style cartoon on a cyan stage. The real Zack D. Films shorts look nothing like that (see below).
2. **The sample copied the House sheet.** When a brand has a hero, the sample still attached the hero's House character sheet as [Image1] and asked for them "exactly as in [Image1]". The model copied the House rendering, so the claymation, wool and skeleton samples came back as House-style 3D.
   - The fix is `prompts.sample_still_prompt(look_id, name, from_picture)`. It uses the picture only for *who* (face, hair, colouring, age, outfit) and draws them completely in the look, with the look's own sheet paragraph.
   - Next-Server switches `look_samples.still_input` to it.
   - Skeleton's sample always shows its own skeleton (`own_sample: yes`), never the brand's human.

## The references

| Look | Reference | Opened? |
|---|---|---|
| Zack D | youtube.com/shorts/YhlCwRRnREY "The Cheese Prank That Ended In Tragedy" | Yes: title and 4 frames |
| Zack D | youtube.com/shorts/1b-z9fscEXk "How A Goldfish Gets A Forehead Trim" | Yes: title and 4 frames |
| Zack D | youtube.com/shorts/sPKpPv9Pk0w "The Rotten Chocolate River In Willy Wonka" | Yes: title and 4 frames |
| Skeleton | starpop.ai inspiration ad 3719280191552611, ad 1531843508294925; libraryVideo ef9804d1…, ba39688c… | No: Starpop needs a login |
| Song / Pixar | starpop.ai p/8de9f26f… ad 1033788136102785; inspiration ad 1050341280713172; libraryVideo 1bacaf46…, d9e8a99e… | No: login |
| Pixar | starpop.ai libraryVideo 83e3f424… | No: login |
| Clay (song) | starpop.ai libraryVideo 11cf011e… | No: login |
| Wool crochet | starpop.ai libraryVideo a99fc607… (Wool) and ef6b7eb3… (Crochet) | No: login |

For the ones I couldn't open, the looks keep their tells from the Starpop skill notes in `starpop-2026-10-28/public-skill-files/`. To check them against Reed's picks, the Producer can ask Reed for the video files (an MP4 each, or three screenshots each).

## Each look's tells

**Zack D** (rewritten from the three shorts):
- **Materials:** semi-realistic 3D, like a modern video-game cutscene. Never a cartoon, never a photograph.
- **People:** realistic proportions and normal-size eyes. Smooth, glossy, slightly waxy skin with a sheen on the forehead and nose. Hair in neat modelled chunks. Big expressions pushed a notch too far (a grin, a grimace).
- **Clothes:** one solid saturated colour (a magenta T-shirt, a navy suit with a red tie), smooth cloth.
- **Places:** real everyday rooms (a classroom, a film set, a fish-show table) built from clean, slightly simplified assets. Walls are painted one bold colour (teal, maroon, royal blue).
- **Light:** bright and even, soft shadows, a gently blurred background.
- **Camera:** medium close-ups and close-ups at eye level. Gross or tiny details get a sharp macro close-up (the goldfish's lump, the rotten river).
- **Motion:** plain hard cuts every 2–3 s under a calm narrator.
- **Captions:** the shorts burn in captions, but we never draw text (P3).

**Skeleton** (Starpop's "Bare-Bones Cinematic"):
- **The skeleton:** one full anatomical skeleton with natural adult proportions, tall and lanky. Ivory-cream bones with real bone detail. Large expressive cartoon eyes in the sockets. No clothes unless dressed.
- **The world:** a photoreal environment with a warm grade, soft volumetric haze and a shallow depth of field. The skeleton is the only cartoon element.
- **Sample:** the sample line had drifted to a cute mascot (a cap and a glow). It now matches the sheet.

**Disney Pixar:**
- **Characters:** designed 3D assets, big glossy eyes, sculpted hair clumps.
- **Light:** soft global light, warm bounce light, saturated but harmonious colour.
- **Composition:** hero-frame composition.
- **Change:** none. It's the one look that should read as Pixar.

**Claymation:**
- **Materials:** hand-sculpted plasticine with thumbprints and tool marks, real woven fabric.
- **Camera:** a miniature set shot with a macro lens and strong bokeh.
- **Light:** warm practical light.
- **Motion:** 12 fps stop-motion.
- **Change:** it now says outright "never smooth, glossy computer animation".

**Wool crochet** (one look, as Reed confirmed; both his Wool and Crochet references belong to it):
- **Materials:** everything is knitted or crocheted yarn with visible stitch rows. Knitted dolls with painted faces.
- **Light:** bright daylight.
- **Camera:** a stop-motion film still, from a step back.
- **Change:** it now says outright "never smooth, glossy computer animation: every surface shows yarn".

**No studio names (the Producer):** every look except Disney Pixar (and House and Song, built on it) is described by its own tells, never as "like Pixar". A test holds this.

**Song** (a format, not a look): its look is Disney Pixar's with music-video light. Reed's Song / Pixar references couldn't be opened either.
