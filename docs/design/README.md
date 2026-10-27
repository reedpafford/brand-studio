# Brand Studio design

Look and tokens: `web/src/styles/tokens.css` (Screening room, dark by default; colours, type, space, radii). Rules, parts and screen specs: `redesign/phase3/README.md` and `redesign/phase3/screens/`. Newer flows: `redesign/workflow-v2/`. Older specs still in use: `screens/` (Approvals, Breakdown, Library, Quick clip, Script Enhance).

## Principles
1. **One main button per area.** Everything else is secondary or ghost.
2. **Cost before click.** A button that spends credits shows the cost inside it ("Generate · 34 credits") and, when disabled, the reason on the line below.
3. **Nothing happens by surprise.** Suggestions and settings changes are previews until accepted. Destructive actions confirm and say what's lost.
4. **Status in words and colour**, never colour alone.
5. **Plain words.** "Brand screens", not "assets". "Credits returned", not "refunded to ledger".
6. **Editors never see dollars.** Only owner pages show `$`.

## Review checklist (Designer uses this on web PRs)
1. Only tokens: no raw hex, no Tailwind palette colours (`bg-violet-500`), no px font sizes outside the scale.
2. Works at 1440 and 390, light and dark; no horizontal scroll on phones.
3. One primary button per area; spend buttons show cost; disabled buttons say why.
4. Visible focus; labels on every input; icon buttons have `aria-label`.
5. Editors see no `$` anywhere.
6. Empty, loading and error states exist and match the spec copy.
7. Can the user undo or delete what they just made? Every object a person creates has a way to remove it (delete or archive) and, after a delete or a big change, an Undo in the toast.
8. No dead ends (Reed, 2026-10-26): every blocking problem has a one-click fix on the same screen, unless the server repairs it for free or it's shown as Advice. Editing the raw prompt is never the only way out.
