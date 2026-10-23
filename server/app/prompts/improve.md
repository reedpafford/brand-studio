# Step: Improve prompt (Quick clip)
<!-- Inputs: <brief> (direction: Cinematic | Realistic | Funny | Product ad; shots: 1–4; seconds), <references> (the server's reference lines, from prompts.reference_lines), <idea> (the editor's text). Output: ImprovedPrompt. -->

The editor wrote a short idea for one clip. Turn it into a video prompt in the same shape as a project clip prompt, so it plays well and shows the brand exactly. The editor's words are theirs: every quoted line and every name stays exactly as written. You only add what we see: camera, movement, reactions, and where the attached brand screens show.

Shape (plain text, these lines, nothing else; the first and last lines are the same audio line, word for word):
```
Audio: only the spoken lines and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: <the reference lines, copied exactly>
Style: <stylized 3D animated feature film, expressive faces, plus a few words for the direction>.
Setting: <the look: palette, visible light, depth, background people>.
Shots (hard cuts):
1. 0.0–1.6 s. <size, angle, one camera move>. <what happens, big and readable>. <Name (how it's said): "words">
2. …
Audio: <the same line as the first>
```

- Use the number of shots in the brief, timed with decimals so they add up to the clip's seconds. Keep the idea's order of events; make the first shot grab with a close camera or a big reaction on the first beat.
- Dialogue is `Name (how it's said): "words"`, word for word from the idea, each line once. In a dialogue shot with others in frame, the others keep their mouths closed. If the idea has no dialogue, don't add any.
- Every attached screen or product is shown: the phone (or the bag) fills the frame, held still and flat-on, and shows [ImageN] exactly. Never describe its content in your own words.
- Show emotion through face and body, never as light in the eyes; one camera move per shot, in standard terms (close-up, push in, pull out, pan, track, orbit, low angle, overhead, handheld).
- Aspect, length and resolution are settings: never write them.
