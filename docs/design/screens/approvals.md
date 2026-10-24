# Approvals (owner only)

Purpose: one place where Reed decides on everything that's waiting. Owner-only route `/approvals`. Editors who open it get "Page not found". The owner sees a count badge on **Approvals** in the top nav and in the phone's More menu.
API: jobs with `status = needs_owner_approval` → `POST /jobs/{id}/approve`, or decline with `POST /jobs/{id}/cancel`.

## What waits here
1. **Work that goes past a project's budget** (2× the 480p estimate): a clip, frame or Claude step that would take the project over 100%.
2. **Quick clips past an editor's weekly allowance.**

Planned length needs no approval. A plan whose budget would go over the per-video cap ($75) is refused when the project is made, with the reason under the length field (see `brief.md`), so it never waits here.

## Desktop (1440)
```
│ Approvals · 2 waiting                                                    │
│ ┌──────────────────────────────────────────────────────────────────────┐ │
│ │ ● fomo · Mia buys the dip · clip c3 redo           asked by Sam, 2m  │ │
│ │ 27 credits ($2.36) · takes the project to 118% of its budget          │ │
│ │ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│━━━━ (danger) │ │
│ │                                         [Decline]  [Approve]           │ │
│ ├──────────────────────────────────────────────────────────────────────┤ │
│ │ ● fomo · Quick clip · "Mia hits the buy moment…"      asked by Sam   │ │
│ │ 68 credits ($5.94) · Sam's quick clips this week: 580 of 600          │ │
│ │                                         [Decline]  [Approve]           │ │
│ └──────────────────────────────────────────────────────────────────────┘ │
```
- Rows are newest first and grouped by nothing: it's one list.
- **Each row shows:**
  - brand dot + brand, the project (linked), and what's being asked for
  - who asked and when
  - the cost in credits **and dollars**, since this page is owner-only
  - the effect in words, plus a meter where a budget is involved
- **Approve** is the primary button and **Decline** is secondary. Both act at once and show a toast: "Approved. Sam's clip is rendering." / "Declined. Nothing was charged." Decline can't be undone (the editor can ask again), so it asks first: "Decline Sam's clip c3 redo?"
- **Empty:** "Nothing waiting. Editors will see 'Waiting for Reed to approve' when something needs you."

## Phone (390)
- One card per row at full width, with the meter under the cost line.
- **Approve** and **Decline** are full-width buttons side by side, 44px tall.
- Approvals is reached from **More**, with the count badge also on the More tab.

## Editors' side (for reference)
Anything waiting shows "Waiting for Reed to approve" in a warning badge where it was asked for (Quick clip history, project card, clip card). Editors never see dollars.
