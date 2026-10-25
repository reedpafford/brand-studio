# Usage (owner) and credits (editor)

> Replaced by `docs/design/redesign/phase3/screens/usage.md` (the brand tracker, 2026-10-25). Kept for history.

Rule: 1 credit = 1 s of 480p video. Editors see credits and % of budget only. The owner sees dollars, only on this page.

## Credits meter (everyone, project header and Projects cards)
```
[━━━━━━━━━━━━━━━━━━━━━━━━━──────────────]  412 / 660 credits · 62%
```
Pill, 8px tall bar + label. Colour: `--accent` < 75%, `--warning` 75–100% ("Almost at budget"), `--danger` > 100% ("Over budget · Reed approved +120"). Hover/tap shows: "Budget is 2× the 480p estimate (330 credits). Used 412. Waiting to render 34."
Phone: header shows only "62%" with a small ring; tap opens the same detail in a sheet.

## Over-budget approval
When an action would cross 100%: button reads "Ask Reed to approve · 120 credits". Dialog: "This takes the project to 118% of its budget. Reed needs to approve." Optional note, [Send request]. The project shows a warning banner "Waiting for Reed to approve 120 credits." The owner decides on the Approvals page (`approvals.md`).

## Usage page (owner only, `/usage`; editors who open it get 404 text "Page not found")
```
│ Usage                       [This week ▾]  [All brands ▾]                 │
│ ┌ Spent ────┐ ┌ Credits ───┐ ┌ Test cap ────────┐ ┌ Approvals ──┐       │
│ │ $11.40    │ │ 1,284      │ │ $11.40 of $15    │ │ 1 waiting   │       │
│ └───────────┘ └────────────┘ └──────────────────┘ └─────────────┘       │
│ By project                                                                │
│ Project            Brand     Credits  Budget %   $       Last used        │
│ Mia buys the dip   ● fomo    412      62%        $3.62   today            │
│ Paws launch        ● Iron P  880      104% ⚠     $7.78   yesterday        │
│ By job (latest 50)                                                         │
│ When   Who   Kind   Model        Credits   $      Status                  │
```
Numbers right-aligned, tabular. Test cap card turns warning at 75%, danger at 100%.
Phone: the 4 stat cards in a 2×2 grid; tables become stacked rows (Project name, then "412 credits · 62% · $3.62").
