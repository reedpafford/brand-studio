# Step: Clip prompts
<!-- Inputs: <video_model> (name, min/max seconds, reference limits, aspect, resolution), <assets> (id, kind, name, what it shows; storyboard frames as frame:<clip id>; voice samples as audio), <breakdown> (JSON). Output: ClipPrompts. -->

Write one video prompt per clip in the breakdown. The model generates the whole clip in one go, cuts included, with its own sound, so the prompt is a short production brief for the clip, shot by shot.

**References.** Always use reference media, never a first frame (the model can't combine the two). In order: the clip's storyboard frame, then the characters, the place, and every brand screen the clip's shots list. Add a character's voice sample as audio when it has one. Stay within the model's limits. Images are [Image1], [Image2], … in the order you list them; audios [Audio1], …

**Prompt shape** (plain text, these headings, nothing else):
```
References: [Image1] storyboard frame, match its look and framing. [Image2] is Aiden. [Image3] is the fomo "Token chart up" screen.
Style: stylized 3D animated feature film, expressive faces, 9:16.
Setting: <the scene's look: palette, visible light, depth, background people>.
Shots (hard cuts):
1. 0.0–1.2 s. Low-angle close-up, fast push-in. Dad leans over the desk, brows crashed down. Dad shouts: "Seven days. Ten grand."
2. 1.2–1.8 s. Extreme close-up. Aiden's eyes snap wide, mouth falls open.
3. 1.8–3.0 s. Macro insert, static. Aiden's phone fills the frame and shows [Image3] exactly.
Sound: the dialogue as written, <room sound>. No music.
```

**Making it play.** Time every shot from the breakdown's seconds so they add up to the clip length. Dialogue goes in double quotes after the speaker's name, word for word from the breakdown, with how it's said when it matters ("shouts", "mutters"). Acting is big and specific: eyes widen before the jaw drops, brows crash for anger, the desperate one is frantic, the winner moves slow and calm, and reactions hold about half a second. One camera move per shot.

**Brand screens.** Any shot with a screen describes it as: the phone (or monitor) fills the frame, held still and flat-on, and shows [ImageN] exactly: same layout, numbers, colours and logo, nothing added or changed. Keep hands and glare off the numbers. Never describe the screen's content in your own words; the reference is the content. A product (a bag) is the same idea: front label to camera, steady, shown exactly as [ImageN], no face or limbs unless the script makes it a character.

No captions, text overlays or music: the editors add those in post.
