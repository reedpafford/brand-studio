# Writing steps 3, 4, 5 and 7: Directions, Variations, Cast, Publish

Step 3 (Directions) is #185's Suggest directions on its own step. Step 6 (Breakdown) is #186's editor, in a tab per version. Plan: `../workflow-v2.md`, decisions d, e, f and i. Mock: `variations.png`.

## 3. Directions (`?step=directions`, gaps #4)
#185's Suggest directions (`phase3/screens/video.md` §2), on its own step, working on version A. Reed's words never change: suggestions only add direction lines (camera, movement, reaction, brand screen).
- **Before:** one card, "Claude suggests camera moves, movement, reactions and where brand screens show. Your words never change." The amber button is **Suggest directions · N credits**; the step bar has a ghost **Skip this step**.
  - For an editor, the price counts towards the week. Past the allowance it's disabled, with the reason and the reset day.
- **While reading:** "Reading your script… 8 s", with skeleton marks under every third line.
- **Suggestions:** exactly as in `video.md` §2. They're marked lines with the kind label, **Accept** / **Reject** on each, **Accept all**, and notes in a card (desktop: a 320px right column). The amber button becomes **Add 2 directions**; with 0 accepted it reads "Accept at least one suggestion".
- **After adding:** toast "Added 2 directions. Undo". The step shows A with its direction lines (script font, direction lines in `text-muted` italics), plus **Suggest again · N credits** (ghost). **Next: Variations** comes back.
- **Variations** are written from A with its directions, so B and C start with them too.
- **States:** "This script already reads well. Nothing to suggest." (toast, and the step counts as done). If it fails: "Suggestions didn't finish. Your script is unchanged. Nothing was charged." **Try again**.
- **Server:** the project Enhance routes, but for a script version: `POST /scripts/{id}/drafts/0/enhance` (paid, estimate first), `GET …/suggestions`, `POST …/suggestions/{id}/accept|reject`, `POST …/apply`. The rule stays: the words never change.

## 4. Variations (`?step=variations`)
Up to two alternates of the script: the same high-level story, with scenes, beats, lines and the payoff changed slightly to fit. They're written together at one price, and each Regenerate is paid (decision d).

### Choose how many
At the top: "How many variations?" with a segmented control: **None · 1 · 2**.
- **None:** the amber button becomes **Next: Cast**, and the step shows "Skipped" in the picker.
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
- **Approve** for the version shown takes the action bar. Once every version is approved, the action bar shows **Next: Cast**.

### Next
**Next: Cast** is disabled until every kept variation is approved. Reason: "Approve or remove variation C first."

### States
| State | What shows |
|---|---|
| Error | "The variations didn't finish. Nothing was charged." **Try again** |
| Waiting | For Reed's own scripts, past the budget: the button reads **Ask Reed to approve · N credits**, as today. On editors' scripts, past the allowance: declined, "That's more than this week's 145 free credits." |
| Success | Toast "2 variations ready. Read them side by side." |

