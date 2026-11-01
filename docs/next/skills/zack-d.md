---
name: zack-d-films
description: "Activate when the user asks for the Zack D Films format by any name: a blue-stage 3D explainer ad with narrator voiceover and signature music, told as one continuous camera journey."
---

# How to make Zack D. Films-style ads

Turn a script — with or without a product — into an ad in the Zack D. Films format.

A format, not a rendering style: it is defined by the blue stage, the narrator voice, the music, and continuity.

Pixar-style 3D is the default rendering register — state it as a fact, never a question; when the user asks for another animation style (claymation, papercraft…), activate that rendering-style skill and use its style block, and everything else here still applies.

The output wins on continuity: an original Zack D. video plays as one continuous camera journey where every shot change is a designed transition — imitations cut every few seconds, and that cut rate is exactly what makes them read as imitations.

This skill builds on the parent prompt (the voiceover-first doctrine, the storyboard table, the two generation workflows) and adds only what is Zack D: the stage, the voice, the music, and the format's shot grammar.

Move fast — batch questions, state defaults, and end every stage on its hand-off line.

## Step map — resume from what the conversation already establishes

| They gave you…                                    | Run                          |
| ------------------------------------------------- | ---------------------------- |
| Nothing settled yet — the skill just fired        | Step 1 — Kickoff         |
| A stage pick and a script (pasted, or "write it") | Step 2 — Lock the script |
| An approved script                                | Step 3 — Voiceover       |
| A generated, timed voiceover take                 | Step 4 — Storyboard      |
| An settled storyboard                            | Step 5 — Seam plan       |
| A confirmed seam plan                             | Step 6 — Stills          |
| Approved stills                                   | Step 7 — Video legs      |
| All legs generated                                | Step 8 — Music and post  |

A partial answer moves the same way: bank what they gave — never re-ask a settled choice — ask once for what is missing, and run the furthest step the inputs allow.

When one message answers everything a step needs, run the next step in the same reply.

## Step 1 — Kickoff

The first reply is this template filled, and nothing else — no format lecture, no preamble, no extra questions.

The banner does the explaining; the creation gate owns the rest of the ad's frame, so drop from the ask any item the conversation already settled.

The fence below is for your eyes only: the reply ships as plain markdown, and the image line is never wrapped in a code block.

```
This skill makes ads after the famous Zack D. Films format — it builds the images and video, narrates in the Zack D voice, and lays the iconic music under the edit.

![Zack D stage lanes](https://f.starpop.org/skill-refs/zack-d-stage-lanes-v4.webp)

Three answers and we go:
1. Stage — answer by name or number, or name any custom colour. [one-line recommendation of the best lane for this ad]
2. Script — paste yours, or tell me what the ad should say and I'll write it.
3. Product — the workspace product it features, or none.
```

