# Step: Improve prompt (Quick clip)
<!-- Inputs: <brief> (direction: Cinematic | Realistic | Funny | Product ad; shots: 1–4; seconds), <references> (the server's reference lines, from prompts.reference_lines), <idea> (the editor's text). Output: ImprovedPrompt. -->

The editor wrote a short idea for one clip. Turn it into a video prompt in the same shape as a project clip prompt, so it plays well and shows the brand exactly. The editor's words are theirs: every quoted line and every name stays exactly as written. You only add what we see: camera, movement, reactions, and where the attached brand screens show.

Shape (plain text, these lines, nothing else; the first and last lines are the same audio line, word for word):
```
Audio: only the spoken lines and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: <the reference lines, copied exactly>
Summary: <the idea in one sentence: who does what, where; add nothing that isn't in the idea>.
Style: <{{clip_style}}; plus a few words for the direction>.
Setting: <the look: palette, visible light, depth, background people>.
Shots (hard cuts):
Shot 1 | 0-2 s. <size, angle, one camera move>. <what happens, big and readable>. <Name (in English, how it's said): "words">
Shot 2 | 2-3 s. <size, angle, one camera move>. <one image: what happens>. No one speaks.
Keep: <each character's identity and clothing stable in every shot, as in their [ImageN] (their clothing this video's outfit when it gives one), one of each; each screen's logo and layout, and each product, as its [ImageN]>.
Audio: <the same line as the first>
```

- Use the number of shots in the brief, in whole seconds, back to back from 0 to the clip's seconds; no shot is shorter than 1 s. A reaction that must be seen gets its own shot, long enough to land, and dialogue is spread across the clip so it doesn't finish early. Keep the idea's order of events; make the first shot grab with a close camera or a big reaction on the first beat.
- Dialogue is `Name (in English, how it's said): "words"` (every line names its language, or the model may speak another one) in straight double quotes (turn the editor's curly quotes into straight ones), word for word from the idea, each line once. In a dialogue shot with others in frame, the others keep their mouths closed. If the idea has no dialogue, don't add any. Nobody speaks unless the idea says so: with no dialogue, the first and last lines are "Audio: no one speaks (no voices, narration or dialogue), only <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles."; every shot without a line ends with "No one speaks."; and action is what the body does, never a line in disguise (not "does not sell", "says no").
- No captions, subtitles, titles or overlay text. Text in the world (a 3D number, a sign, a label, a scoreboard, a screen) appears only when the script or the shot calls for it, its words stated exactly; never random or made-up writing, which comes out garbled.
- Every attached screen or product is shown as [ImageN]. A screen is on a phone in the scene, in a character's hand, over the shoulder or close on the hand holding it, held steady and angled to the camera so its logo reads, never a screenshot filling the frame flat-on; it keeps its UI, logo, colours and layout exactly, and its coin, numbers and chart are what the idea needs. Never invent a screen or a figure: a moment the brand has no screen for is shown another way, the phone turned away from us with its light on the face (red for a loss, green for a win) and the reaction carrying it. The character sheets set each face, and each outfit unless this video gives one (the cast line's "wears: … (this video)"). A product (the bag) fills the frame, held still and flat-on, with its shape, logo and main text exactly. Never describe its content in your own words.
- Show emotion through face and body, never as light in the eyes; one camera move per shot, in standard terms (close-up, push in, pull out, pan, track, orbit, low angle, overhead, handheld).
- Aspect, length and resolution are settings: never write them.
