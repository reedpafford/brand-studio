# A video (`/b/:brandId/projects/:id?stage=`)

Six steps: **Brief → Script → Shots → Storyboard → Clips → Final video**. `?stage=` keeps working; `enhance` opens Script with the suggestions showing, and `breakdown` opens Shots.

Prices in this spec are examples. Real prices come from `GET /credits/rates` and the estimate, rounded up to whole credits.

## Frame (every step)

### Desktop
```
┌ header ───────────────────────────────────────────────────────────────────────────────┐
│ ‹ Videos                                                                              │
│ Bo tries salmon (page 32)  ✎                         412 of 660 credits ━━━━━━──  [FileText Script] │
│ ✓Brief ── ✓Script ── ✓Shots ── ●Storyboard ── Clips ── Final video          step picker │
├───────────────────────────────────────────────────────────────────────────────────────┤
│ Storyboard (section 20) · 4 frames · 3 approved (meta)          [Next: Clips]  amber  │
│ (reason line under the amber button when disabled)                                    │
│ …the step's work, full width (max 1280)…                                              │
└───────────────────────────────────────────────────────────────────────────────────────┘
```
- **Back link:** ghost dense, `ChevronLeft` "Videos".
- **Title:** page role. `Pencil` icon button (`aria-label="Rename"`) turns it into an input with Save / Cancel.
- **Meter:** "412 of 660 credits" (meta, `tabular-nums`) with a 120px bar. Turns `warn` at 80%, `danger` over 100%. Editors never see dollars.
- **Script button:** secondary dense, `FileText` "Script". Hidden on Brief and Script (the script is already the page there). Opens the Script side panel (380px, from the right). The panel shows the working script read-only in the script role, with line numbers, a "Lines for this step are highlighted" meta line, and **Edit in Script** (ghost) that goes to the Script step.
- **Step picker:** six steps in a row joined by 1px lines, each 44px tall.
  - Done: `Check` in `success`, label in text colour. Clickable.
  - Current: an amber pill with the step number and label (`bg-accent text-on-accent`).
  - Not yet: the step number and a muted label, not clickable, focusable, with a tooltip saying why: "Finish Shots first".
  - Out of date (an earlier step changed after this one was done): `TriangleAlert` in `warning`, label "Storyboard · out of date".
- **Step bar:** step title (section), a meta summary, and on the right the step's **one amber button** (the price inside when paid) with any secondary buttons to its left. The disabled reason sits under the amber button, right-aligned.
- Steps change with a 220ms crossfade plus 8px rise.

### Phone (390)
```
┌ top bar 56 ─────────────────────────┐
│ ‹  Bo tries salmon        62% ━━─   │  one line: back, title (truncates), meter
├──────────────────────────────────────┤
│ [● Storyboard  3 of 6  ⌄] [FileText] │  step picker (select) + Script button 44px
│ …the step's work…                    │
├ action bar ──────────────────────────┤
│ [          Next: Clips             ] │
│ Approve every frame first (1 left)   │
├ tabs ────────────────────────────────┤
```
- The video's top bar replaces the brand top bar; the bottom tabs stay.
- **Step picker:** a 44px secondary button "Step 4 of 6 · Storyboard" with `ChevronDown`. It opens a sheet listing the six steps with the same Done / Current / Not yet / Out of date marks, and the reason under each locked step.
- **Script button:** 44px icon button, `aria-label="Script"`, opening the script as a sheet (90dvh).
- The meter shows as a percentage plus a 48px bar; tapping it shows "412 of 660 credits" in a toast-style popover.
- The old Script/step tabs and the stage dropdown are gone.

## 1. Brief
See `new-video.md` (Edit brief). Amber: **Next: Script**.

## 2. Script
The script is the page, in the script role (Courier Prime 14/22), max 72 characters per line, line numbers in `text-faint`.

**Toolbar** (desktop, above the script): Drafts selector · **Edit** (secondary, `Pencil`) · **Suggest directions** (secondary, `Sparkles`, with its price "· 2 credits") · "Saved" / "Saving…" (meta). Amber: **Next: Shots**.

