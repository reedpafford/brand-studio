# Change it in plain English: stills and clips

Reed, 2026-10-26: plain-English changes become the main way to fix a still or a clip on the video page. The person says what should change; the app rewrites that prompt and makes it again, shows what the note changed, and keeps the old one. Editing the prompt by hand moves to **Advanced**. After a cast change, stills are redrawn on their own within the budget (§3). This updates `video-flow.md` §3 Storyboard and §4 Clips, and replaces the Redo note in `phase3/screens/video.md` §4 and §5 on new videos.

## 1. Change this… (each still and each clip)
A box under every still (Storyboard) and every clip take (Clips), always visible. It's not hidden behind a Redo button.
```
┌ [still or take, in the video's shape]                         ┐
│ Clip 2 · 6 s                                     [Approve ✓]   │
│ Change this…                                                   │
│ ┌──────────────────────────────────────────────┐               │
│ │ What should change?                          │  [Change it · 6 credits] │
│ └──────────────────────────────────────────────┘               │
│ Advanced: edit the prompt (ghost link)          Earlier: 1     │
└────────────────────────────────────────────────────────────────┘
```
- **The box:** label "Change this…" (meta), a 2-row textarea with the placeholder "What should change?" (e.g. "Bo should look surprised, not sad"), up to 500 characters.
- **The button:** **Change it · N credits** (secondary, `Wand2`), with the price inside. N covers rewriting the prompt and making the still or take again, rounded up.
  - On a still it's the still's price. On a clip, before any take, it rewrites the prompt only (1 credit); once there's a take, it rewrites and makes a new take (e.g. "Change it · 27 credits").
  - Disabled reasons, first that applies: "Say what should change", "This one is still being made", "Write the clip prompts again first" (stale), and for an editor past the week: "That's more than this week's 145 free credits (140 used). It resets on Monday." There's no Ask Reed, and editors never see dollars.
- **Phone:** the box and button are full width and stacked, 44px. The box stays visible under each card.
- **The step's amber button doesn't change.** Change it is secondary, so the screen keeps one amber button (Next, Make the takes, and so on).

**While it runs:** the button is busy ("Changing… 8 s"). The card shows the old picture with "Making the change…" over it, and the box is read-only.

**After it lands:**
- The new still or take is shown and picked. The previous one stays as an earlier take ("Earlier: 2", the same ‹ › as today), so nothing is lost.
- Toast: "Changed. The earlier one is kept." with **Undo** (8 s). Undo picks the earlier one again and puts its prompt back. It's free, and the credits used stay used.
- **What the note changed** shows under the card, open, until the person approves it or writes another note:
  ```
  What your note changed (meta)
  Before: …Bo looks ~~sad and drops his ears~~ at the bowl…
  After:  …Bo looks **surprised, ears up,** at the bowl…
  [Show the whole prompt] (ghost dense)
  ```
  - It shows only the changed words, with about five words around each, at most three snippets. Removed words are struck through in `text-danger`, and added words are bold on `success-soft`. "Before:" and "After:" are written out, so it never relies on colour alone.
  - If nothing in the prompt changed (the model kept it), it says "Your note didn't change the prompt. Try saying it another way." Nothing new is made, and nothing is charged.
- An approved still or clip loses its approval when it's changed (the new one needs Approve).

**Notes can never change dialogue.** The spoken lines stay exactly as written.
- Before anything is charged, the server checks the note. That check already exists for clip Redo notes. If the note asks to add, cut, reword or quote a line, or to give a line to someone else, nothing is made. A `warn` line shows under the box, in the server's words, e.g. "The note changes what's said. The spoken lines stay exactly as written; say how they should sound instead (louder, angrier, slower)."
- The note stays in the box so it can be edited. Nothing was charged, and the toast stays quiet.
- To change the words, the person goes to the script. The hint under the box reads "To change the words, edit the script." with **Open script** (ghost dense).

**Advanced: edit the prompt** (ghost dense link, `Pencil`): it opens the prompt as a textarea with **Save** / **Cancel**, as **Edit** does today. On a clip before takes, saving counts as Looks good. Saving doesn't make anything; the still or take is made with **Change it** or the step's button.

**Make another (same prompt):** for a plain retry, the card's `Ellipsis` menu has **Make another · N credits**. It's the old Redo, with no note.

