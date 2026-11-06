name: Zack D
order: 3
on: no
image_model: auto
video_model: gemini-omni-1.2
blurb: One continuous camera follows the thing being explained through one real set, in realistic game-engine 3D: cutaways and glowing marks show what happens inside.
card: One moving camera
broll: Game-engine 3D

<!-- Reed's Zack D skill (docs/next/skills/zack-d.md, #1097). Reed, 1 Nov: "Skill, drop realistic": the skill's format replaces the semi-realistic cutscene look of 29 Oct. A format worn as a look: a friendly, rounded 3D world on an infinite blue ground, one calm narrator, one continuous camera journey. Not wired (Reed decides later): the skill's background plates, narrator voices and music track, so the world is described in words. The word "stage" never goes in a picture prompt (it draws a stage set): the banned list repairs it. -->
<!-- Reed, 3 Nov (REED-ANSWERS-2, Z1): "Follow the originals." Realistic game-engine 3D on real sets, as in his three Zack D. Films reference videos (examples/); this replaces the 1 Nov blue-world look. Z2–Z4: one real set per video, the cyan world optional; no hard cuts; glows on single parts; no podiums, 3D numerals, scale anchor or podium outro. F2: this file is the look and the camera; the voice, structure, information and sound are formats/zack-d/guide.md. Captions come in post (Reed: "dont worry about captions"). -->
<!-- Moved 2 Nov from server/app/prompts/styles/zack-d.md and prompts/skills/zack-d.md. Zack D is a format and a style (Reed): this file is how it looks and how the camera moves; how its script reads, its pacing and its sound are formats/zack-d/guide.md. -->
<!-- Reed's skill file (was prompts/skills/zack-d.md), its chat front matter: name: zack-d-films; description: "Activate when the user asks for the Zack D Films format by any name: a blue-stage 3D explainer ad with narrator voiceover and signature music, told as one continuous camera journey." -->

## sheet_look
Semi-realistic 3D render, like a modern game engine: realistic human proportions, real skin and hair texture, ordinary everyday clothes in plain colours, a natural face with a slightly stylised finish. Full body, relaxed neutral pose, facing camera, on a plain mid-grey or cyan seamless background with one soft contact shadow, soft even studio light. Age shows in the body and face. One fixed outfit, identical in every view.

## place_look
Semi-realistic 3D set, like a modern game engine: one physical, furnished place with real materials and only the props the story needs, soft physically plausible light with contact shadows; or the home backdrop, a seamless glowing cyan world, lighter behind the subject, with no visible edges. Objects that must be explained can be shown cut away, with a clean bright rim on the cut edge.

## still_look
Semi-realistic 3D game-engine render in 9:16; one clear subject mid-action, centred or on a third, close enough to read on a phone; the set's own light, soft contact shadows; the part that matters marked by a glow in the world; cut-aways show inside objects. No captions.

## clip_style
Semi-realistic 3D, one continuous camera that follows the moving thing: a steady push, track or crane of 2 to 5 s, never a hard cut; links to the next beat with a fast in-world move or a push through an object; glowing marks appear on the part being named. No captions

## fit_look
everyday clothes in plain colours on realistic-proportioned semi-realistic 3D people

## Stills
- Each line becomes one of four shots: the act itself, close; the real place; a macro cutaway inside the part; a reaction face.
- The best visual wins; the video's one set is home. Every shot gets the most entertaining frame it can carry: if the strongest picture is a real office, shoot the office. Home is one set per video: one real, furnished place, or (optional) a seamless glowing cyan backdrop whose trips go to real places painted cyan or teal. The camera explores it from many angles and keeps coming back; departures stay purposeful and short.
- Colour marks the part: a red ring or glow for here or harm, cyan or blue for something working inside, green for rot or smell.
- Graphics are objects, never overlays: glows, cutaways, holograms and flow arrows in the world, lit by the scene's own light. Never flat text on screen.
- Choose each camera angle as the camera follows: macro inside the part, slightly high three-quarter views most often, a low angle when it helps, at most one wide reveal per video.
- Nothing floats or hovers: everything rests on the ground with a soft contact shadow.

