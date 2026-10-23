# TEZU (tezu.ai) — Product Map for Brand Studio

Explored 2026-10-23, logged out and logged in (Reed's test account, 20 "early-access test credits"). Desktop 1440x900 and phone 390x844.
Screenshots: `shots/` (same folder as this file). Raw page dumps (text, controls, network): `dumps/*.txt`. Downloaded JS/CSS: `bundles/`.

**Nothing was spent.** No Generate, buy, plan-change, delete or settings-save button was pressed. Generation is switched off site-wide anyway ("Generation opens shortly", `generationEnabled: false`). Two side effects to know about:
1. Five solid-colour test PNGs were uploaded as video references. Upload runs as soon as a file is picked, and the files land in the account's private `creations` storage bucket. They are not jobs and do not show in any library.
2. The free Prompt Assistant "Enhance prompt" was run about 8 times. It is labelled "0 generation credits" and it returned the deterministic "TEZU framework" fallback, not an AI model's output.

---

## 0. TL;DR

- TEZU is a single-person, pre-launch AI creative studio. The operator is Nathan Caulfield, BC, Canada (Instagram @nateassets). It has three core tools: **Character Creator → Image Generator → Video Generator**. Around them sit Templates, Viral Cartoons (Worlds), AI Influencer, the My Characters / My Creations libraries, Rewards, Pricing and Settings.
- Core pitch: "One character. Any scene. Make a character. Put them in a scene. Bring them to life." A character sheet becomes a reference for images and videos ("Create a Scene", "Bring to Video").
- Stack: built with **Lovable** (Lovable Cloud = Supabase + TanStack Start server functions, Lovable analytics `__l5e`). Payments are Stripe Link (seller of record). **All generation is routed through "ArgoLink" (HAPPYTOKEN TECHNOLOGY LIMITED, Hong Kong)**, a model aggregator/router, per the privacy policy. No replicate/fal/openrouter/byteplus strings appear in the client.
- Pricing: 1 credit ≈ US$0.0103 (`credits ≈ usd × 96.774`). Video is billed per second per resolution tier. Images cost 2–4 credits each and a character sheet costs 4.

---

## 1. Site map / routes

| Route | Auth | Purpose | Screenshots |
|---|---|---|---|
| `/` | public | Marketing home | out-home(-full), out-home-hero-{character,image,video}, m-out-home |
| `/pricing` (+ `#agency`, `#pricing-details`) | public | Plans, plan finder, compare table, FAQ | out-pricing(-full), out-pricing-expanded-full, out-pricing-annual, m-out-pricing |
| `/about` | public | About / who it's for | out-about |
| `/hire` (+ `#inquiry`) | public | Done-for-you studio quote form | out-hire |
| `/auth`, `/auth?mode=signup`, `/auth?redirect=…` | public | Log in / sign up | out-auth, out-signup |
| `/reset-password` | public | "Set a new password" | in-reset-password |
| `/early-access` | public | Email waitlist "Join Early Access" | in-early-access |
| `/living-worlds` | public | Landing page for Viral Cartoons / Living Worlds | in-living-worlds |
| `/terms`, `/privacy`, `/cookies`, `/refunds`, `/policy-review` | public | Legal | out-terms, out-privacy, out-cookies, in-refunds, in-policy-review |
| `/create/character` | login | Character Studio | character-*, in-create-character |
| `/create/image` | login | Image Studio (post-login landing page) | image-*, in-create-image |
| `/create/video` | login | Video Studio | video-*, pa-*, in-create-video |
| `/templates`, `/templates/$slug` | login | Template gallery and template detail | in-templates, template-* |
| `/create/worlds` | login | "Viral Cartoons" world image generator (Soon) | in-worlds |
| `/ai-influencer` | login | AI Influencer designer (New, no generation yet) | in-ai-influencer |
| `/characters` | login | My Characters library | in-characters, characters-* |
| `/creations` | login | My Creations library | in-creations, creations-characters-tab |
| `/rewards` | login | Daily spin / streak / mini-game (Plus+) | rewards |
| `/settings` | login | Profile, credits, billing, ledger | in-settings |
| `/dashboard` | login | Redirects to `/create/image` | in-dashboard |
| `/admin`, `/analytics`, `/worlds-admin`, `/rewards-admin`, `/agency-review` | admin | "Administrator access required" | in-admin, in-analytics |
| anything else | — | 404 "Page not found · This scene doesn't exist." | out-404 |

Logged-out visits to `/create/*` and `/templates` redirect to `/auth?redirect=…`.

### Navigation
- **Logged-out top bar:** logo · Character Creator [New] · Image Generator · Video Generator · Explore · Templates … right side: Pricing (badge "30% OFF") · Log in · **Start Creating** (purple CTA).
- **Logged-in top bar:** logo · Character Creator [New] · Image Generator · Video Generator · Templates · Viral Cartoons [Soon] · AI Influencer [New] · My Characters · (My Creations) … right side: **Rewards [PLUS]** (gift icon, outlined purple) · Pricing [30% OFF] · **credit pill** "◆ 20 credits" (links to /settings) · avatar initial "W".
- **Account menu** (avatar): name, email, Pricing, Rewards [PLUS], Settings, Sign out (account-menu.png).
- **Mobile (390px):** fixed 65px header with logo, credit pill, avatar and hamburger "Open menu". The menu is a full-screen sheet (m-in-nav-open.png) laid out as: "CREATE" eyebrow → Character Creator [New], Image Generator, Video Generator / divider / Templates, Viral Cartoons [Soon], AI Influencer [New], My Characters, My Creations / divider / Pricing, Rewards, Settings (with icons) / pill button "Open Studio". Large 30px bold type.
- **Footer:** tagline "Characters, images and cinematic video — in one creative studio." Columns: PRODUCT (Character Creator, Image Generator, Video Generator, Explore), ACCOUNT (Pricing, Log in, Sign up, Open Studio), COMPANY (About, Hire TEZU, FAQ, Contact), LEGAL (Privacy, Terms, Cookies). © 2026 TEZU.

---

## 2. Marketing home `/` (out-home-full.png)

Sections in order:
1. **Hero:** large chrome/3D "TEZU" wordmark over a wall of tilted, autoplaying vertical video cards (3D cartoon "Pixar-like" creator content). H1 "Create beyond **imagination.**" (second line in a purple gradient). Sub: "Turn your ideas into cinematic video, images and audio, powered by AI."
   - Segmented tabs **Character / Image / Video**. Each swaps the placeholder: "Describe your character…" / "Describe the image you want to create…" / "Describe the scene you want to bring to life…". The pill input has an inline "Start Creating →" button, which sends you to signup.
   - Model logo strip: Seedance · MiniMax · Wan · Nano Banana · GPT Image · Grok. These deep-link to `/create/video?model=seedance-2.5`, `?model=minimax-h3`, `?model=wan-3`, `/create/image?model=nano-banana-2.1`, `?model=gpt-image-2.5`, `?model=grok-imagine`.
   - Below the strip: "Sign up free ↗".
2. **"TEZU VIDEO STUDIO / TEZU IN MOTION."** cinematic preview with a "Pause cinematic preview" control → "Create a video".
3. **"Start creating — Choose what you want to make."** Three cards: Character Creator "Create character", Image Generator "Create image", Video Generator "Create video".
4. **"One character. Any scene."** Boy/Girl toggle, a 01 Character → 02 Image → 03 Video stepper, and the disclaimer "Results can vary between scenes. Using saved characters in Image and Video Studio is rolling out during launch testing." → "Create your own character".
5. **Explore creations** ("Examples made by the TEZU team"): a horizontal carousel of clips titled after creators ("Video for Ishowspeed", "Kai Cenat", "Mr. Beast", "Drake's Girl", "Viral Detailing Video", "Supercar Streets"…), with prev/next arrows.
6. **Templates:** "Copy a clip, swap in your characters, generate the full sequence." Cards carry a people-count badge (1 PERSON / 2 PEOPLE / 3 PEOPLE); clicking opens a preview modal with a "1 / 9" pager. "View all" → /templates.
7. **Choose your plan:** pricing cards (same as /pricing).
8. **FAQ** accordion, single-open (answers in §10).
9. **Closing CTA:** "Start with one idea. Make a character, an image or a scene — then keep going." Start Creating / Explore Creations.

---

## 3. Video Studio `/create/video` (in-create-video.png, mobile m-in-create-video.png)

Page title "Video Studio · tezu".

### Layout
A two-pane "studio" layout shared by Image and Character Studio:
- **Left panel** (~300px card): a looping preview-video banner tagged "TEZU VIDEO GENERATION", then a stack of labelled fields. A **sticky footer** holds the big Generate button with a cost chip and a status line under it.
- **Right workspace** (large card): tabs **History | Gallery (count badge)**, link "My Creations" at top right, an info banner, and an empty state.
- **Mobile:** single column with the Generate footer fixed at the bottom of the viewport. History sits below the form.

### Controls, top to bottom (exact labels)
1. **Model**: trigger button showing logo, name and one-line description (e.g. "Seedance 2.5 / References · 4–30s · up to 1080p"). It opens a popover (video-model-picker.png) containing:
   - Search box "Search models".
   - Tag chips: All · Fast · Cinematic · High Quality · Budget.
   - Provider chips: Kling · ByteDance · Google · OpenAI · Midjourney · Vidu · MiniMax · Wan.
   - Section "CHOOSE MODEL" lists the available models. The "Recommended" badge sits on Seedance 2.5 and a check marks the active one.
   - Section "COMING SOON" lists greyed rows with a "Soon" badge. They are hidden when a tag filter is active.
   - Empty filter result: "No available models match."
2. **Prompt**: counter "0 / 2,000", textarea placeholder "Describe your scene, movement, and camera action...", helper "Who's in it, what happens, how the camera moves." Minimum 8 characters, otherwise the button reason reads "Describe your scene to continue".
3. **Prompt Assistant** button (sparkle icon). After a suggestion is applied, an "Undo enhancement" ghost button appears next to it. See §3.4.
4. **Reference images · Optional**: dropzone "Drop images or click to upload / PNG, JPG or WebP · up to 20 MB each". After upload it becomes thumbnails with "Remove <file>" buttons and a "+" "Add image" tile. Then "Use saved character" (popover grid of saved characters; empty state "No saved characters yet. Create one in Character Creator."), a counter "0/4", and the hint: "Mention them in your scene, e.g. "the man from @Image 1". References guide the look — exact likeness isn't guaranteed." Typing "@" opens no autocomplete. Uploads past 4 are silently dropped.
5. **Aspect ratio**: buttons with drawn ratio rectangles: 9:16 · 1:1 · 16:9 · 4:3 · 3:4 · 21:9. Wan 3.0 Prime offers only 9:16, 1:1 and 16:9. Default is 9:16.
6. **Duration**: range slider, with "min s" on the left, the current value in the centre and "max s" on the right. Step is 1s. Default is max(4, min).
7. **Resolution**: segmented buttons, model-specific. Default is the lowest tier.
8. Note: "Videos include a generated soundtrack. Rendering takes a few minutes — you can leave this page and come back." There is no audio toggle in the UI, although the catalogue has `audio: 'switch' | 'always'`.
9. **Generate Video [◆ cost]**. aria-label "Generate Video — costs N credits". Tooltip format "Total cost: N credits". Disabled-reason line under the button, in priority order:
   - "Loading your reference"
   - "Resolve the unavailable reference before generating"
   - "Video generation opens after our final checks" (when generation is globally off)
   - "Not enough credits"
   - "A video is still rendering" (one job at a time)
   - "Describe your scene to continue"

Switching models clamps the duration, resolution, aspect and reference count to the new model's limits.

**URL params:** `?model=<id>&prompt=<text>&character=<characterId>&ref=<jobId>`. `character` preloads a saved character as a reference. `ref` preloads a finished image job, and errors with "This image reference is unavailable…" if the job is a video or not completed.

### 3.1 Video models (from the UI and the `models-*.js` catalogue)

Available models (ids are also sent as `providerModel`):

| Model (id) | Provider | Tags | Duration | Resolutions | Aspects | Max refs | Audio |
|---|---|---|---|---|---|---|---|
| Seedance 2.5 (`seedance-2.5`), default, Recommended | ByteDance | Cinematic, High Quality | 4–30s | 480p, 720p, 1080p | 6 | 4 | switch |
| Seedance 2.0 (`seedance-2.0`) | ByteDance | High Quality | 4–15s | 480p, 720p, 1080p, 4K | 6 | 4 | switch |
| Seedance 2.0 Fast (`seedance-2.0-fast`) | ByteDance | Fast, Budget | 4–15s | 480p, 720p | 6 | 4 | switch |
| MiniMax H3 (`minimax-h3`) | MiniMax | Budget | 4–15s | 768p, 2K | 6 | 4 | always |
| Wan 3.0 (`wan-3`) | Wan | Budget | 2–30s | 480p, 720p, 1080p | 6 | 4 | switch |
| Wan 3.0 Prime (`wan-3-prime`) | Wan | Fast | 4–30s | 480p, 720p, 1080p | 9:16, 1:1, 16:9 | 4 | always |

Coming soon (name / tagline): Kling O3 "Start/end frames · up to 7 refs"; Kling 3.0 "Optional start + end frames"; Kling 3.0 4K "Native 4K · start/end"; Kling 2.6 "Start frame · 5s or 10s"; Seedance 1.5 Pro "Start frame · 480p–1080p"; Gemini Omni Flash "T2V · I2V · refs"; Google Veo 3.1 "Start/end · up to 4K"; Google Veo 3.1 Lite "Start frame · 720p/1080p"; OpenAI Sora 2 "Start frame · 4–20s"; Midjourney Video "I2V · start frame"; Vidu Q3 "Start frame · up to 1080p"; Wan 2.6 "T2V or refs · 5 max"; Wan 2.2 I2V "480p · 5s · 1 image".

**Not present today:** first/last-frame slots, reference video or audio uploads, negative prompt, seed, camera-control UI, variations count, or an explicit audio switch. All available models use the same "Reference images (max 4)" slot. Start/end frames appear only in the taglines of the coming-soon models.

### 3.2 Video credit costs

Formula in the client (`models-*.js`):
```
credits = tier.credits_per_second × (duration + ceil(referenceVideoSeconds))
usd     = tier.usd_per_second × (same)
(Seedance 2.5 480p has verifiedTotal: credits = min(9×secs, ceil(usd×96.774)) → 8.5/s effective)
```
Aspect ratio and reference-image count do not change the price (verified in the UI). The `referenceVideoSeconds` term is groundwork for templates/reference video.

Per-second rates (credits/s → provider USD/s, as embedded in the client):

| Model | 480p | 720p | 768p | 1080p | 2K | 4K |
|---|---|---|---|---|---|---|
| Seedance 2.5 | 8.5 ($0.0874) | 24 ($0.196) | – | 59 ($0.483) | – | – |
| Seedance 2.0 | 8 ($0.0598) | 16 ($0.129) | – | 39 ($0.318) | – | 80 ($0.661) |
| Seedance 2.0 Fast | 6 ($0.0478) | 13 ($0.103) | – | – | – | – |
| MiniMax H3 | – | – | 5 ($0.039) | – | 8 ($0.064) | – |
| Wan 3.0 | 5 ($0.038) | 10 ($0.075) | – | 19 ($0.15) | – | – |
| Wan 3.0 Prime | 7 ($0.051) | 14 ($0.11) | – | 26 ($0.21) | – | – |

Sample totals read off the Generate button:
- Seedance 2.5: 4s/480p = 34; 5s = 43; 10s = 85; 15s = 127; 30s/480p = 254; 4s/720p = 96; 30s/720p = 720; 4s/1080p = 236; 30s/1080p = 1,770.
- Seedance 2.0: 4s/480p = 32; 15s/4K = 1,200.
- Seedance 2.0 Fast: 4s/480p = 24; 15s/720p = 195.
- MiniMax H3: 4s/768p = 20; 15s/2K = 120.
- Wan 3.0: 2s/480p = 10; 30s/1080p = 570.
- Wan 3.0 Prime: 4s/480p = 28; 30s/1080p = 780.

The full grid for every second is in `dumps/video-models.json`. Note the margin: Seedance 2.5 at 720p is 24 credits ≈ $0.248 against a $0.196 provider cost.

### 3.3 Job submission, queue, progress, results
- Submit payload (server function): `{prompt, model, duration, resolution, aspect, characterIds?, jobIds?, uploadPaths?, idempotencyKey: crypto.randomUUID()}`. The image version adds `clickedAt`.
- The button shows a busy spinner while submitting.
- Errors appear as a banner "That didn't work. <message>" with a dismiss button. Network failure: "We couldn't reach TEZU. Check your connection and try again. If credits were used, they'll be returned automatically."
- Jobs live in the `generation_jobs` table, read by the client via Supabase REST with RLS. Fields: `id, kind (character|image|video), status (pending|processing|completed|failed|expired), prompt, style, settings{model,duration,resolution,aspect,…}, result_path, error_message, created_at, credits_charged, credits_refunded`.
- Progress: the client polls a server function `{jobId}` every **12s** and gets a `progress` percentage. Character jobs refetch every 5s while pending.
- **Progress UI ("gen-orbit"):** animated rings and particles around the logo. Status text: "Queued" (pending) → "Rendering your video · 42%" (processing) → "Finalizing" (≥100%). Image jobs show "Creating your image". On completion the card plays a "gen-reveal" animation (1.4s).
- **History tab:**
  - Toolbar: "Size" slider (70–200%, saved in localStorage `tezu:history:size`); List/Grid toggle (`tezu:history:layout`); "Filters" popover with Status (All / Generating / Completed / Failed), Model (All models / each model), Sort (Newest first / Oldest first) and "Reset filters". The Filters button carries a count badge when filters are active.
  - List card: model chip, status badge, date ("October 23, 2026"), prompt clamped to 3 lines with "Read more / Show less", chips (duration, resolution, aspect, "N credits"), and buttons **Download**, **Reuse prompt**, ⋯ menu (Delete). Failed cards show "Try this prompt again".
  - Failure states: "Failed · refunded", "Timed out · refunded", "Your credits were returned." / "Check your credit history for the refund status."
  - Delete confirm: "Delete this creation? This permanently removes the video and its file. This can't be undone." Buttons: Keep it / Delete.
  - Empty state: "Your next scene starts here. Describe a scene or add a reference to begin. [✦ Start describing]" (focuses the prompt). Filtered empty: "No creations match these filters. [Reset filters]".
- **Gallery tab:** grid of finished videos (muted hover-play). Empty: "Finished videos will collect here."
- **Lightbox:** full-size player (controls, autoplay) with the prompt as caption, plus Download and Reuse prompt.
- "Reuse prompt" restores the prompt, model, duration, resolution and aspect into the form.
- Download filename: `tezu-video-<id8>.mp4` (images `.jpg`).
- **Missing:** share links, public gallery, variations, extend/continue, stitching shots, folders/projects.

### 3.4 Prompt Assistant (video-prompt-assistant-open.png, pa-*.png)

A modal titled "TEZU · <model name> / **Prompt Assistant** / 0 generation credits · 4s video" ("· Image" in Image Studio).

**Fields:**
- **Your idea**: textarea, placeholder "A simple idea, in your own words…", 3–1,200 characters. It is prefilled from the main prompt.
- **Creative direction**: chips Cinematic (default) · Realistic · Animated 3D · Funny · Product Commercial.
- **Multi-shot storyboard**: checkbox, video only. When on, a "Shots" select appears with 2 / 3 (default) / 4.
- **Advanced direction**: a `<details>` element containing Framing (Auto / Wide / Medium / Close-up) and Camera (Auto / Static / Tracking / Slow push-in; video only).
- **Enhance prompt** button. It reads "Enhancing…" while running and "Enhance again" afterwards.

**Request:** `{kind, modelId, idea, direction, prompt, aspect, resolution, duration, referenceCount (0–4), storyboard, shotCount (2–4), framing, camera}`.

**Response:** `{ok, cached, result: {source: "ai"|"framework", notice, generationCredits: 0, shots: [{title, prompt, settings:{aspect,resolution,duration}}]}}`.

**Result area:**
- Heading "Enhanced preview", or "Storyboard" when there are multiple shots.
- Source tag "AI enhanced" or "TEZU framework", plus "· cached".
- The notice (today: "AI enhancement is awaiting billing verification. This preview uses the TEZU framework.").
- For storyboards: "Separate clips · not automatically combined. Minimum clip durations may exceed your original total."
- Checkbox "Apply compatible setting suggestions". This lets the assistant also set aspect, resolution and duration, after validation against the model.
- Each shot is an editable textarea with a header like "1. Establish   9:16 · 480P · 4s" and a button "Use Prompt" or "Use Shot N Prompt".
- Footer: "No generation starts until you press the generator's Generate button."

Applying a shot replaces the main prompt and shows "Undo enhancement". The multi-shot storyboard just gives N separate prompts; you generate each clip separately.

**The TEZU framework (deterministic template, verbatim pieces):**

```
<idea>. <DIRECTION> <FRAMING> <DURATION> <CAMERA> Maintain consistent lighting, atmosphere, anatomy and object positions throughout. [<REFS>] [<SHOT>] Use clear action timing and one coherent camera move; maintain character and spatial continuity.
```

- DIRECTION:
  - Cinematic: "Cinematic visual treatment, motivated lighting, deliberate composition and restrained contrast."
  - Realistic: "Natural lighting, believable materials and proportions, authentic photographic detail."
  - Animated 3D: "Polished stylized 3D animation, tactile materials, appealing shapes and cohesive lighting."
  - Funny: "Playful visual tone; emphasize the humor already present in the idea without adding unrelated characters or events."
  - Product Commercial: "Clean commercial presentation, precise material detail and intentional product framing; no invented logos or claims."
- FRAMING:
  - Auto: "Keep the requested subject clearly framed with a coherent foreground and background."
  - Otherwise: "<Wide|Medium|Close-up> framing; keep the subject unobstructed."
- DURATION:
  - Short clips (4s): "A 4-second clip: one clear action beat, with no rushed montage."
  - Longer clips (12s): "A 12-second clip: a measured progression of the requested action, without unrelated events."
- CAMERA:
  - Auto: "Camera movement stays restrained and follows the described action."
  - Otherwise: "<Static|Tracking|Slow push-in> camera; smooth movement, no abrupt cuts."
- REFS (when referenceCount > 0): "Preserve the supplied references' identity, proportions, outfit and defining details; change only what the idea requests."
- SHOT (storyboard): shot titles are Establish / Action / Continue / Resolve.
  - Shot 1: "Storyboard shot 1 of N: establish the requested scene."
  - Middle shots: "Storyboard shot k of N: continue the requested action."
  - Last shot: "Storyboard shot N of N: hold on the requested action's outcome, without inventing a new event."
  - Every shot then adds: "Preserve the same subject, setting and visual treatment across shots."
- Image variant (Image Studio) replaces DURATION/CAMERA/ending with: "Balance composition, environmental detail and focal hierarchy; keep anatomy and textures coherent. Keep character details stable and any requested text legible; do not add unrequested text."

The "ai" mode (an LLM rewrite) exists server-side but its system prompt is not exposed to the client. It was off ("awaiting billing verification"). Server-side guardrails seen in the client validation:
- prompt 1–2,000 characters (video) / 1,500 (image)
- "Storyboards are available in Video Studio only."
- "This suggestion is no longer compatible with the selected model."
- error fallback "Prompt Assistant could not complete this request. Your original idea is unchanged."

---

## 4. Image Studio `/create/image` (image-studio.png, image-model-picker.png)

The same studio layout as Video. Subtitle "Create stunning images from your ideas."

- **Model** picker. Tags: All, Fast, High Quality, Budget. Providers: Google, OpenAI, Midjourney, xAI, ByteDance, Wan.
- **Prompt**: "0 / 1,500", placeholder "Describe the image you want to create...". Plus the Prompt Assistant (no storyboard, no camera control).
- **Reference images**: max 4 (Grok 3), same dropzone and "Use saved character". Hint: "Say what to keep from each reference, e.g. "the character from my reference, now at a beach café"."
- **Aspect ratio**: 9:16 · 4:5 · 1:1 · 3:2 · 16:9.
- **Resolution**: 1K · 2K · 4K (Grok has 1K and 2K only).
- Note "Every finished image is saved privately in My Creations." Then **Generate Image [◆ N]** with reason "Generation opens shortly".
- One image per run; there is no batch count control.
- Workspace History/Gallery as in Video. Empty: "Your next creation starts here. Describe your idea to generate an image." Gallery: "Finished images will collect here." Error: "Something is still generating".
- Submit payload: `{prompt, model, aspect, resolution, characterIds?/jobIds?/uploadPaths?, idempotencyKey, clickedAt}`.

| Image model (id → providerModel) | Provider | Tags | 1K | 2K | 4K | Max refs | Sizing |
|---|---|---|---|---|---|---|---|
| Nano Banana 2 (`nano-banana-2`) "Rich detail" | Google | High Quality | 3 | 3 | 4 | 4 | ratio |
| Nano Banana Pro (`nano-banana-pro`) "Max fidelity" | Google | High Quality | 4 | 4 | 4 | 4 | ratio |
| **Nano Banana 2.1** (`nano-banana-2.1`), default, Recommended, "Crisper text · steadier characters" | Google | High Quality | 3 | 3 | 4 | 4 | ratio |
| GPT Image 2.5 (`gpt-image-2.5` → `gpt-image-2.5-sunburst`) "OpenAI · sharp prompts" | OpenAI | Budget | 2 | 2 | 3 | 4 | pixels |
| GPT Image 2 (`gpt-image-2`) "OpenAI · previous gen" | OpenAI | Budget | 2 | 2 | 3 | 4 | pixels |
| Grok Imagine (`grok-imagine` → `grok-imagine-image-2.0`) "xAI · text-to-image + edit" | xAI | Fast, Budget | 2 | 2 | – | 3 | ratio |

Provider USD per image: Nano Banana 2/2.1 $0.02 (1K/2K), $0.025 (4K); Pro $0.03; GPT Image $0.015/$0.015/$0.02; Grok $0.015.

Coming soon: Midjourney "Signature MJ aesthetic", Grok 2 Image, Seedream 4.0 "Posters & layout", Seedream 4.5 "Crisp type & key visuals", Seedream 5.0 Lite "Fast · 4K lite", Wan 2.6 "T2I + edit · max 3 refs".

**Reference upload pipeline (client):**
- Accepts png/jpeg/webp up to 20 MB.
- Images over 3 MB are re-encoded on a canvas to JPEG at ≤2048px long edge, trying quality 0.92 → 0.85 → 0.78 and shrinking by 0.75× until ≤3 MB.
- The base64 is posted to a server function `{contentType, base64}`, which returns `{path, url}` in the private Supabase bucket `creations`. Signed URLs come from `storage/v1/object/sign/creations`.
- Reference kinds: `upload` (uploadPaths), `character` (characterIds), `job` (jobIds = an earlier image creation).

---

## 5. Character Creator `/create/character` (character-studio.png, character-more-options.png)

Subtitle "TEZU CHARACTER CREATION / Character Studio".

**Left panel:**
- **Choose your character**: two big image radio cards, **Boy** / **Girl**, each showing a sample turnaround sheet. Caption "Visual reference".
- **Describe your character**: "0/500", placeholder "Messy black hair, oversized hoodie, blue jeans and a confident smile...". The textarea auto-grows from 120 to 220px.
- **More options** (collapsible):
  - Age range: Auto / Child / Teen / Young adult / Adult / Older adult
  - Clothing: input "Optional outfit details"
  - Pose: Neutral / Confident / Relaxed / Custom (Custom opens "Describe a pose")
  - Background: Neutral studio / Warm studio / Cool studio / White studio / Custom (Custom opens "Describe a background or color")
  - Free-text fields, each with placeholder "As described": Hair color, Expression, Accessories, Shirt color, Pants color, Shoe color (160 characters each)
- Lock line: "Private original · saved after generation".
- **Generate Character [◆ 4]**. Breakdown "1 sheet · 9:16 · 5 views". Reason today: "Generation is off pending provider validation and an approved paid test. No credits will be used."
- The draft is autosaved in sessionStorage (`tezu-character-draft:<userId>`).

**Right workspace:**
- Tabs **Preview | History (count)**, link "My Characters".
- Preview toolbar: Size slider 40–160% (default 70) and a reset button.
- Before any generation it shows an example card: "Boy reference · Example / Character reference sheet / Style Cinematic 3D · Format 9:16 · Views 5 angles / Example sheet · not saved to your library", with an expand-to-fullscreen button.
- Generating: spinner, "Creating your character", "Your request is processing. Recent attempts will show its status when you return."
- Failed: "We couldn't complete this generation." with "Back to canvas".
- **After a result:**
  - Name input "Name your character" + **Save Character**. This inserts into the `characters` table `{name ≤80, description ≤500, style, image_path, job_id, metadata=settings}`; toast "<name> saved to My Characters"; default name "Untitled character". Once saved, the form changes to "Saved to My Characters · Open library →".
  - **Download** (`<name>.png`).
  - **Create a Scene** → `/create/image?character=<id>` (or `?ref=<jobId>` if unsaved).
  - **Bring to Video** → `/create/video?character=<id>`.
  - **Create Variation** is disabled, tooltip "Reference variations await provider verification".
  - Note: "References guide consistency; exact identity matching isn't guaranteed."
- History tab: "Recent attempts N", a thumbnail grid with status and "Credits returned"; empty "No generations yet."

**Output:** one 9:16 "five-view turnaround" reference sheet (front plus 4 angles). The style is fixed to `cinematic-3d` in the UI, but the library knows five styles:
- Cinematic 3D "Feature-film 3D look"
- Stylized Animation "Bold shapes, series-ready"
- Realistic "Photographic detail"
- Cartoon "Clean lines, playful"
- Anime-inspired "Crisp line art"

Generate payload: `{description, style:'cinematic-3d', outfit, customOutfit, background, customBackground, characterType, appearance, age, pose, customPose, gender, format:'reference-sheet', hairColor, expression, accessories, shirtColor, pantsColor, shoeColor, idempotencyKey}`.

The OG description reads "Create original cinematic 3D characters as five-view turnaround sheets."

### My Characters `/characters` (in-characters.png)
- Header "LIBRARY / My Characters / Your private character collection. Ready for new scenes and stories." Button "New character".
- Search "Search characters". Style filter: All styles / Cinematic 3D / Stylized Animation / Realistic / Cartoon / Anime-inspired. Sort: Newest first / Oldest first / Name A–Z.
- Card actions (from the bundle): View character, Rename character ("Give them a name you'll recognise later."), Download, Delete ("This removes the character from your library. It can't be undone."), **Use in Image Studio**, **Use in Video Studio**, "Reference variations · soon". The details view shows Description and Saved settings plus "Boy · Reference sheet".
- Empty: "Your characters live here. Save a character once. Bring it into new scenes whenever you want. [Create your first character]".
- No folders, tags, groups or brands.

---

## 6. My Creations `/creations`
- Header "LIBRARY / My Creations / Everything you've generated, saved privately to your account." Button "New creation".
- Tabs: All / Images / Videos / Characters.
- Grid → lightbox "Open full screen" with Download and Reuse prompt.
- Empty: "No creations here yet / Generate an image, video or character and it will be saved here automatically." with Image and Video buttons.
- Query: completed jobs with a result, newest first, limit 120.

---

## 7. Templates `/templates`, `/templates/<slug>` (in-templates.png, template-golden-goal.png)

- Gallery tiles show a people-count badge and "1 SHOT".
- Banner "Living Worlds · Original illustrated worlds · Coming soon. [Explore Living Worlds]".
- Nine templates: Golden Goal (2), Money Count (1), Stadium Salute (1), Wedding Entrance (1), Studio Duet (2), Lounge Hype (2), Dockside (2), Sunset Groove (3), Beach Shuffle (1). All `shots:1, model:'seedance-2.5'`.
- **Detail page:**
  - Left: "Photos 0/2" with one upload slot per person: "Person 1 — Replaces the purple person", "Person 2 — Replaces the blue person", "Person 3 — Replaces the yellow person". People in the example clip are colour-coded purple, blue, yellow, green.
  - Resolution 480p / 720p / 1080p; "Planned model: Seedance 2.5 · not connected."
  - Consent toggle "I understand, results may vary", then **Generate**: "Preview only · Template generation is coming soon. No credits will be charged."
  - Right: tabs History / How it works and a preview player of the example clip ("These clips are supplied examples, not verified TEZU-generated results").
  - Bottom: a horizontal template strip with a "Selected" marker.
- Concept: a reference-video motion template plus face/photo swaps per colour-coded person. The cost formula already adds reference-video seconds.

---

## 8. Viral Cartoons `/create/worlds` (Soon) and `/living-worlds`
- Header "Viral Cartoons / Create your next world. / Generate an image. Pick your favorite. Make it yours."
- **1. Create an image**:
  - Mode toggle: **Surprise Me** / **My Own World** (the latter adds "Your idea" textarea, 500 characters, "A tiny village inside a glowing forest…").
  - Theme select: Surprise me, Cozy forest campfire, Giant fantasy treehouse, Magical library, Rainy nighttime cabin, Floating pirate village, Enchanted castle, Underground glowing cave, Lakeside camping village, Magical nighttime market, Cozy fantasy inn, Snowy mountain lodge, Hidden woodland village.
  - Aspect 9:16 (RECOMMENDED) / 1:1 / 16:9.
  - "Image generations" 1 / 2 / 3 / 4 (BEST ODDS), with the copy "Roughly half of attempts fail, so 4 gives you the best odds of a keeper." Spec line "Nano Banana 2.1 · 2K · 4 images".
  - Button "Generate Images ✦ 12". The confirm step reads: "Generate 4 images for 12 credits? Each attempt costs 3 credits and failed ones are returned. No video credits will be used."
  - Progress copy "Generating image k of N…" with per-slot status tiles.
- **2. Choose your favorite**: pick from the batch, then Download Image and "Animate Image" (disabled, "Animation coming soon · priced separately"). Also an "Earlier worlds" gallery.
- Overlay "COMING SOON · FINAL POLISH UNDERWAY".
- Social proof block: "Worlds no one can stop watching. 30M+ views across these five videos · 61K+ followers gained in one month · @whenlifefeltreal · made with TEZU".
- `/living-worlds` landing: "Create magical illustrated worlds that come alive with beautiful little movements. No prompting required." Steps 01 Choose a world → 02 Create an illustration → 03 Bring it to life.

## 9. AI Influencer `/ai-influencer` (in-ai-influencer.png)
- Three columns: left "Create new" (drafts sidebar), centre preview "Your AI influencer lives here. Design and build your AI influencer from scratch" with a disabled **Generate Influencer 🔒** button ("Generation coming soon · No credits charged"), right "Appearance settings" accordions.
- Accordions:
  - Gender: Female / Male
  - Ethnicity / Origin Base: photo tiles African, Asian, European, Indian, Middle Eastern, Mixed (separate male/female photos)
  - Skin Color: swatches Black, Deep, Fair, Purple, Tan, Olive, Slate, Green, Blue, Red, Silver + custom colour picker
  - Eye: photo tiles Black, Purple, Green, White, Brown, Solid Black, Cloudy White, Deep Brown, Blue, Amber, Red, Grey + custom
  - Hair color: Black, Dark Brown, Brown, Auburn, Blonde, Platinum, Copper, Silver, Rainbow + custom
  - Age: Adult / Mature / Senior
  - Body type: Slim / Average / Athletic / Muscular / Curvy / Plus Size
  - Additional details: textarea, 2,000 characters
- "Copy appearance prompt" copies this template:
  `Original fictional adult influencer. {Gender}, {age}, {Origin} heritage, {Skin} skin, {Eyes} eyes, {Hair} hair, {Body} build. Natural skin texture, realistic anatomy, professional portrait lighting. {details}`

---

## 10. Pricing `/pricing` and credits

Header "TEZU PRICING / Room for every creator. / Start at $9…". Toggle Monthly / Annually (annual is shown as "proposed"; checkout is monthly only).

| Plan | Price/mo | Credits/mo | Annual (proposed) | Bonuses (proposed, inactive): sheets / 2K images / 480p 5s videos |
|---|---|---|---|---|
| Lite "Try TEZU affordably" | $9 | 120 | monthly only | none |
| Starter "For getting started" | $19 | 270 | $228/yr | +2 / +10 / – |
| Plus "For everyday creators" (SAVE 20%) | $59 | 1,200 | $47/mo, $564/yr | +10 / +40 / +1 |
| Ultra "For serious creators", RECOMMENDED (SAVE 23%) | $129 | 3,000 (volume selector 3,000 / 6,000 / 9,000) | – | +25 / +100 / +3 |
| Agency (inquiry only) | $397 | 12,000 | – | +75 / +250 / +5 |

- Every plan includes "Character, Image & Video tools · Private creation library · Saved character references · Downloadable outputs".
- **Plan finder** ("Find the best plan for you"):
  - 1: "What are you here to make?" multi-select: Social media videos, Cinematic AI videos, AI characters, AI images & artwork, Marketing & product content, Personal projects.
  - 2: "How much content per month?" steppers using "≈ 43 credits per video · 3 per image · 4 per character" (defaults 10 videos = 430, 20 images = 60, 2 characters = 8).
  - 3: Features.
  - Result: "We recommend Plus plan — Expected monthly usage 498/1,200 credits".
- **Compare table** ("Expand all"): Video (Seedance 2.5, resolutions, "2–30s by model", bonus videos), Image (Nano Banana 2.1: 1K 3 credits, 2K 3, 4K 4), Character Creator (4 credits/sheet, Boy & Girl starting references, Custom descriptions, Reference sheets, Saved library, Reuse in images & videos), Credits & Usage ("Exact cost shown before each run", "Failed generations refunded", rollover "To be confirmed", Buy extra credits), Access & Features.
- Pricing FAQ, key facts:
  - No rollover: unused subscription credits expire at the monthly reset. Promo and test balances are kept separately.
  - Upgrades are prorated; downgrades apply at period end.
  - Bonus eligibility: one Nano Banana 2.1 2K image or one 9:16 sheet, or one Seedance 2.5 clip ≤5s 480p, with no reference videos.
  - Agency has no team seats ("No team seats, enterprise controls…").
- Home FAQ, key facts:
  - "TEZU handles the technical prompt for you."
  - "Video Studio currently offers 5, 10 and 15 second clips" (stale versus the 2–30s slider).
  - Failures auto-refund.
  - Support via Instagram @nateassets or the Hire form.

**Credits plumbing:**
- Supabase tables: `credit_balances(credits, bonus_images)`, `stripe_credit_cycles(remaining, starts_at, ends_at, livemode, revoked)`, `credit_ledger(id, delta, reason, created_at)`.
- Credits are reserved at submit, `credits_charged` is set on the job, and refunds go to `credits_refunded`.
- Settings shows a History ledger line, e.g. "Early-access test credits · 23 Oct 2026, 18:18 · +20".

## 11. Settings `/settings`
- "ACCOUNT / Settings & credits".
- Profile: Display name, Email (read-only), Save changes, Sign out, and "Need your account deleted? Email us…".
- Credits & Billing: balance "20 available"; Account benefits; Image promotion: inactive; Subscription status with renewal/cancel copy; Manage billing (when subscribed); History ledger.

## 12. Rewards `/rewards` (rewards.png)
- A gamified retention page for Plus and above: "Your daily spin is waiting".
- Prize wheel slots: 10 credits, Boost "Faster generations", 15 credits, 3 images, 3 characters, 1 video, "$129 Ultra · 1 month" (legendary).
- Also a 7-day streak and a "Chicken Cross — Hop lanes, chase the 10x" mini-game.
- Gated: "Upgrade to Plus to unlock". Not live.
- Admin config (from the bundle) includes probabilities in basis points, daily budget USD, credit caps, overhead / paid-failure / abuse percentages, and a scenario cost model.

## 13. Other public pages
- **Hire** `/hire`: "Your vision. Our production." Service list.
- Quote form fields: Name*, Email*, Instagram or company website, Brand or creator name, Content category, Number of videos, Project description*, Desired timeline, Estimated budget, consent checkbox. Select options:
  - Content category: Storytelling / Creator content / Advertising / Brand campaign / Animation / Other
  - Number of videos: 1 / 2–5 / 6–10 / 10+ / Ongoing
  - Desired timeline: Flexible / Within a month / 1–3 months / Not sure yet
  - Estimated budget: Under $500 / $500–$2,000 / $2,000–$5,000 / $5,000+ / Not sure yet
- Process steps on Hire: 01 Tell us your vision → 02 We plan → 03 Production after scope and payment → 04 Review and delivery.
- **About**: "Built for stories that move people." Audiences: Creators, Brands, Creative Agencies, Media & Entertainment.
- **Auth**: "Welcome back to TEZU", Continue with Google / email + password / Forgot password? / "New to TEZU? Create an account". Signup requires an 18+ and Terms checkbox, then "Sign up with Google" / "Continue with Email". The right half plays a looping Seedance 2.5 animation.

---

## 14. Backend / network (inferred)

- **Framework:** TanStack Start (React 18, TanStack Router + Query), built and hosted on **Lovable Cloud**. Evidence: `/__l5e/trackevents` analytics, `/__l5e/assets-v1/...` asset CDN (R2 keys), `~flock.js`, and the privacy policy's "Lovable Cloud (hosting, sign-in, database, private media and email delivery)". Pages are `noindex`.
- **Server functions:** `GET|POST https://tezu.ai/_serverFn/<sha256>`, JSON body keys `["t","f","m"]` (seroval-serialised). Identified functions:
  - workspace-status (`generationEnabled`, `characterCost`)
  - rewards status
  - submit video / image / character job
  - job progress poll (`{jobId}` → `{status, progress}`)
  - delete job (`{jobId}`)
  - upload reference (`{contentType, base64}` → `{ok, path, url}`)
  - prompt enhance (§3.4)
  - checkout, billing and purchase-disclosure functions (settings)
  - agency inquiry
  - worlds images
  - admin accounts / analytics
- **Supabase project** `nclurwqfdtrtdinlrqrf.supabase.co`:
  - Auth: `/auth/v1/token` (email + password, plus Google OAuth) and `/auth/v1/user`.
  - REST tables read client-side under RLS: `profiles(id, display_name, avatar_url)`, `characters(...)`, `generation_jobs(...)`, `credit_balances`, `stripe_credit_cycles`, `credit_ledger`.
  - RPC `tezu_is_admin`.
  - Storage bucket `creations` (private, signed URLs).
  - The client inserts directly into `characters` on "Save Character".
- **Payments:** Stripe (`js.stripe.com`, `m.stripe.com`), selling through **Link** as seller of record ("LINK.COM* TEZU.AI").
- **Model routing:** "**ArgoLink**, operated by HAPPYTOKEN TECHNOLOGY LIMITED of Hong Kong (routing generation requests to the selected third-party model, for example Google or ByteDance models)". "For a generation we send the prompt, settings and any needed reference image or temporary image link to ArgoLink." The client sends TEZU model ids; the server maps them to `providerModel` strings such as `seedance-2.5`, `seedance-2.0-fast`, `minimax-h3`, `wan-3-prime`, `nano-banana-2.1`, `gpt-image-2.5-sunburst`, `grok-imagine-image-2.0`. No direct replicate / fal / openrouter / byteplus calls or strings in the client.
- **Policy-review page:** "AI enhancement awaiting billing verification", and "Public checkout and paid generation stay off until tax-collection setup is confirmed".

## 15. Design system and UX feel

- **Theme:** dark only. Near-black violet background `oklch(14.1% .004 285.8)`. Surfaces step up `oklch(18.4%)` → card `21.6%` → surface-2 `25.5%`. Borders are white at 8% alpha.
- **Accent:** violet/purple `oklch(60.6% .219 292.7)` (≈ #8b5cf6), with a highlight `oklch(72–78% .13–.18 295–306)`. Destructive is `oklch(65% .2 22)`. Bonus yellow `oklch(92% .2 112)` is used for PLUS badges.
- **Fonts:** **Geist** (sans) and **Geist Mono**. Radius `.875rem` (14px). Soft inset-highlight shadow plus a long dark drop shadow (`--app-shadow`).
- **Components** (shadcn/Radix style, lucide icons):
  - pill badges ("New", "Soon", "PLUS", "30% OFF" hanging under the Pricing button)
  - segmented button groups, chip filters, Radix popovers and selects, alert-dialogs for destructive actions, toasts (sonner)
  - a `<details>` "Advanced" disclosure
  - range sliders with min/value/max labels
  - aspect-ratio buttons with a drawn rectangle icon
- **Studio pattern:**
  - Left control panel with a looping "tool banner" video and a label (e.g. TEZU VIDEO GENERATION), field labels with right-aligned asides (counters, "Optional").
  - A sticky, full-width purple Generate button with the cost as a ◆ chip inside it, and the reason/state line below.
  - Right workspace with a History/Gallery tab switch and a "My Creations" link.
- **Honesty microcopy everywhere:** "No credits will be used", "References guide the look — exact likeness isn't guaranteed", "Failed · refunded", "Example sheet · not saved to your library", "No generation starts until you press the generator's Generate button."
- **Empty states:** centred large bold headline ("Your next scene starts here."), muted subline, one secondary CTA with a sparkle icon. A small purple gradient line sits above the headline.
- **Mobile:** fixed blurred header (logo, credits, avatar, hamburger), a full-screen menu sheet with large type, stacked forms, and a fixed bottom Generate bar with a shadow.
- **Motion:** autoplay muted loop videos everywhere, the gen-orbit progress animation, the gen-reveal on completion, `app-shimmer` loading skeletons.

## 16. Ideas worth copying for Brand Studio
1. A **cost preview on the Generate button**, recomputed live from a declarative model catalogue (per-second × resolution tier). Reasons for a disabled button are shown inline.
2. A **declarative model catalogue** (`kind, id, providerModel, name, desc, provider, tags, resolutions[{id, usd, credits}], min/maxDuration, aspects, maxRefs, audio, status: available|coming_soon`). It drives the picker, its filters, validation, cost and clamping when you switch models.
3. A **Prompt Assistant** with structured inputs (direction chips, framing, camera, multi-shot count). It returns editable per-shot prompts and suggested settings, has an "apply settings" checkbox and "Undo enhancement", and falls back to a deterministic template when the LLM is unavailable (cached results flagged).
4. **Character → Scene → Video chaining** through URL params (`?character=`, `?ref=`) with one-click "Create a Scene" / "Bring to Video". The character sheet (5-view turnaround) acts as the reference asset.
5. **History with job states, refunds, Reuse prompt / Try again**, a list/grid toggle and a size slider stored in localStorage, plus polling progress.
6. **Idempotency keys** on every submit. Credits are reserved and auto-refunded on failure; the ledger is visible in Settings.
7. **Templates** with colour-coded "replace the purple person" photo slots on a reference clip.
8. Batch-of-N with "best odds" guidance (Worlds) and a confirm step showing the exact cost.

## 17. Not accessible / not observed
- Actual generation outputs, queue timings, real progress UI with data, and the result/lightbox with a real asset. Generation is globally disabled and nothing was generated.
- The AI-mode Prompt Assistant (the LLM system prompt is server-side and the mode was off); only the deterministic framework was observed.
- Admin pages (`/admin`, `/analytics`, `/worlds-admin`, `/rewards-admin`, `/agency-review`) require admin.
- Checkout and Manage billing (not opened, by rule). Template generation, AI Influencer generation and Rewards spins are not live.
- No projects, folders, brands, teams/workspaces, scripts or scene timelines exist anywhere on the site. Multi-shot exists only as Prompt Assistant storyboard prompts (2–4 separate clips, not stitched). Share links and public profiles do not exist.
