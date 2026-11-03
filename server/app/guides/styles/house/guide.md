name: House
order: 0
on: yes
image_model: auto
blurb: Our style: stylised 3D feature-film animation, warm amber light against cool blue shadows, big readable faces.

<!-- Our own look (docs/house-style), the default for every brand. Each `## ` section below fills the {{token}} of the same name in the step files, word for word; a style's other sections (still, clip, breakdown, script) are extra guidance added to those steps. House has none: its rules are the step files themselves. -->
<!-- Moved 2 Nov from server/app/prompts/styles/house.md and prompts/skills/house.md into one place. -->
<!-- Reed's skill file (was prompts/skills/house.md), its chat front matter: name: house-camera; description: "The House look's camera, motion, transitions and emphasis: a baseline of tools the director uses when they serve the story." -->

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

## house-camera SKILL
<!-- Drafted 2 Nov by the Director from Song-Producer's visual choices in its TEST 1 reference treatment; approved by Reed the same day as a baseline, not rules ("I don't want it to force slow motion or anything... I want it to be pretty creative with a specific baseline"). It covers only how the House look's camera, motion, cuts and emphasis work. The look itself (the render, the light, the faces) is the House look guide's (server/app/prompts/styles/house.md) and isn't repeated here; the story is producer-craft.md's. -->

## Scope
This skill is a baseline of tools for how a House video is shot and cut: where the camera sits, how it moves, how one moment passes to the next, and how a moment is made to land. None of it is mandatory: use a tool when it serves the story, never by habit, and be creative beyond it. It never decides what happens in the story, and it never changes how the world looks.

## The camera moves with purpose
The camera is usually inside the scene and doing something: a slow drift, a push, a follow; a locked-off frame often reads as stiff. One camera move per shot, chosen for what the moment is doing:

- **Push in** on a line that matters or a reaction that matters, so the viewer leans in with the camera. Save it for those moments; a push on everything flattens them.
- **Follow** a character through a space (a waiter weaving through a crowd) at their pace, so the viewer moves with them.
- **Hold still** only for a beat that needs stillness (a stare, a breath before a reveal), and briefly.

## A hook that starts close, then reveals
One strong way in: open on an extreme close-up of the one detail that tells the situation (coins in a wet palm, a cracked phone, a hand frozen mid-reach), then push out or pull back to reveal where we are and who it is. The viewer understands the detail first and the world a second later, which holds them through the first two seconds.

## Emphasis: slow motion, when a moment earns it
Slow motion is a tool for a moment the story turns on (a reveal, a payoff, the one big gag); many videos need none. When it's used, the moments around it stay at full speed, so it lands by contrast: slow motion everywhere leaves no emphasis.

## Entrances: a low angle for a changed hero
When a character returns transformed (new clothes, new confidence, the tables turned), a low angle, walking toward the camera at an even, unhurried pace, can show the change at once, especially when their first entrance sat at eye level or above.

## Mirror shots: setup and payoff in the same frame
When a payoff answers a setup (the same place, the same people, the opposite outcome), shooting the payoff with the setup's framing and angle is a strong option, so the viewer sees the change at once: the clumsy action and the smooth one, the polite smile and the eager wave, the one who got soaked and the one who gets soaked now. Note the setup's framing when it's planned, so the payoff can match it.

## Transitions: a motivated white flash
When a time jump or a change of place passes through a white flash, it reads best when it comes from something in the scene: headlights sweeping the lens, a camera flash, a phone screen's glow filling the frame, a door opening onto bright light. A bare flash with no source is the fallback, not the habit. Inside one place and time, a straight cut usually does.

## Pace
Cuts are usually quick through setup and montage, and every shot still lands one clear action before it cuts. The pace can slow where a moment needs room, and the ending holds long enough for the last line to be heard and read.

## Screens
A screen is always a phone in a character's hand (held up to friends, turned to camera, tapped), never a full-frame insert. When a screen is the point of a moment, push in on the phone in the hand rather than cutting to the screen alone.

## Known limitations & workarounds
- **Slow motion** sometimes comes back at full speed. Name it in the shot as the action ("in slow motion, the drink tips down his shirt") rather than as a camera note, and keep it to the one action.
- **Two moves in one shot** (push in and pan) drift. Pick the one that serves the moment.
- **A mirror shot** only reads if the setup's framing is repeated closely: same side of the subject, same height, same distance.
