name: House
order: 0
on: yes
image_model: auto
blurb: Our style: stylised 3D feature-film animation, warm amber light against cool blue shadows, big readable faces.

<!-- Our own look (docs/house-style), the default for every brand. Each `## ` section below fills the {{token}} of the same name in the step files, word for word; a style's other sections (still, clip, breakdown, script) are extra guidance added to those steps. House has none: its rules are the step files themselves. -->
<!-- Moved 2 Nov from server/app/prompts/styles/house.md and prompts/skills/house.md into one place. -->
<!-- Reed's skill file (was prompts/skills/house.md), its chat front matter: name: house-camera; description: "The House look's creative direction, from the @nateassets reels: how the story is told in pictures, the camera, framing, cutting, transitions, montage, light and cast." (#1227) -->

## sheet_look
Stylised 3D animated feature-film look (Pixar/Disney-like CG) with expressive eyes and brows. The body and face follow the character's age: an adult has an adult's height, build and face (a defined jaw, adult proportions, about 7 heads tall), never a child's; a teenager looks like a teenager, a child like a child. One fixed outfit, simple, clean and real-world, with fine cloth detail, identical in every view, and one silhouette-defining item that reads at a glance.

## place_look
Stylised 3D animated feature-film look (Pixar/Disney-like CG), dense and specific set dressing with photoreal props, motivated cinematic light: warm amber practicals or golden-hour sun against cool blue shadows, deep but not crushed blacks, no blown highlights.

## still_look
The house look, unless the brand block says otherwise: "Stylised 3D animated feature-film look (Pixar/Disney-like CG). Faces and builds come from the character sheets, and outfits too unless this video gives its own. Fine cloth and prop detail. Lighting is motivated and cinematic: warm amber practicals or golden-hour sun against cool blue shadows, deep but not crushed blacks, no blown highlights. The camera is mostly at eye level and alive, pushing, panning and tracking with the action, with a shallow depth of field and creamy background blur. Expressions are big and readable with the sound off."

## clip_style
Pixar-style 3D animation, warm amber key against cool blue shadows, shallow depth of field, dynamic cinematic camera moves, big readable expressions

## fit_look
a stylised 3D cartoon look with expressive eyes

## banned
photorealistic → stylised
photo-realistic → stylised
live-action →
in the style of Pixar →
Pixar-style → animated-feature

## fixes
refused: Soften it (the free fix rewords the picture, never the lines), then Make another.
face: Make another first: the same prompt often lands. If it drifts again, Change this… "keep the face exactly as the sheet".
outfit: Change this… naming the outfit's key pieces in the shot, this video's when it gives one, else the sheet's ("the red beanie, the grey hoodie").
product: Change this… "the real bag from its image, the label facing the camera and readable".

## sample
A warm, friendly woman in her thirties with shoulder-length dark hair, in one plain mustard sweater, smiling at a phone in her hand.

## The videos
The videos are animated with AI video models: stylized 3D characters.

## house-camera SKILL
<!-- Started 2 Nov by the Director as a baseline of camera tools, approved by Reed as a baseline, not rules ("I don't want it to force slow motion or anything... I want it to be pretty creative with a specific baseline"). Rewritten 3 Nov after Reed's test notes ("not close to nate assets", "the camera panning makes no sense, it should be cuts", "things make sense in chronological order", "you aren't doing flashbacks", "the creative direction, camera work, visuals, etc you NEED to know"). It now carries what the @nateassets reels actually do: counted over their 493 animated shots (docs/references/nateassets/*/BREAKDOWN.md) and measured in docs/house-style/HOUSE-STYLE.md, which the director never saw before. The render and the faces are this guide's look sections above; the story is craft.md's. (#1227, moved here 3 Nov.) -->

## Scope
This is House's creative direction: how Nate's reels tell a story in pictures, so the director can think the same way. None of it is mandatory: use a tool when it serves the story, never by habit, and be creative beyond it. It never decides what happens in the story, and it never forces slow motion or any other device.

## How the story is told in pictures
- **Start at the fight.** The first line is the insult, the rejection or the dare, at 0 s, with the stakes plain. No setup before it.
- **One underdog, one doubter, one promise.** The doubter (a parent, an ex, a rich rival) mocks the hero; the hero answers with a short dare or simply leaves. Everything after pays that off.
- **Flashbacks for what was lost.** A promise broken or a past that changed is shown, not told: a short flashback ("6 MONTHS AGO…", "PREVIOUSLY…"), soft, overexposed, warm and dreamy, then a cut back to the present in the same pose with the other person. It can return later as a flash when someone realises what they gave up.
- **A low point the viewer feels.** The hero alone, often at night or on the steps outside: the one place the pace slows, a close-up held 3–5 s with a slow push in.
- **Proof, not talk.** The middle is a mostly wordless montage of the hero doing the thing that changes his life (trading on the phone, packing orders), with the result growing in frame.
- **A time jump, signalled.** A white flash into a card ("2 YEARS LATER…") over a hero object.
- **The reversal mirrors the opening.** The same people, often the same place, the same words turned around. The hero underplays it (a small smirk, a calm "Yeah"); the doubters overplay (screams, begging, tears), and their reaction is the punchline.
- **A comic button.** The last image is the funniest face or the doubters getting exactly what they gave (the whole wedding eating outside).