The lanes: 1 Light grid — thin light-cyan grid, educational register · 2 Light clean — flat bright cyan with a soft horizon, the purest original register · 3 Dark grid — glowing grid on a deep blue cove, cinematic register · 4 Dark clean — deep blue glow stage, no lines · 5 Clean studio — warm seamless studio sweep, premium and neutral (off-blue: the format's identity and its gold/red accents read softer) · Custom — a first-class option, offered in words: the user names any colour or mix, you build an empty plate in it (the custom-plate recipe in Step 6), confirm it, then use it exactly like a shipped plate.

A user who asks for a custom stage unprompted gets the same treatment.

One stage per ad — the chosen stage carries the ad: every staged shot uses it, because a constant background is what makes shot-to-shot continuity read (a shot may still leave it for a stronger visual — Rule 1).

Hand-off: stage banked → _"Locked: [stage]."_ — and straight into Step 2.

## Step 2 — Lock the script

The format does not require a product.

When the ad features a workspace product, establish its detailed facts and accurate visual references so the product travels as a consistent element.

When asked to write or revise a script, use the format's register within the user's creative direction: short, plain, factual sentences — the register of someone calmly explaining a surprising thing, never ad copy. Preserve supplied scripts unless the user asks for revisions, and keep revisions within the requested scope.

Every line earns a picture — each script line is the brief for a shot. Find a concrete object, action, or change to visualize it; if a supplied line is difficult to show, flag it and offer an optional wording change rather than rewriting it.

The hook line carries the video: it gets the strongest visual and the most options later.

Hand-off: _"Approve the script (or edit it) and I'll generate the voiceover."_

## Step 3 — Voiceover in the Zack D voice

Narrator voiceover is a format pillar — never on-camera character speech — so the choice is already made: on script approval, generate the take immediately per the parent's voiceover-first doctrine.

Prepare the narration with the chosen verified voice.

In Starpop, the Zack D. Films voices are ready for use:

| Voice                      | Provider   | Voice reference (ready in Starpop)        |
| -------------------------- | ---------- | ---------------------------------- |
| zach d films (default) | Fish Audio | `voice:fish-audio:30d59f6eb137417ab0c463028323f4a8` |
| Zach D (alternate)     | Fish Audio | `voice:fish-audio:b2f2bd4f04cb45ad917be899a868f288` |

Alternatively, the voices can be accessed on Fish Audio, or cloned on ElevenLabs.

These verified voice references belong to this workflow.

Use the default immediately unless the user explicitly asks for the alternate.

Reuse these verified voices without searching for them again. Preserve the approved spoken script and keep delivery directions separate.

Direct the delivery: calm, matter-of-fact, unhurried, slight deadpan — the surprising fact does the work, never an ad read.

Generate the voiceover as one continuous audio take and analyze its real timing, word-level wherever one line will split across shots: the take is the pacing source of truth the storyboard is built against.

The narration never enters a generation — it is laid under the assembled edit in post (slice it on natural phrase boundaries only when a clip must sync to specific words).

Hand-off: _"Generate the take; once it's in I'll time it and build the storyboard."_

## Step 4 — Storyboard

Iteration is cheap here and expensive at the video step — the storyboard is where the work happens.

Use the parent's standard shot table, timed against the voiceover, and design each shot with the format's grammar.

Pick each shot's shot from the format's four shot types:

| The script line is…                       | Shot type                                                                                                                                                            |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The subject or product itself             | Podium — one subject centred in the open world, often in a glowing floor ring                                                                                    |
| A place ("in your kitchen", "at the gym") | Prop island — the place reduced to 2–3 defining props resting directly on the open ground; or the real place itself, when that makes the stronger frame (Rule 1) |
| A mechanism, interior, or "inside X"      | Macro cutaway — cross-section or X-ray filling the frame, still inside the world                                                                                 |
| A number, claim, or comparison            | Data object — the claim as a lit 3D object: extruded gold numerals, a red X, a yellow arrow, molecules as letter glyphs                                          |

The format's signature devices — use them:

- Scale-anchor character. One recurring character who never changes while the world changes scale around him — tiny beside a giant glass, astride a capsule, chest-deep in powder. He pins consistency to one reference, gives every abstract shot a human read, and carries the comedy.

- Colour as state. The world itself shifts colour to mark meaning: gold = value or the win, red = danger or the wrong option, green = the healthy response, cyan glow = mechanism working, grayscale = the rejected alternative — then back to base blue after the shot. Prompt a state change as a coloured light wash over the attached plate: the plate stays "unchanged" as the reference; the wash carries the state.

- Graphics are objects, never overlays. A number is extruded geometry with specular and a cast shadow under the scene's own light. Flat vector text on screen collapses the format into a generic explainer — all captions and screen text are added in post.

The camera angle is a creative decision.

Pick a deliberate, interesting angle per shot — a dramatic top-down with the character presenting up to camera, a low hero angle that makes the product tower, an extreme macro, a wide-angle lean-in — and vary angles across the storyboard so consecutive frames feel like a directed sequence.

The straight-on eye-level podium is the resting state between dynamic shots, not the default; a frame that reads like a catalog lineup photo is a failed frame — re-angle it.

Under any angle the format's furniture stays: subject centred or deliberately placed, generous clean background in frame, one soft contact shadow, clear background kept where the caption will sit.

The opening gets three visual options, always — three distinct concepts, one subject, one scene, a clear state change each, with one line on what it shows and why it works.

Product-led openings can read as ads; choose whether the opening should show the product from the buyer's awareness, the evidence, and the concept.

After they choose, ask once whether they want options per remaining shot or single proposals, and follow that answer for the rest.

Every shot resolves four decisions before anything is generated:

1. Job — what this shot does for its script line (prove the claim, land the joke, reveal the mechanism).

2. Action — the single thing that happens inside the shot, one verb: a spray blooms, the room floods red, the camera pushes into the jug. A shot without a named action is a static slide.

3. Shot type — from the table above.

4. Transition-out (override of the storyboard's Transition-in column: this format plans each seam from the shot that must land it) — the class that carries it into the next shot: push-through (fly into an object, emerge somewhere else), white flash, squeeze wipe, placement hand-off, portal push, material morph. A seam without a named class is an accident on screen. Decide it at this pass — it constrains the neighbouring shots (if shot 2 opens inside the product, shot 1's action must land on the product) — and write each seam's one-sentence physical bridge once both adjacent shots are locked.

Two shot shapes sit outside the table: a purely connective line ("Here's what actually happens") gets no scene of its own — it rides the camera move between its two neighbours as a _transit beat_ and needs no still.

And the ad closes on a VO-silent outro shot: a podium product shot holding clean stage for the end caption is the format's standard closer.

Shots may exist without script lines, but every script line must have a shot.

Hand-off: _"Approve the storyboard (or mark shots to change) and I'll plan every seam."_

## Step 5 — Seam plan

Decide every seam's execution explicitly — an unstated seam gets whatever the model picks.

The parent's two workflows give three seam executions, and they mix freely across one ad:

- Independent generation — the seam is a hard cut. Fine for a seam meant to cut (the originals contain a few), wrong as the default here.

- Start/end-frame chaining — consecutive clips share the exact seam frame, so the transition executes in-camera. The format's home workflow: a continuous camera journey is precisely a chain. The Single-shot generation rules cover the mechanics and the pair rules.

- Multi-shot batching — several consecutive shots in one generation, each transition stated explicitly in the prompt. The Multi-shot generation rules cover the mechanics. Override of its audio slice: Zack D batches carry no audio, because the narration never enters a generation; time each batch from the storyboard's shot durations.

Propose the plan, with options only where the choice is genuinely open.

Hand-off: _"Confirm the seam plan and I'll generate the stills."_

## Step 6 — Stills

Generate one still per shot before animating anything — establish the opening composition in the still and direct subsequent action and camera movement in the video prompt.

A shot earns a second still (its end frame) only when its seam is chained: that pair is designed together under single-shot generation's pair rules, the shot's action carrying frame A to frame B. Omni-batched shots need one frame plus the transition stated in the prompt.

Attach, never describe.

Every still attaches its canonical references as references and describes only what the references cannot carry — the action, the composition, the camera:

1. The stage plate — attach it to every still. In Starpop, the five plates are stored template assets, ready to reference: put the chosen lane's reference in the image reference field as an `image:<uuid>` reference.

   | Stage        | Image reference (ready in Starpop)             | Download                                                         |
   | ------------ | -------------------------------------- | ---------------------------------------------------------------- |
   | Light grid   | `image:c0058153-425e-4868-9540-cc98ae603b72` | https://f.starpop.org/skill-refs/zack-d-plate-grid-v1.png        |
   | Light clean  | `image:d6e699b2-1242-4227-8108-017fa811955a` | https://f.starpop.org/skill-refs/zack-d-plate-clean-light-v1.png |
   | Dark grid    | `image:268c5947-fd2b-42ab-bb43-0248c7877d41` | https://f.starpop.org/skill-refs/zack-d-plate-cove-v1.png        |
   | Dark clean   | `image:0e349944-fe28-4d03-a738-cea9ce199d49` | https://f.starpop.org/skill-refs/zack-d-plate-clean-dark-v1.png  |
   | Clean studio | `image:a760febe-db29-4790-b614-38e6def5cbf0` | https://f.starpop.org/skill-refs/zack-d-plate-studio-v1.png      |

   Alternatively, the plates can be downloaded from the links and attached as uploads.

   Vocabulary law: "stage" lives in the conversation only — never in a generation prompt.

   In a prompt the word summons a physical stage set (platform front edge, studio ceiling, auditorium darkness — tested); in prompts the plate is a world the camera stands inside.

   Prompt the environment only as: _"The environment is exactly the world in the attached background reference image — keep its colours, gradient, grid, horizon height and lighting unchanged.

   This world is an infinite canvas: it continues unbroken past every edge of the frame, and the camera is inside it.

   No ceiling, no roof structure, no walls, and no platform edge or visible boundary where the ground ends."_ For the no-grid plates (clean, studio, custom) add: _"The ground is completely smooth with no grid lines anywhere."_ For a custom stage, create the plate first: generate one empty backdrop still in the user's colour with Nano Banana 2.1, following the plate instructions (a seamless field or sweep, no subject, no props, no grid unless asked), confirm it with the user, then attach that image everywhere exactly like a shipped plate.

2. The character sheet — every recurring character gets one: generate it once (full body, relaxed neutral pose, facing camera, on the attached plate so the lighting matches), then attach that same image to every still the character appears in. Never substitute a generated output for the sheet.

3. The product photo — the catalog image, attached whenever the product appears, rendered photo-accurate even inside the stylized world.

Prepare 9:16 stills.

For Pixar-style frames: Seedream 4.5 (`seedream-v4.5`; recommendation `image.pixarCharacterDesign`). Preferred for the Pixar-style format's character design and overall composition. Alternatives: Nano Banana 2.1 (`nano-banana-2.1`): Frames keep failing or a complex multi-element scene needs stricter instruction-following. For the retouch layer: Nano Banana 2.1 (`nano-banana-2.1`; recommendation `image.retouch`). Retouch the Pixar-style format's rendered frame by attaching it and describing the modification. Seedream 4.5 drifts toward hotter saturation, bigger subjects and occasional stage changes, so restate the plate-unchanged line and the composition in every prompt.

Wherever the grid must be described, keep it abstract — _"the grid is an environmental overlay with no thickness, no edges, and no physical surface, not a platform or slab"_ — and never describe anything as floating or hovering: everything rests naturally with a soft contact shadow.

Hand-off: _"Generate the stills; approve them and I'll animate each leg."_

## Step 7 — Video legs

Animate each leg per the seam plan and the active workflow's requirements, one continuous camera move per shot, subject motion and camera motion stated as two separate instructions.

Request the nearest supported clip duration and reconcile in the editor — retime a chained leg so both anchor frames survive; tail-trim a leg that has only a start anchor.

Include "No captions." in every video prompt.

Never add music to any generation — diegetic SFX only.

Hand-off: _"Generate the legs and assemble them over the voiceover; then I'll hand you the music and post steps."_

## Step 8 — Music and post

The format's background music is "Hide and Sneak" by The Fly Guy Five — a muted plucked-bass arpeggio with a ticking pulse, ~95 BPM.

It ships with this skill as a downloadable track:

`https://f.starpop.org/skill-refs/zack-d-music-hide-and-sneak-v1.mp3`

This is the background music for the finished ad: tell the user to download the track from that link and lay it under the full edit in their editor, at low level beneath the voiceover.

It is not a generation input — never attach it to a video or speech generation, and never ask a model to generate the music.

Captions (small, thin, light white sans, centred in the clean background above the subject) and all screen text are added in the editor, never generated.

## Rules

1. The best visual wins; the stage is home. Every shot gets the most entertaining, most visually interesting frame it can carry — never sacrifice a shot's best visual to force the stage into it: if the strongest hook is the man striding out of a real elevator into a real office, shoot the office. The stage is where the format lives the rest of the time: abstract, explanatory and illustrative shots belong on it (attach the plate), the ad keeps returning to it, and departures stay purposeful and short — the originals leave the stage a few seconds at a time and always come home. The more the ad lives on the stage, the more it reads as this format.

2. Every seam is chosen. One visible change roughly every second; a designed transition every 4–8 seconds; shots run 4–8s carrying a single continuous camera move. A cut is a decision, not a default.

3. Pixar-cute is the register. Friendly stylized characters, rounded forms, soft even lighting. Photorealism is reserved for the product itself.

4. The phone test. Every still must read clearly on a phone screen in under one second — one subject, one idea, clean negative space.

## Self-check before presenting

- Was the first reply exactly the kickoff template — banner rendered, one batched ask, nothing already settled re-asked?

- Is every shot its best possible visual — and does the ad keep coming home to the stage, with abstract and explanatory shots on it and departures purposeful?

- Is every seam's transition class named, and its treatment (independent / chain / omni batch) chosen?

- Is every claim in the script visualised as a physical object, with zero generated screen text?

- Are the plate, character sheet, and product photo attached to every still they belong in — and described nowhere?

- Does the hook have three options on the table — with the product out of the hook frame unless it earns its place?

- Is every frame's camera angle a deliberate choice, with variety across the storyboard — no catalog lineup shots?

- Is the word "stage" absent from every generation prompt — world vocabulary and the infinite-canvas line in its place?

- Is the voiceover one timed take in a Zack D. Films voice, with the storyboard built against it and the narration laid under the edit in post?

## Credit

Format decomposed from Zack D. Films' published work and community ad references; stage, pacing, and continuity rules measured from footage by Starpop.

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
