# Writing steps 4, 5 and 7: Variations, Characters, Publish

Step 3 (Directions) is #185's Suggest directions on its own step. Step 6 (Breakdown) is #186's editor, in a tab per version. Plan: `../workflow-v2.md`, decisions d, e, f and i. Mock: `variations.png`.

## 4. Variations (`?step=variations`)
Up to two alternates of the script: the same high-level story, with scenes, beats, lines and the payoff changed slightly to fit. They're written together at one price, and each Regenerate is paid (decision d).

### Choose how many
At the top: "How many variations?" with a segmented control: **None · 1 · 2**.
- **None:** the amber button becomes **Next: Characters**, and the step shows "Skipped" in the picker.
- **1 or 2:** an optional **Direction** field (textarea, 2 rows, placeholder "e.g. swap the altar for a car showroom; keep the payoff about money"). Then the amber button **Write {n} variation(s) · N credits**.
- **For an editor on their own script:** the step opens on **None**, with the line "Optional. Most scripts go out as one version." (decision f).
- **Writing:** column skeletons, plus "Writing 2 variations… 14 s".

### Side by side
**Desktop (≥ 1024):**
- Two or three columns: **A · Original** · **B** · **C**. Each is at least 360px wide; with three columns they share the work area.
- The columns scroll together, and their scenes line up by scene heading.
- **Column header:**
  - the version letter and name ("B · Variation"), with a status badge: Draft · Approved (`Check`, success) · Writing…
  - the line "What changed: car showroom instead of altar; new payoff line" (meta, 2 lines)
- **Body:** the script in the script font, with line numbers. Lines that differ from A are marked `bg-mark` with the 2px `mark-line` underline, the same marks as Directions.
  - A "Changes only" toggle (a switch in the step bar) collapses the unchanged lines to "· 6 unchanged lines ·".
- **Column footer:**
  - while it's a draft: **Approve** (secondary, `Check`), **Edit** (ghost, `Pencil`) and **Regenerate · N credits** (ghost, `RotateCcw`)
  - after approval: `Lock` "Approved · words final" (meta) and **Undo approval** (ghost). Undo disappears once the script is published (decision i).
- **Original (A):** already approved in step 2 and isn't edited here. Its footer reads "Your script · words final" with `Lock`.
- **Edit:** turns the column's body into a textarea in the script font, with **Save** (amber in the column) and **Cancel**. Saving keeps it a draft, so it still needs Approve.
- **Regenerate:** asks "What should change? (optional)" inline under the footer, then **Regenerate · N credits**. The old text stays until the new text arrives. Its older texts sit in a small "Earlier: 2" menu, so one can be brought back.
- **Remove:** in the column header's `Ellipsis` menu, **Remove variation C**. A dialog asks "Remove variation C? It won't be made." with **Keep it** and **Remove** (danger).

**Phone and tablet (< 1024):**
- A segmented control **A · B · C** under the step bar shows one version at a time.
- **Changes only** sits in the step bar's `Ellipsis` menu.
- The column footer's buttons sit in a row under the text, at 44px.
- **Approve** for the version shown takes the action bar. Once every version is approved, the action bar shows **Next: Characters**.

### Next
**Next: Characters** is disabled until every kept variation is approved. Reason: "Approve or remove variation C first."

### States
| State | What shows |
|---|---|
| Error | "The variations didn't finish. Nothing was charged." **Try again** |
| Waiting | For Reed's own scripts, past the budget: the button reads **Ask Reed to approve · N credits**, as today. On editors' scripts, past the allowance: declined, "That's more than this week's 145 free credits." |
| Success | Toast "2 variations ready. Read them side by side." |

## 5. Characters (`?step=characters`)
One locked look per character (decision e). Locked means the sheet is used as-is in every version. Unlocked means the editor makes or picks a look at Assets.
- **The list:** one row per character found in any version's script. Characters are matched to Cast & places by name; unmatched names show **Add to Cast** (secondary), which opens the new-character sheet with the name filled in.
- **Each row:**
  - a 56px picture (the approved sheet's front, else a `User` icon on `surface-2`)
  - the name (card)
  - which versions it's in ("In A, B and C", meta)
  - on the right, a **Lock look** switch (44px)
- **Switch on:**
  - A sheet picker opens under the row, showing this character's approved sheets as 9:16 thumbnails. Picking one draws a 2px amber ring.
  - When only one approved sheet exists, it's picked for you.
  - The row then reads `Lock` "Locked · this look in every version".
- **Can't lock:** with no approved sheet, the switch is disabled with the reason "Bo needs an approved sheet to lock a look", plus **Open Bo** (ghost). That opens the character page and comes back here (`?back=`).
- **Switch off:** "The editor makes or picks a look at Assets."
- Every character must be decided, but "not locked" counts as decided. So **Next** is never blocked by locks; it's only blocked while a sheet picker is open without a pick ("Pick a look for Bo, or turn Lock off").
- **Phone:** rows stacked, with the switch on the right. The sheet picker scrolls sideways inside itself with a fade.

## 7. Publish (`?step=publish`)
- **One summary card per version,** in a grid: three columns on desktop, stacked on phone. Each card shows:
  - the letter and name, plus the first 4 lines in the script font
  - **Words:** `Check` "Approved"
  - **Characters:** picture chips, with `Lock` on locked ones
  - **Breakdown:** "Planned · 28 s · 4 clips", or "Runs when an editor starts"
  - **Estimate:** "About 210 credits to make" (meta)
- **Above the cards:** "Publishing makes these versions ready to make. After that their words can't change. To change one, duplicate the script." (meta, with `Info`).
- **The amber button:** **Publish {n} versions**, then a confirming dialog: "Publish 3 versions of Bo tries salmon? Their words become final." with **Not yet** and **Publish**.
- **For an editor's own script:** the same. Publishing makes it visible in the library to everyone (decision f). The secondary **Add a variation** goes back to step 4.
- **Success:** go to the library with the toast "Published. 3 versions are ready to make." The row is outlined in amber for 1.5 s.
- **Already published** (opened from the library): this read-only page, with `Lock` "Published · final" and **Duplicate script** (secondary).

## Data the screens need (server)
- `POST /scripts/{id}/variations {count, direction?}` writes them as one job at one price.
- `POST /scripts/{id}/versions/{letter}/regenerate {note?}` is paid.
- `PUT /scripts/{id}/versions/{letter}` edits the words while the version is a draft.
- Approve and unapprove per version, and delete for a variation.
- The earlier texts of a version, to bring one back.
- `GET /scripts/{id}/characters` returns the names found, matched to the library, with sheets.
- `PUT /scripts/{id}/locks {character_id: sheet_id | null}`.
- `POST /scripts/{id}/publish`. After it, every words, lock and variation change is refused.
