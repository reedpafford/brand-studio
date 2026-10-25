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
| Empty | `Bell` icon. **Nothing waiting.** "When something needs you, editors see "Waiting for Reed to approve" and it shows up here." No button. |
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
- **Waiting invites:** email, role, "expires 31 Oct" (meta), **Copy a new link** (secondary dense, `Copy`, `aria-label="Copy a new link for jo@example.com"`) and **Cancel** (ghost dense). The server keeps only a hash of each link, so the old one can't be shown again: Copy a new link makes a fresh link and copies it, and the old link stops working. The label says so before the press. It becomes "Copied" with `Check` for 2 s, with the toast "Link copied. The old link no longer works."
- **Invite someone** opens a dialog (sheet on phone): **Email**, **Role** (select: Editor, Owner; Editor first), amber **Create invite link**. Then the dialog shows the link in a read-only field (`aria-label="Invite link"`) with **Copy link** and the meta line "Send this link to them. It works once and expires in 7 days." and **Done** (ghost). No toast while this panel is open: it already says it.

### Phone
- People and invites as stacked rows: the email (wrapping, never cut) and its meta line, then the buttons on a row under them. **Remove**, **Copy a new link** and **Cancel** are 44px. **Invite someone** in the action bar.

### States
| State | What shows |
|---|---|
| Only Reed | People shows Reed alone; under it: "Invite your editors so they can make videos." The amber button is the action. |
| No waiting invites | The section is hidden. |
| Loading | 2 row skeletons. |
| Error | Danger banner "Couldn't load the team. Check your connection." **Try again**. Invite errors in the dialog, in the server's words ("Someone with that email is already on the team."). |
| Success | Toasts: "Invite link made. Copy it and send it to Jo.", "Sam removed.", "Invite cancelled." |
