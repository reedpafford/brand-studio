# No dead ends: a one-click fix for every blocking problem

Reed, 2026-10-26 (DECISIONS #520; review checklist item 8 in `docs/design/README.md`): every blocking problem has a one-click fix on the same screen, unless the server repairs it for free or it's shown as Advice. Editing the raw prompt is never the only way out. This adds to `video-flow.md` §1 to §4 and `change-notes.md`.

## Rules for every fix button
- **Where:** on the problem's own row or card, right after the problem's words. It's never only on another step.
- **Style:** secondary dense (44px on phone), with an icon. The step's one amber button doesn't change.
- **Free fixes** show **Free** in meta beside the button, and no price inside it (README rule 2). Paid fixes keep the price inside the button, rounded up to whole credits.
- **Undo:** each fix that changes something gives the toast "{What was done}." with **Undo** (8 s), and Undo puts back exactly what it changed (checklist rule 7).
- **Repaired on its own:** when the server fixes a problem itself, a note (`Info`, meta) says what it did, in one line, with **Undo**. The problem is gone, so nothing blocks.
- **Keep it anyway** (ghost) stays next to the fix wherever it's offered today.

## 1. Breakdown
Each problem row gets a fix next to **Go to**:

| Problem | Fix (free) | What it does |
|---|---|---|
| A script line is missing from every shot: "Line 7 isn't in any shot." | **Add it to a shot** (`Plus`) | Puts the line in the shot that holds the lines around it, or a new shot after them. |
| A line was changed: "Shot 2.1 says 'see you later', but the script says 'see you soon'." | **Use the script's words** (`RotateCcw`) | Puts the script's exact line back in the shot. |
| Shots with nothing to cover them: "Shot 3.2 has no line and no action." | **Remove this shot** (`Trash2`) | Removes the shot. Undo brings it back where it was. |

- **Several of the same kind:** one fix for all of them under the problem list, e.g. **Fix 3 problems** (secondary, `Wand2`) with "Free" beside it. The cast fix (`change-notes.md` §2) stays as it is.
- **Repaired on its own:** when the breakdown is made or saved, the server may put missing or changed lines back itself. The note at the top reads "Put back 2 lines that were missing from the shots." with **Undo**.
- **The other steps' disabled reason** names the Breakdown step and links there. "Fix the 2 problems in Shots first" becomes **"Fix 2 problems in Breakdown first"**, where "Breakdown" is a link (ghost dense) that opens the step with the first problem outlined for 1.5 s. One problem reads "Fix 1 problem in Breakdown first". It's used on Next, the step picker and Make storyboard alike (`web/src/projects/steps.ts`).

## 2. Edit shot
When a shot names a character, place or screen the video doesn't have ("Shot 1.3 names Nate, who isn't in this video's cast."):
- **The problem row** in the Edit shot panel has **Remove Nate from this shot** (secondary dense, `UserMinus`; `MapPinOff` for a place, `MonitorOff` for a screen), with "Free" beside it.
- **After:** the name goes from the shot's cast (or place, or screens), and the shot's action is left as written. Toast: "Removed Nate from shot 1.3." with **Undo**.
- If the name is a role in the script's cast with no look yet, the row also has **Go to Assets** (the look gets made there), and the remove button stays.
- **Repaired on its own:** when the server removes an unknown name itself, it's shown as Advice, never as a problem: "Advice: Removed Nate from shot 1.3. Nobody by that name is in this video." It sits under **Advice (N)** like any advice, with **Undo** in place of Keep anyway.

## 3. Assets
When a slot points at a Cast & places character that was deleted:
- **The card** shows the role with the badge "Character deleted" (danger), and "The character this role used was deleted from Cast & places." (meta).
- **Two fixes, side by side:** **Make a look · up to N credits** (secondary, `Wand2`, with "Usually 2. Anything not used comes back." under it) and **Pick another** (secondary, `Users`, with "Free" beside it), which opens the same picker as **Use a Cast & places character**.
- Past a limit, an editor's **Make a look** is disabled with its reason underneath, as elsewhere. **Pick another** is always there, so the editor is never stuck.
- The slot blocks Next ("Nate needs a look") until one of them is done.

## 4. Storyboard frames
When a frame's prompt is refused or flagged as too strong ("This frame may be refused: it shows a weapon pointed at someone."):
- **Repaired on its own:** if the server softened the prompt itself before drawing, the card shows the note "We softened this frame so it can be drawn." with the Before/After from `change-notes.md` §1 ("What changed", only the changed words, Before: and After: written out), and **Undo** (it puts the old prompt back, and the problem with it).
- **Otherwise:** the problem row has **Soften it** (secondary dense, `Feather`), with "Free" beside it. It rewrites only the flagged part and shows the same Before/After. It doesn't draw; the still is drawn with **Change it** or the step's button. Toast: "Softened. The earlier prompt is kept." with **Undo**.
- **Change this…** stays under the card for anything else.

## 5. Clips
Any clip card with a blocking problem (refused, flagged or failed check) has **Fix this clip's prompt** (secondary dense, `Wand2`), with "Free" beside it:
- It's always shown while the problem blocks, including for an editor past their week or budget, since it costs nothing.
- It rewrites the clip prompt to clear the problem (it never touches the spoken lines), and shows the Before/After. **Looks good** is cleared, so the new prompt is read again. It doesn't make a take.
- **After:** toast "Fixed clip 2's prompt." with **Undo**. If the rewrite can't clear it: "We couldn't fix this one. Try saying what should change in Change this…", and the problem stays with **Keep it anyway**.
- A stale clip keeps its own **Rewrite this clip's prompt · N credits** (`video-flow.md` §4); this button is for problems, not for staleness.

## Data the screens need (server)
- **Breakdown fixes (free):** `POST /projects/{id}/breakdown/fix {problem_ids?}` (all when empty) and the same under `/scripts/{id}/drafts/{slot}/breakdown/fix`. Each problem carries `fix: {kind: "add_line" | "restore_line" | "remove_shot", label}` or `fix: null`. The reply lists what changed so Undo can put it back; the breakdown reply carries `auto_repaired: [{text}]` for the note.
- **Edit shot:** `POST /projects/{id}/shots/{shot_id}/remove-ref {kind, name}` (free), with its Undo; an automatic removal comes back as an advice line.
- **Assets:** each slot carries `library_deleted: bool`.
- **Frames:** `POST /projects/{id}/storyboard/frames/{frame_id}/soften` (free) returns `{before, after}`; a frame softened on its own carries `softened: {before, after}`.
- **Clips:** `POST /projects/{id}/clips/{clip_id}/fix` (free, never charged, never refused for money) returns `{before, after}` or `{fixed: false, reason}`.
- Every fix route refuses with the reason in plain words, never a raw id.