## 2. Cast mismatch in the breakdown
The breakdown check spots a shot whose cast doesn't match who the script has in it. It shows as a problem (danger row, decision h), in the video's Breakdown and the writing flow's plan (`variations-characters-publish.md` §6):
- "Shot 1.1: the script has Nate proposing, but the shot shows Mogging BF." with **Go to**.
- When there are several, one line per shot, plus one fix for all of them under the problem list: **Put the right cast in each shot** (secondary, `Users`). It's free, so it has no price, and the meta line under it reads "Free. Uses who the script names in each line."
- **After:** each shot's cast is set from the script's lines (the speaker, and anyone the action names). The problems go, and the toast says "Cast fixed in 2 shots." with **Undo** (it puts the old cast back).
- If a shot names someone with no character yet, that shot keeps its problem: "Shot 2.3: Nate has no look yet." with **Go to Assets**.
- It blocks Next like any other problem, and it can be kept anyway like any other problem.

## 3. Stills after a cast or breakdown change
When the cast changes on Assets (a look is picked, swapped or made), or a breakdown change touches a shot's cast or action, the affected frames are rewritten, and their stills are redrawn on their own (Reed, 2026-10-26). The redraw is paid, but only within what the video can spend.
- **Frames** (the words for each still) are rewritten straight away, free.
- **Stills** drawn from the old frames are redrawn automatically, when the money allows:
  - On Reed's library versions, the redraw has to fit inside the video's budget.
  - On an editor's own script, it has to fit inside the editor's week. Editors never see dollars, and there's no Ask Reed.
- **While it runs:** those stills show "Redrawing for the new cast…" over the old picture.
- **After it lands:**
  - A note (`Info`) at the top of Storyboard says "Redrew 2 stills for the new cast · 6 credits". The step's credit line counts the 6 credits.
  - Each redrawn still gets the badge "Redrawn" (neutral, `RotateCcw`) and loses its approval, so it needs **Approve** again. The badge goes once it's approved.
  - The old picture stays as an earlier version ("Earlier: 1"), and picking it back is free.
  - On the step the person was on (Assets or Breakdown), the toast says "Redrew 2 stills for the new cast · 6 credits." with **Go to Storyboard** (ghost dense).
- **When the budget or week can't cover it:**
  - Nothing is redrawn, and nothing is charged. The stills keep their old picture with the badge "Out of date" (warning).
  - The note at the top says why, in plain words. On a library version: "Frames rewritten for the new cast. 2 stills still show the old cast: redrawing them (6 credits) would go over this video's budget." On an editor's own script: "…would go over this week's 145 free credits. It resets on Monday."
  - The step's amber button becomes **Redraw 2 stills · 6 credits**. It's disabled with that reason while it still can't be covered. For Reed past the budget, it reads **Ask Reed to approve · 6 credits** as elsewhere, which on his own versions is his own approval.
- **Takes already made aren't touched.** Their clips get "Out of date" as today.

## Data the screens need (server)
- **Change a still:** `POST /projects/{id}/storyboard/frames/{frame_id}/change` `{note}` rewrites the frame's prompt from the note (Claude), then draws it. It returns the job plus `{before, after}` prompt text. It refuses with 422 (nothing charged) when the note touches dialogue, and the estimate gives the price.
- **Change a clip:** `POST /projects/{id}/clips/{clip_id}/change` `{note}` does the same for the clip prompt. With a take it makes a new take; without one it only rewrites the prompt. The dialogue check is the one in `check.redo_note`.
- **Undo:** picking an earlier still or take also restores its prompt (`POST …/pick` with the take or render id).
- **Unchanged prompt:** when the rewrite returns the same prompt, nothing is made and nothing is charged; the reply says `unchanged: true`.
- **Cast fix:** `POST /projects/{id}/breakdown/fix-cast` (free) and the same on `/scripts/{id}/drafts/{slot}/breakdown/fix-cast`. It returns the shots it changed, so Undo can put them back.
- **Frames after a cast change:** when `PUT /projects/{id}/assets` or a breakdown save changes a shot's cast, the server rewrites the frames (free) and queues a redraw of their stills, if the budget (or the editor's week) covers it. The storyboard reply carries `redrawn_for_cast: {count, credits}`, or, when it couldn't be covered, `stale: true` on each still plus `redraw_refused: {count, credits, reason}` in plain words.
