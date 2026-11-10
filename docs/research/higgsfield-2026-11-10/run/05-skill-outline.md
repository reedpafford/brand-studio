# Higgsfield's drama skill: what its opening shows (seen 10 Nov in Reed's own Claude chat, in our words)
Seen through the "Recreate in Claude" route with Higgsfield's connector signed in. Claude's screen shows only the first part of each document it is handed; nothing beyond that was read, and the full text was not pulled.

## How it is packaged
- Two documents are handed to the assistant when a drama is asked for: short "preset instructions" (what to call, what to say, when to stop and wait) and the "workflow" (version 1.0), which is the real rulebook.
- The workflow is one main file that runs as numbered steps 0 to 8, in order. Each step names the reference files it needs, and the assistant must load them when that step starts, "never from memory".
- Each look has its own style file (live action, 3D feature, claymation, doll, crochet). Only the chosen look's file is read.
- It ships with scripts that live in its sandbox: one that checks the written film plan (a `script.json`) mechanically, including a face count; one that assembles the film; one for song timings; one for separating sound stems.
- All downloading, probing, transcribing, mixing and uploading happens in that sandbox, in one folder per film.
- It states its own philosophy up front: every rule is there because a film broke without it, the reason is written beside the rule, and the reason is to be read before a rule is skipped.
- Its tools: story presets and "recipe" and "stage" calls, image and video generation singly and in batches, audio generation in batches, waiting on jobs, listing voices, media upload, a balance check, and asking the person a question.

## What it did before spending (same chat)
- Checked the balance, weighed the resolution against it, and asked one question with the whole plan in it: two characters with ages and temperaments, two places, the invented product, 8 clips for 115 seconds, the total in credits, and a first step of 5 reference sheets for about 13 credits.

## What this confirms for our build
- A written plan that code checks mechanically before anything is paid for (ours: every script line once, in order, by number).
- One file of look rules per style, read only for that style (ours: the style guides).
- Fixed assembly and checking done by scripts, not by the model.
- Rules that carry their reasons, so a director can judge when one doesn't apply.