## Camera: it holds still, the people move
About four in five of Nate's shots hold still. The energy comes from the characters: Mom bursts through the door and lunges at the lens, a hoodie is thrust at the camera, a chair spins round, a car pulls up into frame. A slow push in (about 7 of every 100 shots) is kept for emotion and status: the face falling, the tear, the resolve, the car grille. Pans, follows and orbits are rare (about 1 in 20). A camera that drifts or circles round a scene reads as aimless.

## Framing: close, frontal, simple
- Mostly medium shots and close-ups, frontal, at eye level. Faces fill the frame.
- Every big line gets its close-up, and the reaction gets its own shot straight after.
- Two-shots across a table or nose to nose in profile, the same set-up returned to through the scene, so the viewer always knows where everyone is.
- Extreme close-ups of an eye or a mouth for the biggest moments.
- Inserts of the thing that matters, held up to the lens and filling the frame: the phone with the number, the wallet, the ring box, the keys.
- Wides for status set pieces (the supercar, the villa, the wedding) and for the final button.
- One or two people in an ordinary, specific place (a bedroom, a stock room, a dinner table, a street). Extras stay soft in the background; never wide shots of small figures in grand sets.

## pacing
- Fast: about one cut a second, often faster, and it never feels choppy because every new shot shows one new thing: the face the line lands on, the thing it points at, the result.
- Things happen in order, and the world keeps its state. Each shot picks up where the last one left off: the wallet slammed on the desk stays on the desk; someone who walks out is gone and the door closes behind him; a spilled drink stays spilled.
- Fast on information, held on feeling: the turn of the story (hurt hardening into resolve) gets a held shot, then the pace picks up again.
- The ending holds long enough for the last line to be heard and read.
- **Is every second earning its place?** The pace is fast because every moment carries something new; a beat that only repeats what we know is cut, and a feeling that matters is given room.
- Measured in the 10 House reference reels (deep-watch, 3 Nov; cut counts checked by eye; per-reel notes in examples/*/notes.md):
  - Overall: about 7–10 cuts every 10 s (10 of 10); the median shot is 0.45–1.0 s (10 of 10); half to four in five shots are under 1 s (10 of 10).
  - Hook: the first line lands at 0–0.3 s (10 of 10). The first shot is short, 0.1–1.8 s, with a cut on the next line (7 of 10), or one held take of 3.5–5.4 s (3 of 10).
  - Dialogue scenes: shots of 0.9–5 s (median about 1.5–2 s), a cut on each line, the next shot arriving 0.05–0.2 s before the next line; reaction inserts 0.3–0.9 s (10 of 10).
  - Longest hold: one long take a video, 5–10.6 s (9 of 10; the tenth's longest is 3.9 s): the argument played out, the turn pushing in to an extreme close-up (9–10 s, 3 of 10), or the payoff two-shot.
  - Wordless montage: shots of 0.1–0.8 s (median 0.35–0.45 s), 13–25 cuts every 10 s, each montage 3–16 s long (10 of 10).
  - Payoff: singles and two-shots of 0.5–3.3 s, ending on a crash zoom or whip into a reaction close-up (8 of 10).

## Transitions
- A quick whip-blur joins most scene changes.
- A white flash marks a time jump, best when it comes from something in the scene (headlights, a camera flash, a phone's glow).
- Match cuts: the same pose, a bigger world (bedroom, then stock room, then warehouse).
- Inside one place and time, a straight cut.

## Montage
A locked-off frame, the same pose, with jump cuts as time passes: day and night flickering behind him, the outfit changing, the stacks or the balance growing in frame. Wordless process inserts (typing, packing, tapping Buy). Before-and-after in one shot. Fast motion on the hero while the world moves at normal speed.

## Light and look
- Soft, motivated light with the face always lit: a warm, soft key from the front or side, the shadow side light and warm, never grey or black.
- Nate's usual set-ups: a warm day interior (soft window key, cool grey walls); night lit by a phone or laptop with a warm doorway behind (the grind, the low point); golden hour or sunrise backlight (the turn, romance); a high sun exterior (status); blue hour city (the reveal after the time jump); a bright warehouse or showroom (the scale-up).
- Flashbacks: overexposed, warm pink-peach, soft bloom.
- Colour: warm skin and neutral rooms, moderate saturation, one saturated hero object per scene (the red car, the ring box). A phone's glow is an accent on the hands and a cheek, never a coloured wash over a face.

## Cast who read at a glance
Every role looks like what it is the moment it appears: the love interest or the ex strikingly attractive and glamorous, the rival broad, square-jawed and smug, the doubting parent the part, the hero likeable and plain. One fixed outfit each. After the turn the hero can be visibly upgraded, or, as the power move, come back in exactly the same clothes. Attractive, never sexual: the video model refuses anything that could read that way. Status lives in props you can see.

## Screens
A screen is a phone in a character's hand: held up to the lens so it fills the frame and reads, turned to someone, tapped. Every time the brand is named, its logo and real UI are clearly visible.

## Emphasis, entrances and mirrors
- **Slow motion** for the one moment the story turns on, if any; many videos need none.
- **A changed hero's entrance** can come walking toward the camera through a doorway, the room turning to look.
- **Mirror shots:** shoot the payoff with the setup's framing, so the change reads at once.

## Known limitations & workarounds
- **Slow motion** sometimes comes back at full speed. Name it in the shot as the action ("in slow motion, the drink tips down his shirt").
- **A mirror shot** only reads if the setup's framing is repeated closely: same side, same height, same distance.
- **A camera move** written into a still shot tends to make the model drift. Say "static" for a held frame.

## must keep
<!-- 3 Nov, from the 10 House reference reels (study-house; evidence per reel in examples/*/notes.md). -->
- Caricatured 3D faces that read on mute: big round eyes with one sharp catchlight, thick dark brows doing the acting, a small nose, a mouth that opens to cartoon extremes on a shout; reactions pushed to the extreme, often in a close-up that fills the frame (10 of 10).
- One fixed real-world outfit per character in every shot (a plain tee with a small logo, joggers, a chain, a cap; a dark suit), changed only to mark the turn (10 of 10; changed on purpose in 3).
- Real, ordinary places, densely dressed, with near-photoreal props; inserts with no one in them sit close to photoreal and are cut in with no change of grade (10 of 10).
- Light that belongs to the place and the time of day, so each scene has its own: a soft warm day interior, a night lit by a screen with a warm doorway behind, golden hour for a turn, blue hour or a bright warehouse for the win (10 of 10).
- The camera holds while the people move; a move is punctuation on a beat: a push in on a feeling, a pull-out to reveal, a snap or crash zoom into a reaction, a whip into a reveal (10 of 10). No handheld in the animated part.
- Eye-level framing: close singles and over-the-shoulder shots with a soft shoulder or object in the foreground, nose-to-nose profiles for stare-downs; low angles kept for status objects (10 of 10).
- Two speeds of cutting, and one long take a video (see pacing).
- Montages that show time and scale in one locked frame: the same pose with a bigger world behind, day and night flicking past, ghosted fast-motion, stacks growing (7 of 10).
- Motion carries the transitions: whip and smear blur in every reel, with things thrown or stacked up to the lens, morphs, and a white flash (6 of 10).