- **No script yet (empty):** two cards side by side (stacked on phone):
  - **Write it with Claude** (`Sparkles`): "Claude writes 3 drafts from your brief. You pick one." Button: amber **Write 3 drafts · 3 credits**.
  - **Upload your own** (`Upload`): "A .txt, .md or .fountain file, or paste it in." Buttons: secondary **Upload a file**, ghost **Paste it in**.
- **Drafts:** after writing, three cards (one column on phone, three on desktop), each with "Draft 1" (card), a 6-line preview in the script role, word count and length ("about 28 s") in meta, and **Use this draft** (secondary). Picking one makes it the working script. The others stay under the Drafts selector ("3 drafts · using Draft 2").
- **Edit:** the script becomes a textarea in the script role (`aria-label="Script text"`), with **Save script** (amber, replaces Next while editing) and **Cancel** (ghost). Saving makes a new version; the toast says "Saved. Undo".
- **Versions** (in the Drafts selector menu, under a divider): "Today 10:42 · edited by Sam", newest first. Picking an older one shows it read-only with a banner "You're looking at an older version." **Restore this version** (secondary) and **Back to the latest** (ghost). Version numbers never show.
- **Suggest directions** (was Enhance): the suggestions appear as indented lines under the script lines, exactly as in `docs/design/screens/script-enhance.md`, with these changes:
  - Marks: `bg-mark` with a 2px `mark` underline; the kind label (caption, muted) at the right: Camera, Movement, Reaction, Brand screen.
  - Toolbar while suggestions are showing: "9 suggestions · 1 note" (meta), filter chips (scroll inside on phone), **Accept all** (ghost, menu), and the amber button becomes **Add 2 directions**. Its reason when 0 are accepted: "Accept at least one suggestion".
  - Each suggestion has **Accept** (secondary dense, `Check`) and **Reject** (ghost dense, `X`); 44px on phone.
  - Notes sit in a card under the toolbar (desktop: right column 320px) with **Got it**.
  - After adding: toast "Added 2 directions. Undo", and Next returns.
- **States:**

  | State | What shows |
  |---|---|
  | Writing drafts | Three draft-card skeletons + "Writing 3 drafts… 12 s" |
  | Reading for suggestions | Skeleton marks under every third line + "Reading your script… 8 s" |
  | Nothing to suggest | Toast: "This script already reads well. Nothing to suggest." |
  | Failed | Danger banner: "The drafts didn't finish. Nothing was charged. [Try again]" (or "Suggestions didn't finish. Your script is unchanged.") |
  | Over the limit | Suggest directions is disabled with the reason under it (README rule 2). Nothing waits for Reed. |

