# Step: Clip prompts
<!-- Inputs: <video_model> (name, min/max seconds, reference limits, recommended images), <assets> (id, kind, name, what it shows; storyboard frames as frame:<clip id>; voice samples as audio), <breakdown> (JSON). Output: ClipPrompts. -->

Write one video prompt per clip in the breakdown. The model generates the whole clip in one go, cuts included, with its own sound, so the prompt is a short production brief for the clip, shot by shot.

**References.** Always use reference media, never the first-frame setting (the model can't combine the two); the storyboard frame goes in as [Image1] and the References line names it the first frame. In order: the clip's storyboard frame, then the characters in the order they first appear in the clip's shots, the place, then every brand screen the clip's shots list. Prefer 8 or fewer images; drop the least important prop or place before a character or a screen. Add a character's voice sample as audio when it has one, and bind it in the References line ("[Image2] is Aiden and uses the voice from [Audio1]."). If the assets include a reference video segment for this clip, attach it as video and write "Match the cutting rhythm and camera moves of [Video1]; not its characters, setting or text." Images are [Image1], [Image2], … in the order you list them; videos [Video1], …; audios [Audio1], …

**Prompt shape** (plain text, these lines, nothing else; the first and last lines are the same audio line, word for word):
```
Audio: only the spoken lines and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] is the first frame. [Image2] is Aiden. [Image3] is Dad. [Image4] is the fomo "Token chart up" screen.
Summary: <who does what, where, and the turn or payoff, in one sentence>.
Style: stylized 3D animated feature film, expressive faces.
Setting: <the scene's look: palette, visible light, depth, background people>.
Shots (hard cuts):
Shot 1 | 0–2 s. Low-angle close-up, push in. Dad leans over the desk, brows crashed down. Dad (shouting): "Seven days. Ten grand."
Shot 2 | 2–3 s. Two quick cuts: an extreme close-up of Aiden, his eyes snap wide; then a close-up of Dad, one brow arching.
Shot 3 | 3–4 s. Close-up on the phone, static. Aiden's phone fills the frame and shows [Image4] exactly.
Keep: Aiden as in [Image2] and Dad as in [Image3], one of each; the screen exactly as [Image4].
Audio: only the spoken lines and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```
Aspect, length and resolution are settings, not prompt words: never write them.

**Timing.** Shot times are whole seconds, back to back from 0 to the clip length (the breakdown keeps its decimals; only this prompt rounds). Round each shot to the nearest second; shots shorter than a second share one segment written as "Two quick cuts: …; then …" (or three), and no segment is shorter than 1 s. A reaction that must be seen gets its own whole second instead of sharing one. Spread the dialogue shots across the clip so the talking doesn't finish early and leave dead air.

**Making it play.** Dialogue is `Name (how it's said): "words"`, word for word from the breakdown, and each spoken line appears once in the prompt. In a dialogue shot with others in frame, add that the others keep their mouths closed. Voiceover is `Voiceover (<who>, <how it sounds>): "words"`, and nobody on screen lip-syncs it. Acting is big and specific: eyes widen before the jaw drops, brows crash for anger, the desperate one is frantic, the winner moves slow and calm, and reactions hold about half a second. Show emotion through face and body, never as light in the eyes. Mention water, waves or echo only when the scene has them. One camera move per shot, in standard terms (close-up, push in, pull out, pan, track, orbit, low angle, overhead, handheld); write anything rarer as "term: what you see".

**Brand screens.** Any shot with a screen describes it as: the phone (or monitor) fills the frame, held still and flat-on, and shows [ImageN] exactly: same layout, numbers, colours and logo, nothing added or changed. Keep hands and glare off the numbers. Never describe the screen's content in your own words; the reference is the content. A product (a bag) is the same idea: front label to camera, steady, shown exactly as [ImageN], no face or limbs unless the script makes it a character.
