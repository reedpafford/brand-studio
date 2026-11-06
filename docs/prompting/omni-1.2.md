# Prompting Gemini Omni 1.2 Flash

Official sources only, read 2026-11-06 (the model launched 5 Nov). Every rule says where it comes from.
- **[Rep]** Replicate model page and README: https://replicate.com/google/gemini-omni-1.2-flash
- **[API]** Google's Gemini API docs: https://aistudio.google.com/docs/omni
- **[Price]** Google's pricing page: https://aistudio.google.com/docs/pricing
- **[Guide]** DeepMind's prompt guide: https://deepmind.google/models/gemini-omni/prompt-guide/
- **[Card]** Model card: https://deepmind.google/models/model-cards/gemini-omni-1-2-flash/

Not read yet: Replicate's input schema and price (the `/api` pages render empty without sign-in; fetch
`GET api.replicate.com/v1/models/google/gemini-omni-1.2-flash` with our token, which is free, and save it as
`server/tests/fixtures/replicate/google_gemini-omni-1.2-flash.json`), and the Omni Flash model card PDF.
Our catalogue still has Omni **1.1** (`gemini-omni-1.1`, fixed 10 s, talker-only).

## 1. What it is and what it takes
- Video generation and editing with its own sound (speech, effects, music) [Rep][API].
- **Length:** 3–15 s, set to the second; the `duration` input wins over any length in the prompt [Rep][API].
  1.1 was a fixed 10 s.
- **Shape:** 16:9 or 9:16, 24 fps; Google's default is 16:9, so always send `aspect_ratio` [Rep][API].
- **Resolution:** 360p (drafts), 720p (default), 1080p and 4k (both upscaled from the base render) [Rep][API].
- **Inputs on Replicate** [Rep]: `prompt`, `duration`, `resolution`, `aspect_ratio`, `image` (start frame),
  `last_frame`, `reference_images` (up to 6), `video` (edit a clip up to 15 s).
  - `image`/`last_frame` **can't be combined with** `reference_images`; `video` can't be combined with any image [Rep].
  - First + last frame: 10 s at most [Rep][API].
  - Reference people: **up to 3 images per character, for up to 2 characters** [API].
  - Reference images "keep the subject consistent, not as literal frames" [Rep].