## 3. Shots (was Breakdown)
Content and editing rules as in `docs/design/screens/breakdown.md`; only the look and placement change.
- **Step bar:** "Shots · 3 scenes · 9 shots · 4 clips · 28 s of 30 s planned". Secondary **Redo · 6 credits** (`RotateCcw`). Amber **Next: Storyboard**.
- **Problems card** (above everything, `bg-danger-soft`, `TriangleAlert`): "2 problems to fix before the storyboard". Each problem is a row with its sentence and **Go to** (ghost dense, `ChevronRight`). On phone it collapses to one 44px row "2 problems" that opens a sheet. Next's reason: "Fix the 2 problems first".
- **Out of date banner** (`warning`): "These shots were made for an older script." with amber **Make new shots · 6 credits** (this takes the step's amber slot; Next hides).
- **Scenes:** eyebrow "SCENE 1", then the heading in the script role and the look in meta.
- **Clip bands:** a card per clip (`bg-surface`, radius 14) with header "Clip 1 · 8 s" (card) and the seam in meta at the bottom ("Ends: hard cut to the street"). Seconds outside the model's range show in `danger` with the reason. The last clip shows the `neutral` badge "End line".
- **Shot rows** inside the band, divided by 1px borders:
  - Line 1: "1.1" (caption, muted) · "3 s" · camera (meta).
  - Line 2: the action (body).
  - Spoken line: `SPEAKER: "line"` in the script role, read-only.
  - Chips: cast (avatar picture), place (`MapPin`), brand screen (`Smartphone` + name), moment.
  - Right side: **Lines 2–3** (ghost dense, opens the Script panel with those lines highlighted) and **Edit** (ghost dense, `Pencil`). Split / Join live in an `Ellipsis` menu.
- **Edit** opens the shot inline on desktop, as a sheet on phone, with the fields from the breakdown table, **Save** (amber within the editor) and **Cancel**. The hint "To change the words, edit the script." sits under the read-only spoken line.
- **States:**

  | State | What shows |
  |---|---|
  | Empty | `Clapperboard` icon. **No shots yet**. "Claude splits your script into scenes, shots and clips. Nothing is filmed yet." Amber **Make shots · 6 credits** |
  | Loading | Two clip-band skeletons with three shot rows each + "Planning shots… 10 s" |
  | Error | Danger banner: "The shots didn't finish. Nothing was charged. [Try again]" |
  | Success | Toast "Shots ready. 2 problems to fix." or "Shots ready. No problems." Storyboard unlocks when there are no problems |

## 4. Storyboard
One still per clip. **Make storyboard** writes the frames and then draws the stills (the existing two calls, one after the other); people press once.
- **Step bar:** "Storyboard · 4 frames · 3 approved". Amber, by state:
  - No frames: **Make storyboard · 12 credits** (frames + stills, total rounded up).
  - Some stills missing: **Draw 2 missing · 6 credits**.
  - All drawn: **Next: Clips**, reason "Approve every frame first (1 left)".
- **Frame grid:** media cards in the video's shape. 2 columns on phone (gap 12), 4 on desktop (gap 16), 3 at 1024.
  - On the picture: the status badge top left ("Approved" success with `Check`, "Drawing…", "Didn't finish · credits returned", "Out of date"), and "Clip 1 · 8 s" (card) at the bottom over the shade.
  - Under the picture: reference chips (cast, place, `Smartphone` screen), then **Approve** (secondary, `Check`) and **Redo · 3 credits** (ghost, `RotateCcw`). Approved frames get a 2px amber ring and the button becomes **Undo approval**.
  - Redo asks "What should change? (optional)" inline (desktop) or in a sheet (phone) with **Redo · 3 credits**.
  - A frame blocked by a missing sheet shows, instead of the picture, `surface-2` with `TriangleAlert` and "Bo needs an approved sheet." plus **Open Bo** (secondary). The amber button's helper adds "1 frame waits for a sheet."
- **Lightbox:** tap a picture to open it full size over `bg-scrim`, with ‹ › between frames (and between older versions of this frame, "Earlier: 2"), Approve / Redo, and a collapsed "What Claude asked for" disclosure in the script role.
- **States:**

  | State | What shows |
  |---|---|
  | Empty | `Image` icon. **No storyboard yet**. "One still per clip, so you can check the look before paying for video." Amber **Make storyboard · 12 credits** |
  | Loading | Frame skeletons in the video's shape, each with "Drawing… 6 s"; frames appear one by one as they land |
  | Error | Per frame: badge "Didn't finish · credits returned" + **Try again · 3 credits**. All failed: danger banner "The storyboard couldn't be drawn. Nothing was charged. [Try again]" |
  | Success | Toast "Storyboard ready. Approve each frame." When the last frame is approved: toast "All frames approved. Next: Clips." and Next lights up |

## 5. Clips
Two presses, always, so prompts are read before takes are paid for.

**Press 1: Write clip prompts.**
- Empty state: `Film` icon. **No clips yet**. "Claude writes one prompt per clip from its frame and shots. You read them before any video is made." Amber **Write clip prompts · 3 credits**.
- While writing: one prompt-card skeleton per clip + "Writing prompts… 12 s".

**Review the prompts.** One card per clip:
```
┌ [frame 64×114]  Clip 1 · 8 s · shots 1.1–1.2                     [Looks good ✓] │
│ A golden retriever noses a bag of salmon treats across a sunlit       (script)  │
│ kitchen floor, slow push-in, warm morning light…                                │
│ [Edit]                                                    1 thing to check (warn) │
└──────────────────────────────────────────────────────────────────────────────────┘
```
- The prompt shows in the script role, at most 5 lines, with "Show all" (ghost dense). Image placeholders like `[Image1]` show as named chips: "Bo's sheet", "Kitchen".
- **Looks good** (secondary, `Check`) marks it read: a `success` badge "Looks good" and the button becomes **Undo**. **Edit** (ghost, `Pencil`) turns the prompt into a textarea with **Save** / **Cancel**; saving also marks it read.
- Prompt checks show under the prompt as `warn` rows with `TriangleAlert`, in plain words ("The end line isn't in the last clip").
- **Step bar:** "Clips · 4 prompts · 3 read". Amber: **Make the takes · 72 credits**, reason "Mark every prompt as Looks good first (1 left)". Past the budget, for an editor: disabled with "That's more than this video's budget."; for Reed: the plain **Make the takes · 72 credits** (README rule 2).

**Press 2: the takes.** After Make the takes, each card becomes a take card:
- Media first: the player in the video's shape (poster = the approved frame until the take lands), status badge top left, "Clip 1 · 8 s" over the shade. A `Play` button in the centre only once a take exists.
- Status words: "Queued", "Making… 1m 12s" (with a thin amber progress bar along the bottom edge of the picture), "Ready", "Approved", "Didn't finish · credits returned". Never "Waiting for Reed": a step held before 26 Oct shows the neutral "Not started" with **Cancel**.
- Under the picture:
  - **Takes:** segmented "Take 1 · Take 2" (newest picked when it lands).
  - **Looks good** (secondary, `Check`) approves the picked take: 2px amber ring, badge "Approved", button becomes **Undo approval**.
  - **Needs a change** (ghost) opens "What's wrong?" (required) and **Redo · 27 credits**; inline on desktop, a sheet on phone. The old take stays.
  - **Download** (ghost dense, `Download`).
  - **Use the real image · Chart down (shot 1.2)** switch rows, only on clips with a product or app-screen insert. Off by default. Helper (meta): "Free. Shows the real picture at that moment."
  - "Prompt" disclosure (collapsed, script role) to reread what was asked.
- **Step bar:** "Clips · 4 · 2 approved · 1 making". Amber, by state:
  - Some clips have no take (e.g. after a failure): **Make 1 missing · 27 credits**.
  - All takes in: **Next: Final video**, reason "Approve every clip first (2 left)".
- Grid: 1 column on phone, 2 on desktop (3 at ≥ 1440 for 9:16 videos).
- **States:** see `clips-states.png`.

  | State | What shows |
  |---|---|
  | Empty | As above, **Write clip prompts · 3 credits** |
  | Loading | Prompt skeletons (press 1) / take cards with "Making… 1m 12s" and the progress edge (press 2) |
  | Error | Per clip: "Didn't finish · credits returned" + "The video service was busy." + **Try again · 27 credits**. All failed or service down: danger banner "Clips can't be made right now. Nothing was charged." **Try again** |
  | Over the budget | For an editor, **Make the takes** and each Redo are disabled with "That's more than this video's budget." Nothing is sent to Reed and nothing waits. |
  | Success | Toast per landed take: "Clip 2 is ready to review." When all are approved: "Every clip approved. Next: Final video." |

## 6. Final video
- **Before it's made:** the approved takes as a filmstrip (small media cards in order, each "Clip 1 · 8 s", tap to play), total "28 s · 9:16" (meta). Amber **Make the video** with the meta line "Free. Puts your approved clips together in order."
- **Making:** a player-shaped skeleton + "Putting your clips together… 20 s".
- **Done:**
  - The player, large: max 420px wide for 9:16 on desktop (centred, with the details in a column to its right), full width on phone.
  - Badge "Ready" (success). Details: "28 s · 9:16 · 14 MB", "Made from: Clip 1 Take 2, Clip 2 Take 1, …" (meta).
  - Amber **Download MP4** (`Download`). Secondary **Make it again** only when out of date.
  - A quiet done moment: the step picker's last step gets its `Check`, and the toast "Your video is ready." Nothing bounces; with reduced motion, nothing moves.
- **Out of date** (a take, approval or real-image switch changed): `warning` banner "Out of date. A clip changed since this video was made." Amber becomes **Make the video again** (free); the old file still downloads (ghost **Download the older video**).
- **States:**

  | State | What shows |
  |---|---|
  | Locked | (not reachable: the step is "Not yet" until every clip is approved) |
  | Loading | Player skeleton + count-up |
  | Error | Danger banner "The video couldn't be put together. Nothing was charged. [Try again]" |
  | Success | As **Done** above |
