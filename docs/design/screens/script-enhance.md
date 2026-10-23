# Script Enhance

Purpose: Claude suggests direction for an uploaded script. **It never changes the script's words** (Reed's rule). It only suggests:
- **Camera**: framing and moves ("Slow push-in on her face").
- **Movement**: what a character physically does ("Mia sets the cup down").
- **Reaction**: a beat or expression ("Mia's eyes widen").
- **Brand screen / product**: where a fomo screen or a product shows.

Suggestions are attached to a script line as direction notes, never merged into it. Anything else Claude notices goes in **Notes** as plain sentences, which never edit anything.

## Desktop (1440): the script pane in Enhance mode
```
│ ✦ Enhance · 9 suggestions · 1 note        [Accept all ▾]  [Done]          │
│ Show: [All 9] [Camera 3] [Movement 2] [Reaction 2] [Brand screen 2]       │
├────────────────────────────────────────────── script ───┬── side card 320 ─┤
│ SCENE 1 — INT. KITCHEN — MORNING                        │ 3 of 9   ‹ ›      │
│ Mia scrolls her phone, coffee in hand.                  │ CAMERA · line 2   │
│   ░▸ Slow push-in on her face as she reads.░   CAMERA   │ "Slow push-in on  │
│ MIA: Wait… it dipped?                                   │ her face as she   │
│   ░▸ Mia's eyes widen.░                       REACTION  │ reads."           │
│   ░★ fomo screen: Chart down░            BRAND SCREEN   │ Why: builds the   │
│ She sighs and puts the cup down.                        │ hook before line 3│
│                                                         │ [Accept A][Reject R]│
│                                                         │───────────────────│
│                                                         │ NOTES (1)         │
│                                                         │ The script says   │
│                                                         │ "strawberry", but │
│                                                         │ the brand kit has │
│                                                         │ no strawberry     │
│                                                         │ product.          │
│                                                         │ [Got it]          │
```
The script's own lines are never highlighted, struck through or edited. Suggestions sit on their own indented line under the script line they belong to.

## The marks
| State | Look |
|---|---|
| Pending suggestion | indented line starting `▸` (or `★` for brand screens), `--mark` background, 2px `--mark-line` underline, kind label at the right edge (`--text-xs`, muted) |
| Focused | 2px `--accent` outline; the side card shows it |
| Accepted | stays as an indented direction note in `--text-muted` with its kind label, no highlight; toast "Accepted. Undo" |
| Rejected | disappears; toast "Rejected. Undo" |

The kind label is always text, so colour is never the only signal. Brand screen notes show the brand dot and the screen name.

## Notes (side card, below the current suggestion)
- These are plain sentences about things Claude noticed but must not fix. Examples: a flavour or product the brand doesn't sell, a claim the kit's "Never say" list forbids, a missing legal line.
- Each note says which line it's about ("Line 4:") and links to it.
- The only action is **Got it**, which hides the note. There is no Accept, no Edit and no "fix it" button. Notes never touch the script.
- When there are no notes, the Notes section is hidden.

## Behaviour
- Keyboard: `J`/`K` next/previous, `A` accept, `R` reject, `Esc` leaves focus. Show these once as a hint line under the toolbar.
- Suggestion text can't be edited. If it's not right, reject it, or write your own direction in the script editor.
- Accept all ▾: "Accept all", "Accept all Camera", … When there are more than 5, confirm first: "Accept 9 suggestions?".
- Done: pending suggestions stay saved as pending, and the script shows the banner "4 suggestions waiting. [Review]".
- Every accept or reject saves a new version ("v5 · saved"). The script words are identical across these versions; only the direction notes change.
- Pressing [✦ Enhance] again while suggestions are pending asks "Replace the 4 waiting suggestions?". Accepted notes are kept.
- Running: skeleton lines over the script + "Reading your script…". The Enhance button shows the cost.

## Phone (390)
The script fills the screen, and suggestions look the same (indented lines).
- Tapping one opens a bottom sheet with the side card content, full-width [Accept] [Reject], and ‹ › to move between suggestions.
- A "Notes (1)" chip in the toolbar opens the notes in the same sheet.
- Filter chips scroll sideways. Accept all lives in the ⋯ menu.

## Copy
- No suggestions: "This script already reads well. Nothing to suggest."
- Failure: "Enhance didn't finish. Your script is unchanged. [Try again]"