## Clips
- One continuous camera move per shot, with the subject's motion and the camera's motion as two separate instructions. One visible change about every second, and every change of beat is a named transition: push through, fast in-world move (whip, arc, lateral), dissolve matched on the subject, material morph; a white flash or wipe only by choice. A plain cut is a choice, never the default.

## camera
- One continuous following camera: an original Zack D. video plays as one continuous camera journey with no hard cuts; imitations cut every few seconds, and that cut rate is exactly what makes them read as imitations.
- The camera follows the moving thing (the pour, the water, the air, the dog, the thrown object) and arrives at each part as it is named.
- It is moving most of the time (over 2% of the frame a second in 67–93% of seconds in the originals); near-still holds last 1–3 s and the subject keeps moving in them.
- Push-in is the default move; pull-outs are reveals (the whole device, the handler, the row of animals).
- Speed: median 6–10% of the frame width a second; the fastest one-second moves push in 22–42%/s, pull out 20–32%/s, pan 18–32%/s, tilt 27–30%/s. The paths are smooth curving fly-throughs (crane, orbit, track along a surface), never handheld.
- Places change by a fast in-world move of 0.15–0.4 s with motion blur, a push through an object, or a dissolve of 0.1–0.35 s matched on the subject.

## banned
in the style of Zack D. Films →
in the style of Zack D →
Zack D. Films →
Zack D →
Pixar-style → semi-realistic 3D
in the style of Pixar →
photorealistic → semi-realistic 3D
photo-realistic → semi-realistic 3D
live-action →
on the stage → in the world
on a stage → in the world

## fixes
refused: Soften it (a cutaway shows the thing, never an injury), then Make another.
face: Make another first. If it drifts again, Change this… "the same face as the sheet: same hair and skin tone, semi-realistic game-engine 3D".
outfit: Change this… naming the one outfit colour, this video's when it gives one, else the sheet's.
product: Change this… "the real product from its image, in the video's set, the label facing the camera".

## sample
A semi-realistic 3D man in his thirties, like a modern game engine, with short brown hair and a calm half-smile, in one plain orange T-shirt, standing in a furnished kitchen.

## The videos
The videos are animated with AI video models: stylized 3D characters, rendered like a realistic modern game engine (Reed, 3 Nov: "Follow the originals").

## pacing
Every seam is chosen. One visible change roughly every second; one continuous camera with no hard cuts: a new camera beat every 2–3 s, each a steady follow of 1–5 s, joined by a fast in-world move or a matched dissolve of 0.1–0.4 s.
Measured in Reed's three Zack D. Films originals (examples/water-alarm-clock, dog-ears-and-tails, chocolate-river):
- Hard cuts: 0 per 10 s (3 of 3). Each video is one continuous take of 30–31 s.
- Camera beats (a new subject or part framed by the moving camera): one every 2.2–3.1 s (3 of 3); each beat 1.0–5.2 s, median about 2.4 s (35 beats).
- Links between beats: a fast in-world move of 0.15–0.4 s with motion blur (whip, arc, lateral), a push through an object, or a dissolve of 0.1–0.35 s matched on the subject (3 of 3).
- Hook: the action is already under way on the first frame and the camera follows it within the first second (3 of 3); the first follow runs 2.6–3.0 s.
- Longest steady follow inside one beat: 4.0–5.2 s (3 of 3), at 9–21% of the frame a second.
- Near-still holds (under 3% of the frame a second): about 10 of 35 beats, 1–3 s each, always with the subject moving.

## Step 1 — The set
One set per video — the chosen set carries the video: every beat uses it, because a constant set is what makes beat-to-beat continuity read (a beat may still leave it for a stronger visual — Rule 1).

## Step 4 — Storyboard
Iteration is cheap here and expensive at the video step — the storyboard is where the work happens.

Pick each shot's shot from the four shot types:

