# Gold standard breakdown: why those reels work and how to prompt it

Gemini 3.5 Flash watched Reed's gold-standard reels shot by shot on 2026-10-18 (`DehudnaAmce`, `DelfKPdA4f0`,
`DecatUAggVY`, `DeLWYN4RQd9`). It also watched the reference that GF Betrayal copies (`DdkD1vNqpUa`) and our three
GF Betrayal clips. The raw results are in `gemini/gold-standard-watch-2026-10-18.json`: every shot with its framing, camera,
acting, emotion, setting and a Seedance sentence that recreates it.

## Why ours fell flat

Watched one at a time, Gemini scores everything about 9, ours included. That makes it useless as a judge. Watched
against the reference's shot list, the same GF Betrayal clips score **4 out of 10** (the reference is 9):

| | Reference / gold standard | Our GF Betrayal (1:1 copy, made 2026-10-18 before the scene standard) |
|---|---|---|
| Acting | Faces snap between keyframes: eyes go wide before the jaw drops, brows crash down, mouths open wide on stressed words. Reactions hold about 0.3–0.5 s, then cut | "Mild facial movement and slow expression transitions"; a "rigid, frozen smirk" |
| Cuts | Under 1.8 s a shot, faster in montages; every turn in an argument gets its own close-up | Static frames held for 2–4 s |
| Light | The low point and the grind in a dark blue room, lit by the warm laptop key light; the payoff on a sun-drenched avenue | An evenly lit warm kitchen; the late-night grind in flat daylight |
| Background | Pedestrians react, crowds film, depth from foreground clutter and bokeh | An empty street |

Our prompts explain it. Copy mode copied the reference's beats, but its shot sheet toned them down: "restrained movement",
"small, open-handed appeals", "a small, settled smile", "static medium close-up", "kitchen room tone". By design, a 1:1
copy also got none of the scene standard (no color mood, no visible light, no background people). The planner also never knew the reference's look: the reference watch recorded each shot's camera and motion but not its
light, colors or background people. The fix (2026-10-18) records them and has copies keep them.

## What the gold standards do (Gemini's rules, merged)

**Acting**
- Eyes widen fully just before the big reaction (the jaw drop, the scream), and expressions snap from one pose to the next.
- Squash and stretch on faces: the mouth opens double on a scream, the brows knit deep for anger and arch high for shock.
- Speeds contrast: the desperate character is frantic (begging hands, twitching), the winner moves slowly and with control.
- Reactions hold 0.5 to 1 s before the cut. Clear silhouettes: leaning in to want, shrinking in shame, leaping in joy.

**Shots**
- About 0.3 to 1.8 s a shot. Every turn in a conversation gets its own tight close-up, with shot and counter-shot.
- Low angle for power, a high or isolated wide shot for defeat. Push in on focus, pull out to show time passing, track the payoff.
- Macro inserts of the screen, the number, the ring or the clock move the story on without dialogue.

**Scenes**
- Color temperature tells you the story state: cold blue for struggle and poverty, warm gold for memories and wealth, neon purple and magenta at night for success.
- Visible key lights (laptop glow, desk lamps, neon) tint the skin, with rim light to separate the head from the background.
- Depth: foreground clutter (book stacks, car doors, a laptop lid), shallow depth of field, bokeh city lights. Never a plain dark void.
- Background extras are always doing something (filming, walking past, gasping, pointing). Hero props get rim light and glossy reflections.

## How we prompt it now

- **1:1 copies: the reference comes first.** Many references come from the same accounts as the gold standards.
  The reference watch (`gemini_watch.REEL_ASK`, `gemini-reel-v3-look`) now records each shot's **look** (palette,
  visible light, background people) and **acting**, next to its size, camera move, speed and motion. The planner keeps
  all of it (`genie.MOTION_FROM_REFERENCE`): the copy's `Setting:` sentence describes the reference's own look for
  those shots, and reactions play at least as big as the reference's. The house standard fills only what the reference
  doesn't show. A copy never gets a guessed mood default that could fight its reference.
- **Originals and remixes**: each clip carries one `Setting:` sentence from `scene_standard.py` (the mood's palette,
  the visible light, depth, atmosphere and background people who react).
- **Detailed (shot sheet) prompts** add the `Performance:` line (`genie_workflow.PERFORMANCE`): eyes snap wide before
  the jaw drops, brows crash, reactions hold about half a second, the desperate move frantically, the winner stays cool.
- **The copy and remix planners** (`genie.REFERENCE_MODES`) never write a reaction as small, subtle, slight,
  restrained or settled.
- **Short prompts** keep the cut-rhythm line (`prompt_style.CUT_RHYTHM`) and comic poses.

Sentences Gemini wrote for a single Seedance shot, as examples of the level of specificity that works:

- "Low-angle shot of a young boy kneeling with an open ring box, gasping in horror, as a fashionable blonde girl yells at him. Dense background crowd in neon-lit Times Square at sunset, rim lighting on characters."
- "Extreme close-up side profile. Young boy staring wide-eyed in absolute horror at a screen, dark background with dramatic red and green neon chart lights reflecting sharply in his huge blue eye."
- "Low-angle over-the-shoulder shot. A young man typing on a dark laptop in a dim bedroom lit by blue ambient backlight and the warm laptop screen key light. Behind him a girl stands with arms crossed, frowning."
