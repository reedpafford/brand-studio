# Step: Clip prompts
<!-- Inputs: <video_model> (name, min/max seconds, reference limits, recommended images), <assets> (id, kind, name, what it shows; storyboard frames as frame:<clip id>; voice samples as audio), <breakdown> (JSON). Output: ClipPrompts. -->

Write one video prompt per clip in the breakdown. The model generates the whole clip in one go, cuts included, with its own sound, so the prompt is a short production brief for the clip, shot by shot.

**References.** Always use reference media, never a first frame (the model can't combine the two). In order: the clip's storyboard frame, then the characters in the order they first appear in the clip's shots, the place, then every brand screen the clip's shots list. Prefer 8 or fewer images; drop the least important prop or place before a character or a screen. Add a character's voice sample as audio when it has one, and bind it in the References line ("[Image2] is Aiden and uses the voice from [Audio1]."). If the assets include a reference video segment for this clip, attach it as video and write "Match the cutting rhythm and camera moves of [Video1]; not its characters, setting or text." Images are [Image1], [Image2], … in the order you list them; videos [Video1], …; audios [Audio1], …

**Prompt shape** (plain text, these lines, nothing else; the first and last lines are the same audio line, word for word):
```
Audio: only the characters' voices and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
References: [Image1] storyboard frame, match its look and framing. [Image2] is Aiden. [Image3] is Dad. [Image4] is the fomo "Token chart up" screen.
Style: stylized 3D animated feature film, expressive faces.
Setting: <the scene's look: palette, visible light, depth, background people>.
Shots (hard cuts):
1. 0.0–1.2 s. Low-angle close-up, push in. Dad leans over the desk, brows crashed down. Dad (shouting): "Seven days. Ten grand."
2. 1.2–1.8 s. Extreme close-up. Aiden's eyes snap wide, mouth falls open.
3. 1.8–3.0 s. Close-up on the phone, static. Aiden's phone fills the frame and shows [Image4] exactly.
Audio: only the characters' voices and <room sound>. No music, background music, BGM, score, instrumental, melody, synth effects, ambient pad, drone, swelling tone or stinger. No subtitles.
```
Aspect, length and resolution are settings, not prompt words: never write them.

**Making it play.** Time every shot from the breakdown's seconds so they add up to the clip length. Dialogue is `Name (how it's said): "words"`, word for word from the breakdown, and each spoken line appears once in the prompt. In a dialogue shot with others in frame, add that the others keep their mouths closed. Voiceover is `Voiceover (<who>, <how it sounds>): "words"`, and nobody on screen lip-syncs it. Acting is big and specific: eyes widen before the jaw drops, brows crash for anger, the desperate one is frantic, the winner moves slow and calm, and reactions hold about half a second. Show emotion through face and body, never as light in the eyes. Mention water, waves or echo only when the scene has them. One camera move per shot, in standard terms (close-up, push in, pull out, pan, track, orbit, low angle, overhead, handheld); write anything rarer as "term: what you see".

**Brand screens.** Any shot with a screen describes it as: the phone (or monitor) fills the frame, held still and flat-on, and shows [ImageN] exactly: same layout, numbers, colours and logo, nothing added or changed. Keep hands and glare off the numbers. Never describe the screen's content in your own words; the reference is the content. A product (a bag) is the same idea: front label to camera, steady, shown exactly as [ImageN], no face or limbs unless the script makes it a character.
