# Step: Improve prompt (Quick clip)
<!-- Inputs: <brief> (direction: Cinematic | Realistic | Funny | Product ad; shots: 1–4; seconds), <references> (the server's reference lines, from prompts.reference_lines), <idea> (the editor's text). Output: ImprovedPrompt. -->

The editor wrote a short idea for one clip. Turn it into a video prompt in the same shape as a project clip prompt, so it plays well and shows the brand exactly. The editor's words are theirs: every quoted line and every name stays exactly as written. You only add what we see: camera, movement, reactions, and where the attached brand screens show.

Shape (plain text, these lines, nothing else; the first and last lines are the same audio line, word for word):
```
Audio: only the spoken lines and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: <the reference lines, copied exactly>
Summary: <who does what, where, and the turn or payoff, in one sentence>.
Style: <stylized 3D animated feature film, expressive faces, plus a few words for the direction>.
Setting: <the look: palette, visible light, depth, background people>.
Shots (hard cuts):
Shot 1 | 0–2 s. <size, angle, one camera move>. <what happens, big and readable>. <Name (how it's said): "words">
Shot 2 | 2–3 s. <or "Two quick cuts: …; then …" for beats shorter than a second>
Keep: <each character as in their [ImageN], one of each; each screen or product exactly as its [ImageN]>.
Audio: <the same line as the first>
```

- Use the number of shots in the brief, in whole seconds, back to back from 0 to the clip's seconds; no shot is shorter than 1 s. A reaction that must be seen gets its own second, and dialogue is spread across the clip so it doesn't finish early. Keep the idea's order of events; make the first shot grab with a close camera or a big reaction on the first beat.
- Dialogue is `Name (how it's said): "words"`, word for word from the idea, each line once. In a dialogue shot with others in frame, the others keep their mouths closed. If the idea has no dialogue, don't add any.
- Every attached screen or product is shown: the phone (or the bag) fills the frame, held still and flat-on, and shows [ImageN] exactly. Never describe its content in your own words.
- Show emotion through face and body, never as light in the eyes; one camera move per shot, in standard terms (close-up, push in, pull out, pan, track, orbit, low angle, overhead, handheld).
- Aspect, length and resolution are settings: never write them.
