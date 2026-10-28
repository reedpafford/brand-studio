---
name: ai-podcast-ads
description: "Activate when the user wants a podcast ad: a realistic podcast-style clip where two hosts discuss the product as a natural conversation."
---

# How to make AI podcast ads

A podcast ad is a short vertical clip that looks like a moment lifted from a real podcast: two hosts at microphones, one telling the other about a problem she solved, the product entering the story as a recommendation between friends.

It wins because it does not read as an ad — the viewer eavesdrops on a conversation instead of being pitched.

The 80% law: realism lives in the script.

Current video models make the faces, voices, and room convincing on their own.

What breaks the illusion is dialogue no human would say.

Spend most of your effort making the conversation sound real; the generation steps below are mechanical by comparison.

## The model: MiniMax H3 Max

MiniMax H3 Max (`minimax-h3-max`; recommendation `video.realisticSpeaker`). Preferred for realistic native speech on a designed start frame, long talking shots, and podcast performances. Alternatives: Gemini Omni Flash 1.1 (`gemini-omni-flash-1.1`): Cheap, fast native speech is preferred; describe the voice explicitly.

The format uses MiniMax H3 Max for its speaker performances.

Plan the workflow around three rules:

1. One reference image per generation. Each clip locks one face, so a two-host conversation is generated one host at a time — never both hosts in one clip.

2. Duration window: 5 seconds minimum, 15 seconds maximum. A single short line undershoots the minimum and comes back padded with dead air; a speaker's full set of lines fits comfortably.

3. Every generation rolls a fresh voice. Voice, tone, and energy are consistent only _within_ one generation.

All three point at the same law: one speaker = one generation (or as few as possible).

## Step 1 — Write the conversation

1. Pull real customer language first. Search Reddit (or reviews) for how real buyers describe the problem this product solves. Collect their phrases, complaints, and objections — the script gets built out of this vocabulary, not marketing copy.

2. Shape it as a discovery arc between two hosts: Host A owns the problem, Host B has already solved it and reveals what worked, the product arrives as a personal recommendation with one concrete proof point (a sleep trial, a number, a detail only an owner would know).

3. Keep it conversational: contractions, interruptions, "oh yeah, we had the exact same problem", questions answered with stories. Read it aloud; anything that sounds like a landing page gets rewritten.

4. Length: 6 to 12 exchanges, 25 to 45 seconds spoken.

## Step 2 — Find a real scene reference

