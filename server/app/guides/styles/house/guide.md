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
- (range to be set from the reference videos)

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