## safe to vary
- How the hook is cut: a burst of short shots or one held take.
- Which places and times of day appear, and whether there is a night low point at all (7 of 10 have one) or a golden-hour beat.
- How many montages (1–3) and how long each runs (3–16 s).
- One-off visual gags: price tags glowing in the pupils, a clock in the frame, a view from inside a box.
- How a memory is treated (a bloomed, washed-out pink-peach) and how a time card looks (white serif on black, or white capitals on a hero object after a flash).

## combines with
- **Dialogue** is its format: all 10 references are dialogue skits.
- **Real footage:** every reference ends on a 1.5–3.7 s live-action handheld tag after the animation (10 of 10), and one cuts a 1.1 s real phone clip into the middle (1 of 10). In the references it is the creator's own life; for a brand it is the slot for the brand's real thing.
- Not seen in the references, so untested: a narrated or song script over House's wordless montages, which already run on music with no lines.

## measured in the reference videos
<!-- 3 Nov, deep-watch kit (per-shot colour, per-second camera flow, stems and spectrograms). Facts only; anything that disagrees with the lines above is listed for Reed in the PR, not changed here. -->
- Colour (average of the frame): day interiors #594a43 to #7d5a49, gently warm, saturation about a quarter to a third; night #0e1d32 to #30343c, blue, saturation about two thirds, blacks deep but not crushed; golden hour #8a5e56 to #997d72; the whole animated part averages about #665650 to #6f5556. The colour comes from props and one hero object, not from a saturated grade.
- Camera: in the four reels counted second by second, 54–74% of animated shots are static. Slow pushes move about 2–13% of the frame a second; crash zooms 25–30%; the quickest follow pans 13–35%.
- Depth of field: shallow on close-ups; wides keep the set readable (7 of 10 noted).
- No slow motion in any of the 10; fast motion and ghosted time-lapse instead.
- Sound: a music bed under every second (no silence in 10 of 10), about −14 LUFS overall; under lines it is a soft pad or low drone about 10–27 dB below the voice (8 of 10), and it rises with drums when no one speaks. Whooshes and impacts on whips, a ding on each notification. Cuts follow the lines and the sound hits, never the musical beat (10 of 10 at chance).
- Captions belong to the edit, never the clips (rule 32): in the references one word at a time, bold capitals with a thin black outline at 55–70% of the frame's height, white in the older reels and bright yellow italic in the newer ones; none during wordless montages.