| The script line is…                          | Shot type                                                                                       |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| The action itself                            | The act, close — the thing happening, mid-action, the camera following it                      |
| A place ("in your kitchen", "at the gym")    | The real place — furnished, in the video's set or a short trip from it (Rule 1)                 |
| A mechanism, interior, or "inside X"         | Macro cutaway — the front cut away or an X-ray filling the frame, a glow on the part that works |
| A turn in the story (a problem, a surprise)  | A reaction face — one person's face, a second at most                                           |

The style's signature devices — use them:

- Glows on single parts. A red ring or red glow marks "here" or the part that hurts, blue flow arrows or a cyan glow show something working inside, green shows rot or smell, white swirls show air. The glow sits on the part, never washes the whole world.

- Graphics are objects, never overlays: glows, cutaways, holograms and flow arrows lit by the scene's own light. Flat vector text on screen collapses the style into a generic explainer.

The camera angle is a creative decision.

Pick a deliberate, interesting angle per shot — a macro inside the part, a slightly high three-quarter view, a low angle when it helps, at most one wide reveal per video — and vary angles across the storyboard so consecutive frames feel like a directed sequence.

A frame that reads like a catalog lineup photo is a failed frame — re-angle it.

Under any angle the style's furniture stays: subject centred or deliberately placed, one soft contact shadow.

The opening gets three visual options, always — three distinct concepts, one subject, one scene, a clear state change each, with one line on what it shows and why it works.

Product-led openings can read as ads; choose whether the opening should show the product from the buyer's awareness, the evidence, and the concept.

Every shot resolves four decisions before anything is generated:

1. Job — what this shot does for its script line (prove the claim, land the joke, reveal the mechanism).

2. Action — the single thing that happens inside the shot, one verb: a spray blooms, the water rushes up the pipe, the camera pushes into the jug. A shot without a named action is a static slide.

3. Shot type — from the table above.

