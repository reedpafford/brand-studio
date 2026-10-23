---
name: nano-banana-pe
skill_version: 0.2.0
description: How Story Studio writes prompts for Google's Nano Banana image models (Nano Banana 2.1 and Pro on Replicate), from Google's own guidance and Reed's proven short style. Applied in code by nano_banana_prompt.py to every picture the Nano Banana engine draws.
sources:
  - https://ai.google.dev/gemini-api/docs/nanobanana (Gemini API docs: models, reference limits, editing)
  - https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana (Google Cloud prompting guide)
  - Reed's prompt in Google's Nano Banana, 2026-10-22: "preserving image 3's style, generate the male from image 1 and 2 in the same style - as a charactersheet"
pinned: 2026-10-22
---

# Nano Banana prompting (house skill)

Google publishes no official agent skill for Nano Banana, so this file pins its guidance in our own words, the way
`.agents/skills/sd25-pe` pins Seedance's. `nano_banana_prompt.py` follows it; `tests/test_nano_banana_prompt.py` checks it.

## Purpose
Nano Banana reasons about a prompt before drawing. It does best with one plain sentence that says what each attached
image is for and what to make, followed by the specifics. Reed's blind use (2026-10-22) showed the site's long rule
paragraphs made new pictures, regenerations and edits worse, so the prompt stays short.

## Rules (10)
1. Name every attached image by its number and its job in one sentence: "Preserving image 3's style, generate the man from images 1 and 2".
2. Open with the verb for the job: generate, show, keep / change.
3. Then the subject, then the specifics: the project's own words about this picture (place, action, camera), unchanged.
4. Narrative sentences, not keyword lists; camera words (low angle, close-up, over the shoulder) for framing.
5. Say it positively ("an empty set", "screens show no readable text"), once; no rule piles.
6. Style comes from the house style board image, named by number; no style paragraph.
7. Edits: "Keep image 1 exactly; change only: <the change>." Nothing else is restated.
8. Character consistency: the person's own images go first; the board last. At most 14 images (Google: up to 14 in all; ~4-5 characters held with high fidelity), props dropped before the place before characters.
9. Lettering: one short clause only when a screen or sign is in the picture; the real fomo app capture stays exactly as it is.
10. Aspect ratio and resolution (1K) are request parameters, not prompt text.

## Output contract (how this site applies it)
Images are attached in order: the picture being edited, photos of the person, characters, the place, an opening
composition, props and products, the fomo capture, anything else, the house style board last.
The prompt is one of:
- Character sheet from photos: "Preserving image N's style, generate <name> from images 1 and 2 in the same style, as a character sheet (...): <description>."
- New character: "In image N's style, generate a character sheet (...): <description>."
- Edit or correction: "Keep the character|picture in image 1 exactly; change only: <correction>."
- Storyboard or opening frame: "In image N's style, show <name> (image 1) and <name> (image 2) in <place> (image 3), with <prop> (image 4): <the moment and framing>."
- Place or prop: "In image N's style, generate <description>." A place adds "The place is empty: nobody from the story is in it."
Then, only when needed: a correction ("Change: ..."), the fomo capture line, one lettering clause.

House rules still apply: script words never change, identity and wardrobe facts from the description are kept as
written, the project's style version decides the board, and pictures are never sent with another workspace's data.

## Final checklist
- Every attached image is named by number with its job, in the first sentence.
- Under 80 words of fixed text; the rest is the project's own words.
- No internal ids, seeds or rule names in the prompt.
