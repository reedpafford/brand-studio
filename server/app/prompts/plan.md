# Step: Plan (the scene plan)
<!-- Inputs: <brief>, <cast> (the cast's ids and descriptions), optional <places>, <video_model> (name, max seconds per clip), <format> (dialogue, song or narrated), <script> numbered, optional <reference> (the reel this video adapts, from the reel import) or optional <study> (S3a's study of the reference), optional <note> (the editor's words for a new plan). Output: ScenePlan. Checked free by check.plan; the breakdown is made from the approved plan (flows 1b, P1). -->

Turn the script into a scene plan: the script's words grouped into scenes, with where each line happens and what we see. The editor approves the plan before the breakdown is made from it, so it is the story in pictures, simply put: no shots, cameras or timings yet.

**The words are the script's.** Never change, add, drop or reorder a line (rule 19). Every numbered line that has words and isn't a scene heading (SCENE, INT., EXT.) is in exactly one scene, in order, once. For a song the lines are the lyric lines; for a narrated video, the narration's lines as written (a line with two sentences stays whole, in one scene). A [tag] line (an accepted direction like "[Camera] slow push in") goes in the scene of the line it sits next to, its action following the direction.

**The structure.** First choose the structure: its `name`, its `parts` in order, and what it's `based_on`:
- With a <reference> or <study>: follow its beats in order, the same parts at about the same share of the video (name "The reference reel", based on "reference").
- Otherwise: the proven pattern below that fits the brand and the script (name "Pet supplement", based on "pattern").
Give each scene its part.

**Proven patterns** (the parts in order; a part can take several scenes):
- **Pet supplement:** Problem (the symptoms, played big and funny) → Failed fixes (the sprays, creams and pills that don't work) → Why (the hidden cause, shown inside the body) → Discovery (she finds the product) → Proof (weeks later, the symptoms gone) → Payoff (the product, then the pet with it, to the lens).
- **Trading app:** Doubt (someone says he'll fail) → The way out (he opens the app, others lean in) → Grind (small wins, one dip) → Payoff (rich, the doubter sees it) → End line (the phone to the lens).
- **Other app:** Frustration (the old way, played big) → Discovery (the app opens) → First win → Life after (bigger, easier) → End line (the app on the phone to the lens).
- **Food and drink:** Craving → The letdown (the ordinary option) → The find → First bite (close, slow, sensory) → Shared joy → End line (the product to camera).
- **Beauty and care:** The insecurity → Tries that fail → Discovery → The routine → The glow (someone notices) → End line.
- **Health and fitness:** Low point (no energy, the struggle) → Discovery → Small wins → The change → End line.
- **Local service:** The problem → The call or visit → The care (the team at work) → The result → End line.

**The cast.** One cast for the whole video, from <cast> only, named once in `cast` by their ids: the same people and animals in every scene. Each scene lists who is in it. Never add a person the cast doesn't have; a passer-by is part of the place, not the cast.

**Scenes.** Each scene is one place and one time (rule 29): `place` reads like a heading ("INT. KITCHEN — NIGHT", "EXT. PARK — DAY, WEEKS LATER"), never two places ("kitchen, then park" is two scenes). A new place or time starts a new scene, and the script's own scene headings always do. A scene is as long as its lines need, up to what one clip of the video model can hold (<video_model>'s max seconds): split a longer run at a natural turn. Use a place from <places> when one fits, named the same.

**Actions.** Each line gets one action: what we see while it plays, vivid and exaggerated, made for a phone screen. Play symptoms and problems big and funny ("he licks his paw so fast his tongue is a blur"), show the hidden cause as a picture (a camera dive into the belly, an x-ray glow), and keep the payoff warm and quiet. The action shows what the words say, and moves on with them: never the same action twice in a row. Dialogue lines show the speaker saying it and how the others take it. For a song or narrated video, nobody speaks on screen: the action is B-roll that shows the words.

**★ The product.** Mark the key product moments with `product` (the product or screen id from the brand block): the find, the use (the scoop, the tap), the proof and the end. Usually three to five lines, never none. A ★ line shows the real product, label or logo to camera.

**The note (<note>, when given):** follow it over your own choices, still with the script's words unchanged.
