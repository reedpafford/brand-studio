# Project workspace

Purpose: one video, guided by its script, from brief to final cut. Script stays visible on the left the whole time.
Stages: Brief → Script → Enhance → Breakdown → Storyboard → Clips (review, redo and the finished video are inside Clips).
API: `/projects/{id}` (has `budget_credits`, `budget_pct`).

## Desktop (1440)
```
│ ← Projects  Mia buys the dip  ✎                [412 / 660 credits · 62%]          │
│ Brief ✓ ─ Script ✓ ─ Enhance ✓ ─ Breakdown ● ─ Storyboard ─ Clips                │ stepper
├───────────────── script pane (min 360, resizable 30–50%) ┬───────── stage pane ──┤
│ [Edit] [✦ Enhance]                     v4 · saved       │ Breakdown              │
│                                                         │ Scene 1 · Kitchen, 0:00│
│ SCENE 1 — INT. KITCHEN — MORNING          (Courier)     │ ┌ Shot 1.1 ───────────┐│
│ Mia scrolls her phone, coffee in hand.   ◀ shot 1.1     │ │ Wide · 4s · Mia      ││
│ MIA: Wait… it dipped?                    ◀ shot 1.2     │ │ ★ Screen: Chart down ││
│                                                         │ └─────────────────────┘│
│ SCENE 2 — …                                             │ ┌ Shot 1.2 ───────────┐│
│                                                         │ │ Close · 3s · Mia     ││
│                                                         │ [Next: Storyboard →]   │
```
- Stepper: done = ✓ teal, current = filled dot, future = muted. Any done stage is clickable. Future stages are not clickable and say why on hover ("Finish the breakdown first").
- Script pane: line-numbered Courier Prime, 1.6 line height, max 64 characters per line. Selecting a shot on the right highlights its lines on the left (`--accent-soft`) and scrolls them into view; and the reverse.
- Stage pane by stage:
  - **Brief**: form (Goal, Audience, Must show (brand screens, chips), Length, Format). [Write script] (cost shown in the button like every paid action).
  - **Enhance**: `script-enhance.md`.
  - **Breakdown**: `breakdown.md`.
  - **Storyboard**: `storyboard.md` (one frame per clip).
  - **Clips, review and the finished video**: `clips.md`.
- Credits meter in the header (see `usage.md`). If an action would push past 100%, its button reads "Ask Reed to approve · 120 credits" and sends an approval request instead.

## Phone (390)
```
│ ← Mia buys the dip      62% ● │
│ Breakdown ▾  (stage picker)    │
│ [ Script | Shots ]  segmented  │
│ …one pane at a time…           │
│ [ Next: Storyboard → ]  fixed  │
```
Stepper collapses into a "Stage ▾" select. Script and the stage pane are two tabs; tapping a shot's "◀ line 12" link switches to Script and highlights it. Main action of the stage is a fixed bottom bar.

## Copy
- Empty brief: "What's this video for?" / "A few lines is enough. Claude turns it into a script." 
- Locked stage: "Finish the <stage> first."
