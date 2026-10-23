# Prompting Seedance 2.5

Official sources only, read 2026-10-23. Every rule links to where it comes from.
- **[Guide]**: BytePlus ModelArk, *Seedance 2.5 prompt guide*.
- **[Skill]**: the official `sd25-pe` prompt skill v0.1.1, linked from the guide's "Get the skill" section ([index][skill-index], [archive][skill]; sha256 `c9c765aa…7cba` matches the index). We read it as text. We never run its install or self-update commands.
- **[Replicate]**: the model page and the input schema we actually call ([README][rep], [schema][rep-api]; same as `GET api.replicate.com/v1/models/bytedance/seedance-2.5` and our snapshot `server/tests/fixtures/replicate/bytedance_seedance-2.5.json`).

How we call it: through Replicate, in reference mode (reference images, videos and audio). We never send a first frame. Replicate doesn't allow first or last frames together with references ([schema][rep-api]: `image` "cannot be combined with reference images, videos, or audios").

## 1. Prompt structure
Treat the model as "a visual content producer" and write a structured prompt ([Guide][g]). The guide's basic shape, in order ([Guide § Basic prompting techniques][g]):
1. **Asset references.** Say what each image, video or audio file is, by its upload number, and what it's for (subject, voice, action, scene).
2. **One-sentence summary.** Subject + location + event + genre/style + camera movement.
3. **Detailed plot.** A shot list or a timeline. Use timestamps or "Shot N", and give each segment's visuals, camera, action, dialogue and sound.
4. **Additional notes.** What must stay the same throughout: angle, environment, sound, atmosphere.

Replicate's description of the `prompt` input: Seedance 2.5 "works best with detailed, structured 'production brief' style prompts" ([schema][rep-api]). Its README says to be specific about camera movement, lighting, mood and actions ([Replicate][rep]).

## 2. Referencing images, videos and audio
- On Replicate the syntax is `[Image1]`, `[Video1]`, `[Audio1]` ([schema][rep-api]; [README][rep]: "The character from [Image1] performs the dance from [Video1]"). The numbers follow upload order ([Guide § Reference tasks][g]).
- Bind every asset in the text. Don't rely on a name written on the picture: a character sheet labelled "John" plus a prompt that says only "John is at school" can confuse or duplicate the character ([Guide § Reference tasks][g]).
- With several subjects, give one mapping per line ([Guide][g]). Examples from the guide: "Image 1 depicts the protagonist John and uses the voice timbre from Audio 1", and "Images 1-2 are Character 1 and correspond to Audio 1".
- Say which part of an asset to use ("Refer to Image 1 for lighting and filters"). If the reference is accurate enough, just point to it and don't re-describe it ([Guide][g]).
- **Upload characters in the order they first appear.** Mismatched characters is a known failure, and this is the official fix ([Guide § FAQ: Incorrect character-to-reference mapping][g]).
- To make a reference image the opening frame, write it in the text: "Image 1 is the first frame." In reference mode this does not lock the aspect ratio, and the result will be close to the image but not exact ([Guide § First and last frames][g]).
- Audio references need at least one image or video with them ([schema][rep-api]).

## 3. Dialogue and audio
- Put spoken words in double quotes: `The man stopped and said: "Remember this moment."` The model makes matching lip movement and voice ([Replicate][rep]; [schema][rep-api] `generate_audio`). The skill uses `{}` for dialogue ([Skill § Sound, Dialogue, and Text][skill]). We call through Replicate, so we follow Replicate's quotes.
- When lines need different deliveries, use `Name (emotion): "line"`. Don't repeat the line's words afterwards, and don't attach tone or action notes to single words: both can make the model add subtitles ([Guide § FAQ: Subtitles generated][g]).
- In multi-speaker scenes, bind speaker and audio for each segment, and say the listeners keep their mouths naturally closed ([Skill § Sound, Dialogue, and Text][skill]).
- Language: label each speaker's line. If English might come out as Chinese, write "Use English." Don't add an accent nobody asked for ([Skill][skill]). The model speaks more than 10 languages ([Guide § Overall introduction][g]).
- **No music.** Negative audio control works: "No BGM; generate only environmental sounds and action sounds" ([Guide § Negative control][g]). The model can still turn sound effects into music. The official fix is to say the soundtrack is character voices only, and to list the banned words: music, background music, BGM, score, instrumental, melody, synth effects, ambient pad. Put that audio rule at both the start and the end of the prompt ([Guide § FAQ: Background music generated despite "no BGM"][g]). The guide's own worked example also bans drone, swelling tone, crescendo, musical build and stinger ([Guide § Prompt examples][g]).
- Water, waves or echo in the prompt can cause bubbling or whistling artifacts. Leave them out unless needed ([Guide § FAQ: Ripple-like audio artifacts][g]).

## 4. Camera language
- Write standard terms directly ([Guide § Camera language][g]):
  - shot size: extreme wide, wide, medium, medium close-up, close-up;
  - moves: push in, pull out, pan, track, follow, orbit, dive, pull back, tilt up, handheld shake;
  - angles: low angle, overhead, first-person;
  - techniques: one-shot/long take, dolly zoom, aerial, FPV, bullet time, speed ramp.
