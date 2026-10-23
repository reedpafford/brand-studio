# Script Enhance

Purpose: Claude suggests improvements to an uploaded script as marks the editor accepts or rejects. It never rewrites on its own (DECISIONS 2026-10-23).
Suggestion kinds: Scene break, Action, Reaction, Camera, Brand screen, Cut (remove dead air).

## Desktop (1440): the script pane in Enhance mode
```
│ ✦ Enhance · 14 suggestions        [Accept all ▾]  [Done]                   │
│ Show: [All 14] [Camera 4] [Brand screen 3] [Action 5] [Cut 2]              │
├────────────────────────────────────────────── script ───┬── side card 320 ─┤
│ SCENE 1 — INT. KITCHEN — MORNING                        │ 3 of 14  ‹ ›      │
│ Mia scrolls her phone, ░coffee in hand.░                │ CAMERA            │
│ ░Slow push-in on her face as she reads.░ ← added        │ Add: "Slow push-in│
│ MIA: Wait… it dipped?                                   │ on her face as she│
│ ┄┄┄┄┄┄┄┄┄┄ ⧉ new scene ┄┄┄┄┄┄┄┄┄┄                       │ reads."           │
│ ★ fomo screen: Chart down ← brand screen                │ Why: builds the   │
│ ~~She sighs and puts the cup down.~~ ← cut              │ hook before line 1│
│                                                         │ [Accept A][Reject R]│
│                                                         │ [Edit E]          │
```
## The marks
| Kind | Look |
|---|---|
| Added text | `--mark` background, 2px `--mark-line` underline |
| Cut | strikethrough in `--danger`, text in `--text-muted` |
| Scene break | dashed `--mark-line` rule across the pane with "new scene" label |
| Brand screen | ★ + brand dot + screen name in a chip, inline on its own line |
| Accepted | becomes normal script text (no trace); a toast "Accepted. Undo" |
| Rejected | disappears; toast "Rejected. Undo" |
| Focused | 2px `--accent` outline around the mark; side card shows it |

Each mark has a small kind label at the right edge (`--text-xs`, muted) so colour isn't the only signal.

## Behaviour
- Keyboard: `J`/`K` next/previous, `A` accept, `R` reject, `E` edit (inline textarea, then Accept), `Esc` leaves focus. Shown once as a hint line under the toolbar.
- Accept all ▾: "Accept all", "Accept all Camera", … Confirm when > 5: "Accept 14 suggestions?".
- Done: any pending marks stay saved as pending; banner on the script "4 suggestions waiting. [Review]".
- Every accept/reject creates a script version (shown as "v5 · saved").
- [✦ Enhance] again on a script that has pending marks asks "Replace the 4 waiting suggestions?".
- Running: skeleton lines over the script + "Reading your script…". Cost in the Enhance button.

## Phone (390)
Script fills the screen; marks look the same. Tapping a mark opens a bottom sheet (the side card content) with full-width [Accept] [Reject] and ‹ › to move. Filter chips scroll horizontally. Accept all lives in the ⋯ menu.

## Copy
- No suggestions: "This script already reads well. Nothing to suggest."
- Failure: "Enhance didn't finish. Your script is unchanged. [Try again]"
