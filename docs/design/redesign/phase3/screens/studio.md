# Studio (Reed only): Approvals and Team

Both pages live outside the brand: the rail shows the STUDIO group active, and the brand switcher stays as it was. Editors who open Approvals see "Page not found". Editors can open Team read-only (people and waiting invites, no Invite, Remove or Cancel); it is not in their account menu. Dollars appear on Approvals and nowhere else.

## Approvals (`/approvals`)
### Desktop
```
Approvals (page 32)   2 waiting · 135 credits ($11.79) (meta)           [Approve all · 135 credits]  amber
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ┌preview 96×170┐  ● Iron Paws · Bo tries salmon · Clip 3 redo             Sam · 2 min ago │
│ │  (frame or   │  27 credits ($2.36)                                                     │
│ │   prompt)    │  Takes the video to 118% of its budget                                  │
│ │              │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━│━━━━━  (danger past the line)             │
│ └──────────────┘  "Make the dog's tail move more." (what's wrong, if a redo)            │
│                                                              [Decline]  [Approve]       │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌preview┐  ● fomo · Quick clip · "Mia hits the buy moment…"                Sam · 1 h    │
│ │       │  68 credits ($5.94) · Sam's quick clips this week: 580 of 600                 │
│ └───────┘                                                    [Decline]  [Approve]       │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```
- **Rows**, newest first, in one card divided by 1px borders.
- **Preview** (left, in the work's shape): the frame the clip starts from, the storyboard frame being redrawn, the source photo for a sheet, or for Claude steps the `Sparkles` icon on `surface-2`. Tapping a preview opens it large.
- **Line 1:** brand dot + brand, the video (link) or "Quick clip", and what's asked for in words. Right: who and when (meta).
- **Line 2:** credits **and dollars**.
- **Line 3:** the effect in words, with a meter when a budget is involved.
- **Buttons:** **Approve** (secondary, `Check`) and **Decline** (ghost). Only **Approve all** is amber.
  - Approve acts at once: toast "Approved. Sam's clip is being made."
  - Decline asks first, in a dialog: "Decline Sam's clip 3 redo? Nothing is charged. Sam can ask again." **Keep it** / **Decline** (danger). Toast: "Declined. Nothing was charged."
  - **Approve all · N credits** asks first: "Approve 2 requests for 135 credits ($11.79)?" **Keep them** / **Approve all** (amber).

### Phone
- Title "Approvals" (page 26) with "2 waiting · 135 credits" under it.
- One card per request: preview at the top (full width, max 200px tall, cropped), then the lines, then **Decline** and **Approve** side by side, 44px.
- **Approve all · N credits** in the action bar.

### States
| State | What shows |
|---|---|
| Empty | `Bell` icon. **Nothing waiting.** "Editors are never sent here any more: past a budget or their week, their button gives the reason. Requests from before 26 Oct show here until they're handled." No button. |
| Loading | 2 row skeletons with a preview block. |
| Error | Danger banner "Couldn't load approvals. Check your connection." **Try again**. A failed approve: toast "Couldn't approve. Nothing was charged. Try again." |
| Success | Approved rows leave with a 160ms fade; the count in the top bar updates. When the list empties: the empty state plus toast "All done." |

## Team (`/team`, also from the account menu)
### Desktop (one column, max 720)
```
Team (page 32)                                                    [Invite someone]  amber
People (section)
┌──────────────────────────────────────────────────────────────────────┐
│ (R) Reed · reed@example.com                                  Owner   │
│ (S) Sam  · sam@example.com                       Editor  [Remove]    │
└──────────────────────────────────────────────────────────────────────┘
Waiting invites (section)
┌──────────────────────────────────────────────────────────────────────┐
│ jo@example.com · Editor · expires 31 Oct  [Copy a new link] [Cancel]│
└──────────────────────────────────────────────────────────────────────┘
```
- **People:** 44px avatar (initial), name (body 600), email (meta), the role as a neutral badge ("Owner", "Editor"). **Remove** (ghost dense, `aria-label="Remove Sam"`) opens the danger dialog: "Remove Sam from the team? Their videos stay." **Keep them** / **Remove**.
  - **After removing:** toast "Sam removed." with **Undo** (8 s). Undo puts Sam back with the same role and password (`POST /team/members/{id}/restore`).
  - **Change role** (gaps #16, Reed only): each other person's row has an `Ellipsis` menu (44px on phone) with **Make owner** or **Make editor**, and **Remove** moves into the same menu.
    - Make owner asks first: "Make Sam an owner? Owners see dollars, approve spending, and manage the team." **Keep as editor** / **Make owner**.
    - Make editor asks first: "Make Jo an editor? Jo stops seeing dollars and can't manage the team." **Keep as owner** / **Make editor**.
    - After: the badge changes, with the toast "Sam is now an owner." and **Undo** (it sets the old role back).
    - Reed's own row has no menu, because nobody can change their own role (the server refuses it: "You can't change your own role."). So there's always at least one owner.
  - **Removed people** (gaps #16): a ghost **Show removed (2)** under People, only when there are any (`GET /team/members?removed=true`). Open, it lists each removed person muted, with "Removed {date}" (meta) and **Restore** (secondary dense, 44px on phone). Restore gives the toast "Sam is back on the team."
- **Waiting invites:** email, role, "expires 31 Oct" (meta), **Copy a new link** (secondary dense, `Copy`, `aria-label="Copy a new link for jo@example.com"`) and **Cancel** (ghost dense). The server keeps only a hash of each link, so the old one can't be shown again: Copy a new link makes a fresh link and copies it, and the old link stops working. The label says so before the press. It becomes "Copied" with `Check` for 2 s, with the toast "Link copied. The old link no longer works."
- **Invite someone** opens a dialog (sheet on phone): **Email**, **Role** (select: Editor, Owner; Editor first), amber **Create invite link**. Then the dialog shows the link in a read-only field (`aria-label="Invite link"`) with **Copy link** and the meta line "Send this link to them. It works once and expires in 7 days." and **Done** (ghost). No toast while this panel is open: it already says it.

- **Credit limits** (Reed only, gaps #9): a card above People.
  ```
  Credit limits (section)
  Editors' weekly allowance   [ 145 ] credits   ≈ $14.91 a week (meta)
    Free generation for each editor's own scripts and quick clips. Resets on Monday.
  Most one video can cost     [ 729 ] credits   ≈ $74.94 (meta)
    For everyone, Reed too. A video's budget is twice its estimate, up to this.
                                              [Save limits]  (secondary)
  ```
  - Two number inputs (`inputmode="numeric"`, whole credits, 120px). The dollars beside them use the credit rate (1 credit = $0.1028), and they update as Reed types. Only Reed ever sees this card, and only he sees dollars here.
  - **Save limits** is secondary, because **Invite someone** stays the page's amber button. It's disabled until something changes, with the reason "No changes yet".
  - Checks under each field: "Use a whole number of credits.", "The weekly allowance can be 0 or more.", "The cap needs to be at least 1 credit."
  - Lowering the allowance below what an editor has used this week asks first: "Sam has used 120 credits this week. With 100, Sam can't make anything more until Monday." **Keep 145** / **Save 100**.
  - After: toast "Limits saved." with **Undo** (it saves the old values back). Editors' meters and stop reasons use the new numbers on their next load.
  - The existing per-editor allowance rows (#228) stay under People, and now read against the new allowance.
  - Server: `GET /credits/limits` and `PUT /credits/limits {weekly_quick_clip_credits, per_video_max_credits}`. Both fields are always sent.

### Phone
- The Credit limits card comes first. Each field takes the full width, with its dollars and helper under it, and **Save limits** is full width at 44px.
- People and invites as stacked rows: the email (wrapping, never cut) and its meta line, then the buttons on a row under them. **Remove**, **Copy a new link** and **Cancel** are 44px. **Invite someone** in the action bar.

### States
| State | What shows |
|---|---|
| Only Reed | People shows Reed alone; under it: "Invite your editors so they can make videos." The amber button is the action. |
| No waiting invites | The section is hidden. |
| Loading | 2 row skeletons. |
| Error | Danger banner "Couldn't load the team. Check your connection." **Try again**. Invite errors in the dialog, in the server's words ("Someone with that email is already on the team."). |
| Success | Toasts: "Invite link made. Copy it and send it to Jo.", "Sam removed.", "Invite cancelled." |
