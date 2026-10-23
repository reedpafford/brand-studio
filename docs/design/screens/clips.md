# Clips, review and the finished video

Purpose: make one video clip per breakdown clip, review each one, redo what's wrong, then stitch them into one video to download. Schema: `ClipPrompts.clips[]` = `{clip_id, seconds, references[], prompt}`. Stitching costs no credits.

## Desktop (1440): the stage pane
```
│ Clips · 4 · 2 ready · 1 rendering · 1 not made   [Make missing · 72 credits] │
│ ┌ c1 · 8 s · shots 1.1–1.2 ───────────────────────────────── Ready ┐ │
│ │ [frame]  ▶ player (muted until you press play)                    │ │
│ │          Takes: (●) Take 2  ( ) Take 1                            │ │
│ │          [✓ Looks good]  [Needs a change]          [Download]     │ │
│ └───────────────────────────────────────────────────────────────────┘ │
│ ┌ c2 · 6 s ──────────────────────────────────────── Rendering 1m 12s ┐ │
│ │ [frame]  ━━━━━━━━──────                              [Cancel]     │ │
│ └───────────────────────────────────────────────────────────────────┘ │
│ ┌ c3 · 9 s ────────────────────────────── Failed · credits returned ┐ │
│ │ [frame]  The video service was busy.             [Try again · 27] │ │
│ └───────────────────────────────────────────────────────────────────┘ │
│                                                                       │
│ ┌ The video ──────────────────────────────────────────────────────┐   │
│ │ 3 of 4 clips approved. Approve every clip to make the video.    │   │
│ │ [Make the video]  (free)                                        │   │
│ └─────────────────────────────────────────────────────────────────┘   │
```
- **Clip card:**
  - Header: clip id, seconds, the shots it covers (clicking them highlights the script lines), and a status badge in words ("Not made", "Queued", "Rendering 1m 12s", "Ready", "Approved", "Failed · credits returned", "Waiting for Reed to approve").
  - Body: the approved storyboard frame as the poster, and the player once ready.
- **Takes:** every redo adds a take, and a radio picks the one used in the video. The newest take is picked when it arrives.
- **Review:**
  - **✓ Looks good** approves the picked take (green border and "Approved").
  - **Needs a change** opens "What's wrong?" (required) + **[Redo · 27 credits]**. The note goes to the Director/prompt step, and the old take stays.
  - Approving is per clip. Changing the picked take removes the approval.
- **Make missing** generates every clip that has no take yet. Like every paid action, it shows the cost, or "Ask Reed to approve · N credits" when over budget.
- **The video:**
  - **[Make the video]** is enabled when every clip is approved, with the reason otherwise: "Approve every clip to make the video (1 left)".
  - It stitches the picked takes in order, showing "Putting your clips together…" while it runs.
  - The result card shows: a player, "28 s · 9:16 · 14 MB", **[Download MP4]**, and "Made from takes c1 T2, c2 T1, …" (muted).
  - Changing any take or approval after that shows "Out of date. [Make the video again]".
- **Download** on a single clip downloads that take: `<project>-c1-take2.mp4`. The video downloads as `<project>.mp4`.

## States
- Nothing made: "No clips yet." / "Each clip is made from its storyboard frame and the breakdown." / **[Make all · 96 credits]**.
- All failed, or the service is down: a banner "Clips can't be made right now. Nothing was charged." with **[Try again]**.

## Phone (390)
- The tabs read **Script | Clips**. Clip cards are full width, with the player at full width and buttons stacked (44px).
- "Needs a change" opens a bottom sheet with the note and **Redo**.
- The fixed bottom bar shows **Make missing · N credits** until every clip has a take. After that it shows **Make the video**, then **Download MP4**.
