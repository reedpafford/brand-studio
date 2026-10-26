# Brand Studio design system

Tokens: `web/src/styles/tokens.css` (light + dark). Screens: `screens/`. Preview of the tokens in both themes: `preview.html` (open in a browser) and `preview-1440.png`.

## Identity: "the cutting room"
A quiet, warm workroom where the **brand's** work is the colourful thing on screen, not our chrome.
- **Neutral, warm paper** (light) and **warm charcoal** (dark). No gradients, no glow, no violet.
- **One accent: deep teal** (`--accent`). Used for the one main action per area, links, focus and "selected". Never for decoration.
- **The brand's own colour** (`--brand`, set from the brand kit's first colour) shows in exactly two places: the 3px stripe under the top bar and the dot beside the brand name. That's how you always know which brand you're in.
- **Scripts look like scripts**: the script pane uses Courier Prime. Everything else uses Inter.
- Words over icons. Every icon button has a text label on desktop or a tooltip + `aria-label` on phone.

## Principles
1. **One main button per area.** Teal, bottom-right of a form or full-width at the bottom of a panel. Everything else is secondary (outlined) or ghost.
2. **Cost before click.** Any button that spends credits shows the cost inside it ("Generate · 34 credits") and, when disabled, the reason on the line below.
3. **Nothing happens by surprise.** Suggestions, enhancements and settings changes are previews until accepted. Destructive actions confirm and say what's lost.
4. **Status in words + colour**, never colour alone: "Rendering 42%", "Ready", "Failed · credits returned".
5. **Scan in one glance.** Lists are tables or tidy grids with the name first, status second, actions last. Max ~70 characters per line of prose.
6. **Plain words.** "Brand screens", not "assets". "Credits returned", not "refunded to ledger".
7. **Editors never see dollars.** Only the Usage page (owner) shows `$`.

## Type scale (Inter; numbers use `font-variant-numeric: tabular-nums`)
| Token | Size | Use |
|---|---|---|
| `--text-xs` | 12 | badges, timecodes, counters |
| `--text-sm` | 13 | helper text, table meta |
| `--text-base` | 15 (16 on phones) | body, inputs, buttons |
| `--text-md` | 17 / 600 | card and section titles |
| `--text-lg` | 22 / 600 | page titles |
| `--text-xl` | 28 / 600 | login headline, empty states |

Weights: 400 body, 500 labels and buttons, 600 titles. No 700+.

## Space, shape, layout
- 4px grid: `--space-1..7` = 4, 8, 12, 16, 24, 32, 48. Card padding 16 (phone) / 24 (desktop). Gap between fields 16.
- Radius: 6 inputs/chips, 10 buttons/cards, 16 dialogs/sheets. Not pills, except the credits meter.
- Desktop: top bar 56 + left sidebar 232 + content (max 1280). Phone (< 768): top bar 56 + bottom tab bar 64, single column, 16px side gutter.
- Breakpoints: `sm` 640, `md` 768 (sidebar appears), `lg` 1024 (two-pane studios appear), `xl` 1280.
- Touch targets ≥ 44px on phones; desktop controls are 36px tall (32 for compact table actions).

## Colour use
| Need | Token |
|---|---|
| Page / card / sunken area | `--bg` / `--surface` / `--surface-2` |
| Divider / input border | `--border` / `--border-strong` |
| Main action, selected, link, focus | `--accent` (+ `--on-accent` text) |
| Selected chip / active tab / info banner | `--accent-soft` + `--accent-text` |
| Ready, approved | `--success` on `--success-soft` |
| Over 75% budget, needs attention | `--warning` on `--warning-soft` |
| Failed, over budget, delete | `--danger` on `--danger-soft` |
| Pending script suggestion | `--mark` background, `--mark-line` underline |

All text pairs pass WCAG AA (4.5:1). `--text-faint` is for disabled states only.
Focus: 2px `--focus` outline, 2px offset, on every interactive element.

## Components (build these, nothing more until a screen needs it)
| Component | Notes |
|---|---|
| Button | `primary` (teal), `secondary` (surface + border), `ghost`, `danger`. Sizes 36 / 44 (phone). Optional cost chip inside: "· 34 credits". Busy state keeps width, shows spinner + "Generating…". |
| Icon button | 36 square, `aria-label` required, tooltip on hover. |
| Input, Textarea, Select | Label above, helper/counter on the right of the label row, error text below in `--danger`. |
| Segmented control | Aspect, resolution, Script/Shots on phone. |
| Chip | Filter and tag chips; selected = `accent-soft`. Removable variant with ×. |
| Badge | Status: neutral, success, warning, danger, accent. Always text. |
| Card | Surface, 1px border, radius 10, no shadow (shadow only when draggable). |
| Media tile | 9:16 / 1:1 / 16:9 thumbnail, status badge top-left, actions on hover (desktop) or ⋯ (phone). |
| Table | For team, screens list, usage. Becomes a stacked list on phones. |
| Tabs | Underline style, accent underline on active. |
| Dialog / Sheet | Centered dialog on desktop, bottom sheet on phones. |
| Popover / Menu | Brand switcher, model picker, ⋯ actions. |
| Toast | Bottom-centre, 4s, one line, optional Undo. |
| Banner | Inline, full width of its card: info / warning / danger. |
| Empty state | Headline (`--text-xl`), one line, one button. |
| Credits meter | Pill bar "412 / 660 credits · 62%". Teal < 75%, warning 75–100%, danger > 100%. |
| Dropzone | Dashed `--border-strong`, "Drop files or choose", accepted types + size limit in helper text. |
| Suggestion mark | See `screens/script-enhance.md`. |
| Skeleton | `--surface-2` blocks, no shimmer when reduced motion. |

Icons: lucide, 16px in controls, 20px in nav. Stroke 1.75.

## Fonts
Self-host via `@fontsource-variable/inter` and `@fontsource/courier-prime` (400, 700). No Google Fonts calls at runtime.

## Screens
| Screen | Spec |
|---|---|
| Login, setup, accept invite | `screens/login.md` |
| App shell + brand switcher + team | `screens/app-shell.md` |
| Brand kit + screens | `screens/brand-kit.md` |
| Character / place / prop library | `screens/library.md` |
| Quick clip | `screens/quick-clip.md` |
| Brief (new video) | `screens/brief.md` |
| Project workspace | `screens/project.md` |
| Script Enhance | `screens/script-enhance.md` |
| Breakdown | `screens/breakdown.md` |
| Storyboard | `screens/storyboard.md` |
| Clips, review, finished video | `screens/clips.md` |
| Approvals (owner) | `screens/approvals.md` |
| Usage (owner) and credits (editor) | `screens/usage.md` |

Each spec has: purpose, desktop wireframe (1440), phone wireframe (390), states, copy. Wireframes are layout only; spacing and colour come from the tokens.

## Review checklist (Designer uses this on web PRs)
1. Only tokens: no raw hex, no Tailwind palette colours (`bg-violet-500`), no px font sizes outside the scale.
2. Works at 1440 and 390, light and dark; no horizontal scroll on phones.
3. One primary button per area; spend buttons show cost; disabled buttons say why.
4. Visible focus; labels on every input; icon buttons have `aria-label`.
5. Editors see no `$` anywhere.
6. Empty, loading and error states exist and match the spec copy.
7. Can the user undo or delete what they just made? Every object a person creates has a way to remove it (delete or archive) and, after a delete or a big change, an Undo in the toast.
8. No dead ends (Reed, 2026-10-26): every blocking problem has a one-click fix on the same screen, unless the server repairs it for free or it's shown as Advice. Editing the raw prompt is never the only way out.