- Niche terms: write the term plus what you see. Example: "Rack focus: the focus shifts smoothly; the trees … become blurred, while the character … gradually becomes clear" ([Guide][g]).
- Transitions: give the timing and the method ("At the 5-second mark … left wipe combined with a natural dissolve") ([Guide][g]).
- With several people in frame, name the subject the camera follows and where the move starts and ends ([Skill § Professional Cinematography][skill]).
- Actions: describe them in general terms, and give specific detail only to a few memorable ones. Don't repeat actions. Expressions: use descriptive sentences and few idioms ([Guide § Action and expression descriptions][g]).

## 5. Timing and multi-shot
- One prompt makes up to 30 s, with cuts inside it ([Replicate][rep]; [Guide][g]). Duration 4–30 s, or `-1` to let the model choose ([schema][rep-api]).
- 2.5 supports **integer-second timestamps**. 2.0 only follows shot numbers ([Guide § Differences from Seedance 2.0][g]).
- **The basic unit is 1 second.** Segments must be continuous with no gaps: write "0-3 seconds…3-7 seconds…", not "0-3s… 5-6s…". Too little content in a segment lets the model improvise. Too much gives "excessive cuts" or drops plot. Don't time very fast repeated actions ("shake your head three times per second") ([Guide § Timestamps][g]).
- Point and relative timing also work: "At the 2-second mark…", "After 3 seconds…" ([Guide][g]).
- Don't claim half-second precision. Timestamps are event budgets, not frame-exact edit points ([Skill § Long Videos and Time Segments][skill]).
- **Our A/B (2026-10-23, one clip each; see [FIT.md](FIT.md#ab-result-2026-10-23-206-logged-by-the-producer)):** decimal shot times were followed within about 0.3–0.7 s. Rounding to whole seconds and grouping two quick cuts into one second lost a shot and finished the dialogue early. We keep decimal shot times.

## 6. Limits
| | Limit | Source |
|---|---|---|
| Length | 4–30 s (or -1 = model decides) | [schema][rep-api] |
| Reference images | up to 30, each ≤ 4K | [schema][rep-api], [Guide][g] |
| Reference videos | up to 10, **combined** ≤ 30 s | [schema][rep-api] |
| Reference audio | up to 10, **combined** ≤ 30 s; needs an image or video too | [schema][rep-api] |
| All references | ≤ 50 per request | [Guide][g] |
| Works best with | 1–8 subjects in images (9–12 may be unstable); 1–5 subjects in audio/video | [Guide § Reference asset input recommendations][g] |
| Replicate resolutions | 480p, 720p | [schema][rep-api] |
| Usage metrics | Replicate reported none for this model in our A/B; cost = requested seconds × price, marked estimated | FIT.md A/B result |
| Aspect | 16:9, 4:3, 1:1, 3:4, 9:16, 21:9, adaptive | [schema][rep-api] |
| Storyboard grid image | ≤ 15 panels, line art, little text; it isn't followed frame by frame | [Guide § Multi-panel storyboards][g] |

## 7. Known failure modes
From the official FAQ ([Guide § FAQ][g]).
- **Subtitles despite "no subtitles"**: this is reduced in 2.5 but still happens. Avoid the dialogue patterns in §3, and don't use reference videos that have subtitles.
- **Wrong character on a reference**: upload in order of first appearance (see §2).
- **Misspelled text**: "E" can come out as "A" or "I". Give exact text as a reference image instead of typing it.
- **Glowing eyes** from strong emotion words ("fanatical", "extremely shocked"): use calmer words ("amazed"). Don't describe emotion as an eye effect. If it still happens, add "normal human eyes; no glowing eyes".
- **Fingerprint-like textures** in grass or foliage when the reference image is high resolution: resize references so they're **no larger than the output video resolution**.
- **HTTP 400 on some JPGs** (non-standard chroma subsampling): re-encode as standard JPEG or PNG.
- **Unstable results on complex tasks**: split the task into simpler passes.
- **Style drift**: 2.5 and 2.0 look clearly different from the same prompt. Don't mix them in one video.

## 8. What NOT to put in the prompt
- **Output settings**: aspect ratio, total duration, resolution, frame rate, the sound switch. These go in the API parameters ([Skill § Non-Negotiable Principles 7][skill]).
- **Generic quality or "stability packs"**, or constraints nobody asked for ([Skill, principle 8][skill]).
- **Internal ids, analysis notes, reasons for changes, keys** ([Skill, principle 6][skill]).
- **Negative visual lists.** Describe what you want instead. Negatives are only supported for subtitles and audio ([Guide § Basic prompting techniques][g]).
- **Names written on reference pictures as the only mapping** (see §2).
- **Re-describing a reference** that is already accurate ([Guide][g]).

[g]: https://docs.byteplus.com/en/docs/modelark/seedance-2-5-prompt-guide
[skill]: https://arkdocs-en.tos-ap-southeast-1.volces.com/skills/artifacts/video-generation/sd25-pe/0.1.1/sd25-pe-0.1.1.zip
[skill-index]: https://arkdocs-en.tos-ap-southeast-1.volces.com/skills/.well-known/agent-skills/index.json
[rep]: https://replicate.com/bytedance/seedance-2.5
[rep-api]: https://replicate.com/bytedance/seedance-2.5/api/schema