- **Not available:** an audio input (it can't lip-sync to our voice track), a seed, a negative-prompt field, a
  sound on/off switch [Rep][API]. Sound is always made; control it in the prompt words.
- **Edits and extensions** (Google API; check Replicate's schema for which it exposes) [API]:
  - Edit a clip up to 15 s; edits keep the source's length and shape.
  - Extend from the last 10 s of a clip, 3–10 s per turn, 30 s total. Speech can continue when extending a
    clip Omni made, not an uploaded one.
- **Price:** Google's own rate is about $0.023/s at 360p, $0.07/s at 720p, $0.104/s at 1080p, $0.209/s at 4k
  (720p: about $0.70 for 10 s, $1.04 for 15 s); 1.1 was about $0.10/s [Price]. Replicate's price isn't shown
  publicly; read it from the schema call above before quoting. Our catalogue prices 1.1 on Replicate at
  $0.15/s 720p.
- **1.2 vs 1.1** [Rep][API]: up to 15 s and set to the second; holds faces, clothing, product labels and brand
  colours better; "dialogue sounds more natural with better lip sync"; cheaper. From 3 Dec 2026, Google routes
  every 1.1 request to 1.2.

## 2. Prompt structure
- Cover five things: **shot framing and motion, style, lighting, location, action** [Guide][Rep].
- Say the effect you want and let the model fill in the details; it needs less prescription than Veo and
  uses its own world knowledge, so don't over-explain the world [Guide].
- More detail gives more control, but the model works from the overall intention [Guide].
- Plain sentences. **Don't use control tags** such as `<FIRST_FRAME>`, `<LAST_FRAME>`, `<IMAGE_REF_0>` or
  `<VIDEO_REF_0>`; describe each input's role in words [API].

## 3. Camera and cuts
- Camera words it reads [Guide][Rep]: "one continuous shot" / "oner", "static", "locked off", "fixed angle",
  "push in", "punch in", "pan left", "dolly zoom", "orbit", "FPV drone"; camera kinds such as "natural
  smartphone zoom", "film camera", "webcam style".
- **It makes several shots with a story by default.** For one shot, say "a single continuous shot" or "no
  scene cuts" [API][Guide].
- Timing: natural language ("after 3 seconds, a woman enters") or timecodes `[0-5s] … [5-10s] …` for cuts
  and quick sequences [API].

## 4. Dialogue and voices
- Put each spoken line in quotes and **name who says it**: `The man in the blue sweater replies: "Did your
  father go out on the boat too?"` [Rep][Guide].
- Write "no dialogue" to keep anyone from speaking [Rep].
- The voice is Omni's own. There's **no voice input and no official way to keep one voice across separate
  clips** [API]. The only continuity tools are extending or editing the same generated clip [API].
  (Our 3 Nov test on 1.1, `.context/tests/batch-b` q2: faces matched the references and each line came from
  the right mouth; about 25 words / 3 shots per 10 s clip.)
- Editing a person's speech in an existing clip is restricted [Card].
- Only English is fully evaluated [API].

## 5. Sound and music
- Describe the place's sound and any music; "no music", "no dialogue" and short negatives like "No extra
  sound effects" work [Rep][API].
- Without direction it picks fitting audio itself, so say what you want, especially for music [API].

## 6. References: people, products, style
- Refer to references by their order and role, in words: "the woman from the first image … holding the
  tumbler from the second image" [Rep].
- Up to 6 images; at most 3 per person and 2 people [API]. Real photos or Nano Banana images both work [Rep].
- High-resolution images and specific motion; "make it move" gives weak results [API].
- A drawing can guide movement only: "turn this into realistic footage, using the drawing only as a guide
  for movement, do not show the drawing in the final video" [API].
- Storyboard sheet: "Follow the story exactly in order starting top left. Entire story in 10 seconds." [Guide].

## 7. Styles (realistic and cartoon)
- It does photoreal and a wide range of styles: anime, claymation, watercolour, crayon, graphite sketch with
  "line boiling", 3D translucent glass, risograph, flat vector explainer [Guide][Card].
- The guide's style question: "Realistic, or cinematic? Grounded, or majestic?" [Guide].
- Nothing official compares it with Seedance on any style; that needs a test.

## 8. Text in the picture
- On-screen text renders legibly; state exactly what a sign, label or screen says, and its type, placement
  and animation [Guide][API]. (Our rule 32: no captions; in-world text stated exactly.)

## 9. Edits, extensions, first/last frame
- Edits: short and surgical; wordy edit prompts cause unintended changes. Say what changes **and** what
  stays: "Keep the people, their dialogue and the camera move the same." [Rep][API].
- Extend: "Extend this video" / "The scene continues: …"; say whether it continues or cuts; re-mention or
  re-attach anything from more than 10 s back [API].
- First/last frame: describe the first frame, the move between, and exactly what the last frame shows [Guide].

## 10. Workflow, failures and refusals
- Draft at 360p, then re-run the prompt you like at 720p [Rep]. There's no seed, so a draft previews the
  prompt, not the exact take (inference).
- Common failures: unwanted cuts (the multi-shot default), unintended changes from long edit prompts, vague
  motion, control tags [API].
- Safety: prompts, inputs and outputs are filtered; refusals "fail with a content error" [Rep]. Images of
  certain recognisable people aren't supported; images of minors can't be uploaded or edited in the EEA,
  Switzerland and the UK [API]. Every output carries SynthID [Rep].

## 11. Where our site differs today (for the builder; nothing changed yet)
| # | Docs say | Site now | Change | Pri |
|---|---|---|---|---|
| 1 | Model is `google/gemini-omni-1.2-flash`, 3–15 s | Catalogue has 1.1, `fixed_seconds: 10` | Add 1.2 with its duration range and real Replicate price (schema call) | must |
| 2 | Name references in words by order; no tags | Omni gets the Seedance clip prompt (`[Image1] is the first frame…`) plus `SILENT` (`model_map.fit`) | An Omni prompt shape of its own: "the woman in the first image" | must |
| 3 | Start frame and references can't be combined | The prompt calls a reference "the first frame" while only `reference_images` are sent | Pick one per clip: start frame (`image`) **or** references | must |
| 4 | At most 3 images a person, 2 people | `reference_images[: max_reference_images]` cuts the list without regard to people | Cap per person and per clip; a shot with 3+ cast needs another plan (wide, or Seedance) | must |
| 5 | Sound always made; say "no music" / "no dialogue" in words | Seedance's audio line ("No music, background music, BGM…") | Short Omni audio line; quoted speech with the speaker named | should |
| 6 | Multi-shot by default | Seedance shot list (fine), but single-shot clips don't say "one continuous shot" | Add it when a clip is one shot | should |
| 7 | Edit with "keep everything else the same" | No edit path | A cheap continuity fix (wardrobe, a prop) once built | nice |
| 8 | No voice input or cross-clip voice control | — | Movie: write each character's voice the same way in every clip; test whether it holds (Movie spec test 2) | must for Movie |

Reed's 6 Nov plan (in the style-verification session): Omni 1.2 for B-roll overlay clips, Movie, and anything
realistic, and for cartoon or Skeleton looks if it beats Seedance. This replaces "Omni never for B-roll"
(4 Nov) once built. The code still allows Omni only for a talker's silent shot (`model_map.py`).
