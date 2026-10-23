# Script Enhance

Purpose: Claude suggests direction for an uploaded script. **It never changes the script's words** (Reed's rule). It only suggests:
- **Camera**: framing and moves ("Slow push-in on her face").
- **Movement**: what a character physically does ("Mia sets the cup down").
- **Reaction**: a beat or expression ("Mia's eyes widen").
- **Brand screen / product**: where a fomo screen or a product shows.

Suggestions sit under a script line until you decide. **Apply** writes the accepted ones into a new script version as *direction lines*; the script's own lines stay exactly as they were. Anything else Claude notices goes in **Notes** as plain sentences, which never edit anything.

## Desktop (1440): the script pane in Enhance mode
```
│ ✦ Enhance · 9 suggestions · 1 note  [Accept all ▾] [Apply 2 accepted]    │
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
| Accepted (not yet applied) | indented line in `--text-muted` with its kind label, no highlight; [Remove] undoes it |
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
- Accepting or rejecting doesn't change the script. Only **Apply N accepted** does: it saves a new version (source "enhanced") with the accepted directions added as lines before or after the line they belong to. Every existing line, dialogue included, stays exactly as it was.
- When suggestions are still pending, the helper under Apply says "Suggestions you haven't decided on are dropped." Apply shows the toast "Added 2 directions as v5. Undo", and Undo restores v4.
- Pressing [✦ Enhance] again while suggestions are pending asks "Replace the 4 waiting suggestions?".

## Direction lines (after Apply)
Applied directions must never look like dialogue or action, so they are written in a fixed form: `[Camera] Slow push-in on her face as she reads.` The tag is one of `[Camera]`, `[Movement]`, `[Reaction]` or `[Brand screen]`. The server adds the tag on Apply.
- The script view shows any line starting with one of these tags as a direction line: indented like a suggestion, `--text-muted`, with the tag shown as the kind label at the right. There is no highlight and no buttons.
- In Edit mode the tag stays as plain text, so editors can see it and delete the line if they want to.
- Breakdown reads these lines as directions for the shot, not as words to say or show on screen.
- Running: skeleton lines over the script + "Reading your script…". The Enhance button shows the cost.

## Phone (390)
The script fills the screen, and suggestions look the same (indented lines).
- Each suggestion shows its text full width, then a second line with the kind label and [Accept] [Reject] buttons (44px tall). Tapping the text opens a bottom sheet with the "Why". Apply sits in the toolbar.
- A "Notes (1)" chip in the toolbar opens the notes in the same sheet.
- Filter chips scroll sideways. Accept all lives in the ⋯ menu.

## Copy
- No suggestions: "This script already reads well. Nothing to suggest."
- Failure: "Enhance didn't finish. Your script is unchanged. [Try again]"
