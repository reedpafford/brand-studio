# Prompting HeyGen Avatar IV (a talking head from a still and our own voice)

Official sources only, read 2026-11-06. `docs.heygen.com` now redirects to `developers.heygen.com`.
- **[Create]** https://developers.heygen.com/reference/create-video.md (POST /v3/videos, `type: "image"`)
- **[I2V]** https://developers.heygen.com/image-to-video.md · **[A2V]** https://developers.heygen.com/audio-to-video.md
- **[IV]** https://developers.heygen.com/avatar-iv.md · **[Photo]** https://developers.heygen.com/photo-avatar.md
- **[Assets]** https://developers.heygen.com/docs/upload-assets.md · **[Limits]** https://developers.heygen.com/docs/usage-limits.md
- **[Alpha]** https://developers.heygen.com/transparent-background-videos.md · **[Errors]** https://developers.heygen.com/docs/error-codes.md
- **[Help-motion]** https://help.heygen.com/en/articles/10034438-how-to-get-started-with-photo-avatars
- **[Help-IV]** https://help.heygen.com/en/articles/11269603-heygen-avatar-iv-complete-guide
- **[Help-bg]** https://help.heygen.com/en/articles/11371315-how-to-remove-the-background-of-any-avatar

Not found: an API price page (developers.heygen.com/docs/pricing is a 404); an official gesture vocabulary
(HeyGen's GitHub skill file mentions one; not read).

## 1. The request
- `POST /v3/videos`, header `X-Api-Key`; asynchronous: poll `GET /v3/videos/{video_id}` until `completed` or
  `failed` (read `failure_message`), or use `callback_url` [Create].
- Avatar IV is the default engine for a raw image [Create].
- Fields for `type: "image"` (unknown fields are rejected) [Create][I2V]:
  - `image`: url, `asset_id` or base64. URLs must be public, no sign-in.
  - `audio_url` **or** `audio_asset_id`: our own voice to lip-sync. Can't be combined with `script`.
  - `motion_prompt`: "Natural-language prompt controlling avatar body motion." No length limit documented.
  - `expressiveness`: `high`, `medium` or `low`; **default `low`**. "Energy and range of movement."
  - `aspect_ratio`: `16:9`, `9:16`, `4:5`, `5:4`, `1:1`, `auto`; **default `16:9`**. `auto` keeps the photo's shape.
  - `resolution`: `720p` (default) or `1080p`; 4k is not for Avatar IV (a 4k request is upscaled 1080p) [Help-IV].
  - `fit`: `cover` (fills, may crop) or `contain`.
  - `background` (colour or image), `remove_background`, `output_format` `mp4` or `webm` (alpha) [Alpha].
  - `voice_settings` and `brand_glossary_id` affect HeyGen's own speech only, not our audio [Create].
- Upload: `POST /v3/assets` (multipart `file`) returns `asset_id`, which doesn't expire. PNG/JPEG, MP3/WAV,
  32 MB [Assets][Limits]. Uploads are moderated; a blocked file is removed [Assets].

## 2. The photo
- A clear, **front-facing**, well-lit portrait with a **neutral expression** [Photo][I2V].
- Eyes and **mouth and lips clearly visible**; human-like face proportions; no sunglasses, no hat over the
  forehead, no extreme angle [Photo][Help-motion].
- The face should **take up a large part of the picture**; a small character is a common failure [Help-motion].
- Natural posture, hands visible if they'll be used [Help-motion].
- **Too stylised or exaggerated faces give weaker movement and less accurate lip-sync**; beaks, snouts or masks
  over the mouth don't work [Help-motion]. A picture with no detectable face is refused (400) [Create].
- PNG/JPEG under 2K for a URL input [Limits].

## 3. The audio
- MP3 or WAV; public URL or uploaded asset [A2V][Limits]. The video runs as long as the audio.
- Length: Usage Limits says 10 minutes of audio at most; the audio-to-video guide says 30 minutes. Plan for 10 [Limits][A2V].
- No official lip-sync tips for our own audio. Avatar IV reads the voice's tone, rhythm and emotion to drive the
  face and head [Help-IV], so a clean, expressive voice track with no music under it should help (inference).

## 4. Motion prompts and expressiveness
- Official examples: "walk towards the camera slowly" [IV], "nodding gently", "gesturing with hands while
  presenting" with `expressiveness: high` [Photo].
- HeyGen's prompting rules [Help-motion]:
  1. **Clear, direct descriptions** of what moves, not abstract ideas.
  2. **No conversational or command phrasing** ("can you please…", "add snow…"); describe the result.
  3. **Positive phrasing.** "Negative prompts … are not well-supported and may result in unintended effects."
     Write "Fixed camera. The shot stays steady." rather than "No motion."
  4. Keywords to try: mood (radiant, striking…), lighting (warm, natural…), position (centred, off to the side…),
     detail, angle (close-up, headshot, 3/4…).
- Results vary with the photo, pose, lighting and prompt [Help-motion].

## 5. Backgrounds
- Transparency needs `output_format: "webm"` (MP4 has no alpha); it removes the background itself and refuses
  a `background` value in the same request [Alpha].
- The alpha examples use saved avatars; whether `type: "image"` with `webm` works isn't documented: test it [Alpha].
- For filmed avatars HeyGen advises against green screens ("green glare") [Help-bg].

## 6. Failures, limits, safety, price
- Errors: no face (400), `download_failed` (URL not public, wrong extension, corrupt file), `content_policy_violation`,
  `insufficient_credit` (402), `rate_limit_exceeded` (429, `Retry-After`) [Errors].
- 10 jobs at once on pay-as-you-go [Limits].
- Moderation can leave a video "Pending" or "Rejected" [Help-IV].
- Price: "1 minute of Avatar IV video via API should cost about $4 at 1080p" (about $0.067/s) [Help-IV]. Our tests
  were billed about $0.038–0.039/s at 720p (batch-b, th-20s); the catalogue says $0.05/s.

## 7. Where our site differs today (for the builder; nothing changed yet)
| # | Docs say | Site now | Change | Pri |
|---|---|---|---|---|
| 1 | Positive phrasing; negatives work badly | `talker.MOTION` ends "no camera movement"; the director's motion notes aren't checked | Use "The phone is locked off. The shot stays steady."; tell the director to write motion notes positively | should |
| 2 | Default shape 16:9 | We send the video's `aspect_ratio` | Fine; keep sending it | — |
| 3 | Stylised faces lip-sync worse | Dr. Pickle's clay cartoon doctor goes through HeyGen in the corner | Check the doctor's lip-sync by eye in the Dr. Pickle test | test |
| 4 | Face large in frame, neutral, mouth visible | UGC still: chest-up, mouth closed or just parted (matches); presenter still: waist-up on green | Waist-up makes the face smaller: compare chest-up in the Dr. Pickle test | test |
| 5 | `webm` gives alpha without green | Presenter: Nano Banana still on chroma green, then keyed | Try `webm` from a photo once; if it works, no keying and no green spill | nice |
| 6 | Price about $0.067/s at 1080p | Catalogue $0.05/s at 720p | Re-check against the next real bill | should |
