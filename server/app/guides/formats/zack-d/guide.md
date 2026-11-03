name: Zack D
order: 3
on: no
engine: narrated
blurb: One continuous 3D camera journey through an infinite blue world, explained by a calm narrator: podiums, prop islands, cutaways and glowing 3D numbers.

<!-- Moved 2 Nov from server/app/prompts/styles/zack-d.md and prompts/skills/zack-d.md: how a Zack D script reads, its structure, pacing, beats and sound. The look and the camera are styles/zack-d/guide.md. -->

## Breakdown
- One continuous camera journey: a designed transition about every 4–8 s, each shot one continuous camera move. Every shot settles four things: its job (prove the claim, land the joke, show the mechanism), its one action (a spray blooms, the room floods red, the camera pushes into the jug), its shot type (podium, prop island, macro cutaway, data object) and the transition out (push through, white flash, squeeze wipe, hand-off, portal push, material morph), which the next shot's opening answers: if shot 2 opens inside the product, shot 1 lands on it.
- A purely connective line ("Here's what actually happens") gets no scene of its own: it rides the camera move between its two neighbours. Every line has a shot; a shot may have no line. The video closes on a podium shot of the product with clean space for the end line.
- The hook line gets the strongest picture. In `hook`, name the chosen opening and two other distinct opening pictures in a clause each (one subject, one scene, a clear change), so the editor can pick; an opening on the product itself has to earn its place.

## Script
- One surprising thing, explained in short, plain, factual sentences: the register of someone calmly explaining something odd, never ad copy. A new draft is Narrated, one calm narrator, never on-camera speech. Every line earns a picture: a concrete object, action or change. The first line gets the strongest picture.
- This shapes a new draft or a variation. A script that already exists keeps every line word for word, dialogue included: Enhance adds pictures, never lines, and a narrator speaks only lines the script gives a narrator (to have one voice read it all, the editor makes the script Narrated).

## Clips
- When the video is narrated, the narrator is a voiceover (calm, matter-of-fact, unhurried, slightly deadpan: the surprising fact does the work) and no one on screen speaks; otherwise the script's speakers say their lines in the same calm register.

## How to make Zack D. Films-style ads
Turn a script — with or without a product — into an ad in the Zack D. Films format.

A format, not a rendering style: it is defined by the blue stage, the narrator voice, the music, and continuity.

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

## Step 7 — Video legs
Never add music to any generation — diegetic SFX only.

## Step 8 — Music and post
The format's background music is "Hide and Sneak" by The Fly Guy Five — a muted plucked-bass arpeggio with a ticking pulse, ~95 BPM.

It ships with this skill as a downloadable track:

`https://f.starpop.org/skill-refs/zack-d-music-hide-and-sneak-v1.mp3`

This is the background music for the finished ad: tell the user to download the track from that link and lay it under the full edit in their editor, at low level beneath the voiceover.

It is not a generation input — never attach it to a video or speech generation, and never ask a model to generate the music.

Captions (small, thin, light white sans, centred in the clean background above the subject) and all screen text are added in the editor, never generated.

## Rules
2. Every seam is chosen. One visible change roughly every second; a designed transition every 4–8 seconds; shots run 4–8s carrying a single continuous camera move. A cut is a decision, not a default.

## Self-check before presenting
- Is the voiceover one timed take in a Zack D. Films voice, with the storyboard built against it and the narration laid under the edit in post?