Search Pinterest for a real photo of the podcast setting that matches your audience (a women's podcast in an RV, a garage gym podcast, a kitchen-table setup).

Two rules:

- Match the audience, not the product. The scene sells the "I'm watching a real show" feeling to the target viewer.

- Verify the reference is real footage. Pinterest now carries a lot of AI images; an AI reference compounds into an AI-looking result.

## Step 3 — Generate the host images

Generate one still per host in the reference's environment.

Anchor each face with a real actor reference image — asking the model to invent a person produces generic faces; giving it a reference of a real-looking person produces a host who reads as human.

Keep both hosts in the same environment, seated at microphones, framed like a podcast camera.

## Step 4 — Plan the generations (the core mechanic)

Before generating any video, turn the script into a speaker map:

| Speaker           | Reference image | Voice description                                                               | Lines              |
| ----------------- | --------------- | ------------------------------------------------------------------------------- | ------------------ |
| Host on the LEFT  | her host still  | Warm, friendly female voice, early 40s, American, casual and enthusiastic       | 4 lines, ~35 words |
| Host on the RIGHT | her host still  | Confident, relatable female voice, early 40s, American, warm and conversational | 5 lines, ~70 words |

Then apply the batching rules:

1. Batch all of one speaker's lines into one generation. One generation = one consistent voice across every line in it, and the model pauses naturally between lines — exactly where the edit will cut.

2. Estimate duration with the native-speech estimate in the media generation foundations (words ÷ 3 = seconds), rounded up to the model's next allowed duration. 5–10 words ≈ 2–4s · 15–25 words ≈ 5–9s · 30–40 words ≈ 10–14s.

3. Split a speaker above ~45 words. At three spoken words per second that fills the 15-second ceiling; give them 2–3 generations, each within the window. Never go below one line per split.

4. Copy-paste the exact same voice description into every generation for that speaker — it is what keeps a split speaker's voice matched across their clips.

The speaker map above resolves to 3 generations instead of 9: the left host in one 12s clip, the right host split into two 12s clips.

A normal two-host script lands at 3 to 6 generations total, versus ~30 one-per-line clips that each roll a new voice.

## Step 5 — The prompt structure

Attach the speaker's host still as the start frame — the start frame IS the face lock.

Then use this structure, filled per speaker:

```
Style: Podcast-style video. 4K, rich details, sharp clarity, natural colors, soft lighting, stable picture.

References: the attached start frame is this speaker's host still — the host, wardrobe, and set come from it.

Shots: one continuous shot, no cuts. The host speaks directly to someone off-camera, delivering the lines with natural pauses between them as if listening to responses.

Camera: static, medium close-up locked to match the start frame throughout. No camera movement or angle changes.

Script:

Line 1: "[full dialogue]"
Delivery: [emotion, gesture, expression]

Line 2: "[full dialogue]"
Delivery: [emotion, gesture, expression]

Line 3: "[full dialogue]"
Delivery: [emotion, gesture, expression]

Voice & delivery: [this speaker's voice description, verbatim from the speaker map]. Soft room tone, close-mic'd podcast sound.

Constraints: No captions. No background music.
```

The rules that make it work:

- Plain line labels beat cinematic prompt craft. Shot lists, camera keywords, and style stacks degrade line delivery; "Line 1 / Line 2 / Line 3" plus context and tone is what lands clean reads with clean pauses.

- Full line first, delivery note underneath — never mixed in one block. Mixing dialogue and direction muddies both.

- Static camera, framing locked to the start frame. Describing cuts or camera moves makes the model change angles mid-clip; the edit adds all the cutting later.

- Keep the "natural pauses between them as if listening to responses" phrase. It is what spaces the lines so the edit can cut between them.

## Step 6 — Edit the conversation together

1. Cut each generation into its individual lines and interleave them into the back-and-forth. The pauses between labeled lines make the cuts trivial.

2. Crop uglier for realism. A full clean 9:16 frame reads as AI. Crop to the aspect ratio real podcast clips use (letterboxed, slightly tight) — matching the native format of real clips instantly raises believability.

3. Patch clipped word endings with TTS, not regenerations. Generations sometimes cut the final phoneme ("I thin—" instead of "I think"). Generate just the missing word in a TTS tool (clone the voice or use any similar voice), cut out the phoneme, and layer it under the original audio. Unnoticeable, and it saves a regeneration cycle.

4. Add captions styled like real podcast-clip captions (bold center-bottom, word-by-word), and a hook title card if the clip opens cold.

## What fails → what to do instead

| Fails                                        | Do instead                                                                                         |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| One generation per line                      | Undershoots the 5s minimum, pads dead air, rolls a new voice per clip — batch per speaker (Step 4) |
| "Hard cuts" or shot directions in the prompt | The model changes camera angles mid-clip — static camera line + start-frame lock                   |
| Script and delivery mixed in one block       | Muddier reads — separate Line / Delivery pairs                                                     |
| Timestamps in the prompt                     | Unnecessary — the natural-pauses phrase handles pacing                                             |
| Regenerating a clip for one clipped phoneme  | Patch the missing sound with TTS under the original audio                                          |

## Self-check before delivery

- Read the script cold: would a stranger know it's an ad before the product appears? If no, that's good. If yes, that's bad.

- One voice per host throughout, no mid-conversation voice changes — every generation of a split speaker used the identical voice description.

- Cuts land between lines, never inside a word.

- The product enters as a recommendation inside the story, not a pitch.

## Credit

Made by @davidaistar (Instagram, YouTube), cofounder of starpop.ai.

This skill is optimized for use in Starpop, as it assumes features natively included there, like research, storyboarding, analysis of audio, image and videos, audio slicing, and generation of image, video, audio and music.

However the skill will also work in any agent such as Claude, Claude Code, ChatGPT, Codex etc.
