# Storyboard

Purpose: one still per clip (its first shot), so the editor can check the look, the cast and the brand screens before paying for video. Schema: `StoryboardFrames.frames[]` = `{clip_id, shot_id, prompt, reference_ids}`.

## Desktop (1440): the stage pane
```
│ Storyboard · 4 frames · 3 approved        [Make all · 12 credits]  │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                                  │
│ │ 9:16 │ │ 9:16 │ │ 9:16 │ │ ░░░░ │   frame shape = project aspect   │
│ │  ✓   │ │  ✓   │ │  ✓   │ │ …    │                                  │
│ └──────┘ └──────┘ └──────┘ └──────┘                                  │
│ c1 · 1.1   c2 · 2.1   c3 · 2.3   c4 · 3.1                            │
│ 8 s        6 s        9 s        5 s                                 │
│ [● Mia][★ Chart down]  references used, as chips                     │
│ [Approve] [Redo · 3]                                                 │
│                                         [ Next: Clips → ]            │
```
- Frames are a grid of 2 columns in the stage pane, or 4 when the pane is wide. Each frame shows:
  - the image, in the project's shape
  - the label "c1 · shot 1.1 · 8 s"; clicking it highlights that shot's script lines
  - the reference chips: cast, place, ★ screen, and "previous frame" when one is used
- **Approve** puts a 2px `--accent` border and a ✓ on the frame, and the button becomes **Undo approve**.
- **Redo · 3 credits** opens a small form: "What should change? (optional)" + **[Redo · 3 credits]**. The old image stays visible until the new one is ready, and both stay in the frame's history (‹ ›).
- **Make all** generates every frame that's missing, showing the cost. While frames are rendering they show a skeleton and "Drawing…".
- **Next: Clips →** is enabled only when every frame is approved, with the reason "Approve all 4 frames first (1 left)."
- A character or place without an approved sheet blocks its frame or clip: "Mia needs an approved sheet. [Open Mia]" (see `library.md`).
- If the breakdown changes after frames exist, the frames for changed clips get a warning badge "Breakdown changed: redo this frame" and lose their approval.
- **Lightbox:** clicking an image opens it full size, with the prompt (muted, collapsible "Prompt Claude wrote") and the same Approve / Redo buttons.

## States
- None yet: "No frames yet." / "One still per clip, so you can check the look before making video." / **[Make all · 12 credits]**.
- Failed frame: a danger badge "Didn't finish · credits returned" with **[Try again]**.
- Over budget: the button reads "Ask Reed to approve · 12 credits" (see `usage.md`).

## Phone (390)
- The tabs read **Script | Storyboard**, with one frame per row at full width and its buttons underneath (44px).
- The Redo form opens in a bottom sheet.
- **Next** sits in the fixed bottom bar.
