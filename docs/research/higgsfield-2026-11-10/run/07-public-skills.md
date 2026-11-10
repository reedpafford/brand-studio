# Higgsfield's public skills (official repository, MIT licence), read 10 Nov
Source: github.com/higgsfield-ai/skills, version 0.14.0, commit 2700040, MIT licence (free to use, copy and change with the notice kept). The two skills that bear on our videos are copied beside this file in `../public-skills/` with the licence. The organisation's other public repositories (cli, cursor-plugin, higgsfield-video-engineer, app-templates) were also read.

**The drama skill (`/drama-ads`, `/microdrama-ads`) is not in any of them.** A search of the organisation's public code for either name finds nothing. It reaches a user only through their signed-in connector.

## What the public skills say that matters to us
**Prompting (`higgsfield-generate/references/prompt-engineering.md`)**
- Concrete and sensory: subject, setting, style; then camera; then light. "Keep it under ~200 tokens. Models distort with very long prompts."
- With a picture attached, describe what changes or moves, never the picture again.
- Say what you want, not what you don't ("tack sharp", not "no blur"): most models take no negative prompt.

**Which model (`model-catalog.md`)**
- Seedance 2.5 is their default for serious motion, several shots in one clip and steady identity: 4 to 30 seconds, reference pictures, video and audio, editing and extension.
- Gemini Omni Flash is "fast multimodal reference-to-video": up to 7 reference pictures, one reference video.

**Narrated videos (`higgsfield-faceless-video`)**
- One idea and its matching picture per stretch of narration; the picture shows what the narrator is saying.
- Vary shot size, angle, place and action so neighbouring shots differ. No over-the-shoulder shot unless the shoulder is in frame.
- No spoken words or text in the background clips; the voice is made separately.
- Narration is made to fit its window and re-written if it doesn't; it is never sped up.
- Check the first finished clip before sending the rest. Remake only what failed or is defective.
- Scripts do the assembly and refuse to deliver if a check fails (timing, length, sound present, file decodes).

**Songs:** the song is made first and is the only sound; pictures follow the lyric and the chorus; "avoid lip-sync"; the first clip is checked before the rest.

**A presenter:** theirs is a cut-out of the person laid over the background clip, one talking clip per stretch. Ours films the host as a take of their own; nothing to take here.

## What we changed because of it
- The narrated plan now asks for neighbouring shots that differ in size and angle (`prompts/narrated_one_pass.md`).
- Everything else above our one-pass build already does: the pilot clip, lean code-built prompts, the voice or song first, pictures-only songs, remakes only for real faults, checks by tools.