## 5. Cast (`?step=cast`)
Reed, 2026-10-25 (#197): once the script and its variations are approved, the app reads them and lists the **cast**. That's every named or recurring role, shared across all versions: main characters, helpers (a mentor or a coach), rivals, family. **Background people** (guests, crowds, extras) are never cast slots; they're made as part of each scene. One locked look per slot (decision e).

- **Roles fill in automatically (gaps #10):**
  - **Written by Claude** (Write with Claude or Write from the reference): the cast is found right after version A is written, as part of the same job. Its price is folded into the write's price, so the Script step's button already includes it. The meta under the button reads "Includes finding the roles."
  - **Imported from a reel:** filled free from the reel's breakdown, marked "From the reel" (`reel-import.md` §6).
  - **Variations:** a role that only appears in B or C is added when that variation is written, marked "In B only". Its price is folded into the variations' price.
  - **Pasted or uploaded scripts:** nothing is found on its own. When the step opens with no roles, it shows the card "Claude can find the roles in your script." with **Find roles in the script · N credits** (secondary, `Sparkles`; the step's amber stays **Next**, since every role is optional). Its price comes from the rates. For an editor it counts towards the week, and past the allowance it's disabled with the reason. Before version A is approved it's disabled with "Approve the script first".
  - While roles are being found: "Finding the roles… 6 s", with row skeletons.
  - Crowds, guests and extras are never roles. **＋ Add a role** always stays.
- **One row per slot,** in a single card divided by 1px borders:
  - **Role** (card): the name as written, e.g. "Mia".
  - **Kind** (badge): Main · Helper · Rival · Family.
  - **Description** (meta, 2 lines): "Late 20s, confident, says hell no at the altar."
  - **In** (meta): "In A, B and C".
  - **On the right:**
    - Locked: the look's 56px picture, its name, and `Lock` "Locked to Mia (Cast & places)", with **Change** and **Unlock** (ghost dense).
    - Unlocked: **Lock to a look** (secondary) and the meta line "Generated at Assets".
- **Lock to a look** opens a sheet (phone) or side panel (desktop) with two tabs:
  - **From Cast & places:** this brand's characters that have an approved sheet, as 9:16 cards with the name. A search field shows once there are more than 8. Picking one locks the slot to that sheet. Characters without an approved sheet are shown too, with "No approved sheet yet" (meta) and **Make sheet · N credits** (secondary) in place. It runs that character's house-style sheet from its photo, shows **Approve** / **Redo** in the same card, and approving locks the slot to it. Nothing opens in another page.
  - **Make one:** a name (filled with the role), a photo (optional), and the description (filled). Then **Make a look · N credits**, which runs the house-style sheet and comes back for **Approve**. Approving adds the character to Cast & places and locks the slot to it.
- **Editing the cast** (the owner, before publishing):
  - **＋ Add a role** (ghost): role name, kind and description.
  - Rename a slot: `Pencil` on the role.
  - Remove a slot: `Ellipsis` → **Remove role**, then the dialog "Remove Mia from the cast? She'll be made at Assets like a background person." with **Keep** and **Remove**.
  - **Find roles again · N credits** (ghost, `RotateCcw`) in the step bar, for after the script changes. It asks first: "Find the roles again? Locked roles stay locked; roles you added stay." A slot that the script no longer names is flagged "Not in the script any more" (warning), with **Remove**.
- **Every slot is optional.** Next is never blocked by unlocked slots. It's only blocked while a lock panel is open without a pick.
- **Done state:** "5 roles · 2 locked".
- **Phone:** stacked rows, with the lock button under the description at full width (44px).

**States:**
| State | What shows |
|---|---|
| No roles found | "Claude found no named roles. Everyone will be made at Assets." **＋ Add a role** |
| Finding failed | "The roles weren't found. Nothing was charged." **Try again** (free when it failed inside a write) |
| Success | Toast "Mia is locked. She'll look the same in every version." |

## 7. Publish (`?step=publish`)
- **One summary card per version,** in a grid: three columns on desktop, stacked on phone. Each card shows:
  - the letter and name, plus the first 4 lines in the script font
  - **Words:** `Check` "Approved"
  - **Cast:** role chips; locked ones show the look's picture and `Lock`, unlocked ones read "made at Assets"
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
- The script write (`POST /scripts/{id}/write`) and the variations write also find the roles, with the price folded into their estimates (gaps #10). They fill the slots unless the person already has some, and only add new ones.
- `POST /scripts/{id}/cast/read` (Find roles in the script) reads the roles from every approved version (a paid Claude call). It returns slots: `{id, role, kind, description, versions[]}`, with background people left out.
- `GET/POST/PATCH/DELETE /scripts/{id}/cast` for the slots (add, rename, remove).
- `PUT /scripts/{id}/cast/{slot_id}/lock {character_id, sheet_id} | null`.
- `POST /scripts/{id}/publish`. After it, every words, lock and variation change is refused.