4. Transition-out (this style plans each seam from the shot that must land it) — the class that carries it into the next shot: push-through (fly into an object, emerge somewhere else), fast in-world move (whip, arc, lateral), dissolve matched on the subject, material morph. A seam without a named class is an accident on screen. Decide it at this pass — it constrains the neighbouring shots (if shot 2 opens inside the product, shot 1's action must land on the product) — and write each seam's one-sentence physical bridge once both adjacent shots are locked.

One shot shape sits outside the table: a purely connective line ("Here's what actually happens") gets no scene of its own — it rides the camera move between its two neighbours as a _transit beat_ and needs no still.

Shots may exist without script lines, but every script line must have a shot.

## Step 5 — Seam plan
Decide every seam's execution explicitly — an unstated seam gets whatever the model picks.

Three seam executions, and they mix freely across one ad:

- Independent generation — the seam is a hard cut. The originals contain none; use it only by choice.

- Start/end-frame chaining — consecutive clips share the exact seam frame, so the transition executes in-camera. The format's home workflow: a continuous camera journey is precisely a chain.

- Multi-shot batching — several consecutive shots in one generation, each transition stated explicitly in the prompt. Zack D batches carry no audio, because the narration never enters a generation; time each batch from the storyboard's shot durations.

## Step 6 — Stills
Generate one still per shot before animating anything — establish the opening composition in the still and direct subsequent action and camera movement in the video prompt.

A shot earns a second still (its end frame) only when its seam is chained: that pair is designed together, the shot's action carrying frame A to frame B. Omni-batched shots need one frame plus the transition stated in the prompt.

Attach, never describe.

Every still attaches its canonical references as references and describes only what the references cannot carry — the action, the composition, the camera:

1. The set — every still is in the video's one set, described the same way every time.

   Vocabulary law: "stage" lives in the conversation only — never in a generation prompt.

   In a prompt the word summons a physical stage set (platform front edge, studio ceiling, auditorium darkness — tested).

   When the set is the cyan backdrop, prompt it as: _"This world is an infinite canvas: it continues unbroken past every edge of the frame, and the camera is inside it.

   No ceiling, no roof structure, no walls, and no platform edge or visible boundary where the ground ends."_ _"The ground is completely smooth with no grid lines anywhere."_

2. The character sheet — every recurring character gets one: generate it once (full body, relaxed neutral pose, facing camera), then attach that same image to every still the character appears in. Never substitute a generated output for the sheet.

3. The product photo — the catalog image, attached whenever the product appears, rendered photo-accurate.

Prepare 9:16 stills.

Never describe anything as floating or hovering: everything rests naturally with a soft contact shadow.

## Step 7 — Video legs
Animate each leg per the seam plan and the active workflow's requirements, one continuous camera move per shot, subject motion and camera motion stated as two separate instructions.

Request the nearest supported clip duration and reconcile in the editor — retime a chained leg so both anchor frames survive; tail-trim a leg that has only a start anchor.

Include "No captions." in every video prompt.

## Rules
1. The best visual wins; the set is home. Every shot gets the most entertaining, most visually interesting frame it can carry — never sacrifice a shot's best visual to force the set into it: if the strongest hook is the man striding out of a real elevator into a real office, shoot the office. The set is where the video lives the rest of the time: abstract, explanatory and illustrative shots belong in it, the video keeps returning to it, and departures stay purposeful and short.

3. Realistic game-engine 3D: realistic proportions and materials, soft physically plausible light; the product photo-accurate.

4. The phone test. Every still must read clearly on a phone screen in under one second — one subject, one idea, clean negative space.

## Self-check before presenting
- Is every shot its best possible visual — and does the video keep coming home to its one set, with departures purposeful?

- Is every seam's transition class named, and its treatment (independent / chain / omni batch) chosen?

- Is every claim in the script visualised as a physical object, with zero generated screen text?

- Are the character sheet and product photo attached to every still they belong in — and described nowhere?

- Does the hook have three options on the table — with the product out of the hook frame unless it earns its place?

- Is every frame's camera angle a deliberate choice, with variety across the storyboard — no catalog lineup shots?

- Is the word "stage" absent from every generation prompt?

## must keep
- Realistic game-engine 3D on one real set per video (3 of 3).
- One continuous camera with no hard cuts; places change by a fast in-world move, a push through an object or a dissolve matched on the subject (3 of 3).
- The camera follows the moving thing and arrives at each part as it is named (3 of 3).
- The camera is moving most of the time: over 2% of the frame a second in 80%, 67% and 93% of seconds (3 of 3).
- Push-in is the default move: 14 of 35 beats push in, 6 pull out, and pull-outs are reveals (3 of 3).
- Cutaways show inside: the front of an object cut away with a clean bright rim on the cut edge, a body part cut away to the bone, a cyan hologram X-ray (3 of 3).
- Glowing marks in the world point at the part being explained: a red ring or red glow for "here" or the part that hurts, blue flow arrows or a cyan glow for something working inside, white motion swirls for air (3 of 3).
- One set per video, explored from many angles (3 of 3).

## safe to vary
- The set: a furnished real place (2 of 3) or a seamless glowing cyan backdrop with short trips to places painted cyan or teal (1 of 3).
- Which link carries a change of place: one original uses only fast moves, one mostly dissolves, one both.
- How many reaction faces (one to four per video).
- The speed of each move, inside the measured ranges in pacing and camera.
- How far the camera goes inside: a single cutaway or a long track through a mechanism.

## combines with
- The Zack D format (formats/zack-d): all three originals are both (3 of 3).
- Reed, 3 Nov (F2): the Zack D format can wear another style, and this style can carry another voiceover script whose lines describe a physical process the camera can follow.

## measured in the references
- Framing: 9:16; macro (inside a pot, an ear, a cup on the water) alternating with medium, and at most one wide reveal per video; slightly high three-quarter views most often.
- The one cyan home backdrop seen (dog-ears-and-tails): a seamless glowing cyan world, sampled #2eb6ca at the top of the frame, lighter behind the subject; places it visits are painted cyan or teal (a wall sampled #2589aa).
- Average frame colour: #46452d (a dark warm room), #6a7e7e (the cyan backdrop), #645c55 (a candy film set); saturation low to moderate; no heavy grade: colour comes from the set and the glows.
- Light: soft and physically plausible with contact shadows; from low key (one warm key light, deep shadows) to bright and even on the cyan backdrop.
