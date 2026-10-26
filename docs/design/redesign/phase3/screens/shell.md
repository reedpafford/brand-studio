# Shell: always on screen

## Desktop (≥ 1024)
```
┌ top bar 60 ───────────────────────────────────────────────────────────────────────┐
│ [● Iron Paws ⌄]                                          [🔔 Approvals 2]  (R)     │
├ rail 232 ────────┬ work area (max 1280, gutters 32) ───────────────────────────────┤
│ IRON PAWS        │                                                                  │
│ ▣ Videos       ◀ │  page                                                            │
│ ⚡ Quick clip    │                                                                  │
│ 👥 Cast & places │                                                                  │
│ 🎨 Brand         │                                                                  │
│ ──────────────── │                                                                  │
│ STUDIO           │   (Reed only)                                                    │
│ 🔔 Approvals   2 │                                                                  │
│ ＋👤 Team        │                                                                  │
└──────────────────┴──────────────────────────────────────────────────────────────────┘
```
- **Top bar.** 60px, `bg-bg`, 1px bottom border, sticky.
  - **Brand switcher** (left): a `secondary` button showing the brand dot (`--brand`), the brand name (700) and `ChevronDown`. It opens a menu listing every brand with its dot, a ✓ on the current one, and, for editors, "Brands are set up by Reed." in muted text at the bottom.
    - **Reed** gets a divider and **＋ New brand** (`Plus`) at the bottom instead (gaps #8). It opens a dialog (a sheet on phone):
      - **Brand name** (input, required), with the helper "You add its logo, colours and screens next."
      - The amber button is **Create brand**. When it's disabled: "Give it a name first". If the name is taken, the server's words show under the field ("A brand with that name already exists.").
      - After: the app switches to the new brand and opens its Brand page on **Look**. Toast: "{Name} is ready. Add its logo and colours." The new brand shows up on Usage straight away.
      - Archived brands aren't listed here.
  - Switching keeps the section. For example, Cast & places in fomo becomes Cast & places in Iron Paws. A video page goes to that brand's Videos.
  - **Approvals pill** (right, Reed only): `Bell` "Approvals" with an amber count when the count is above 0. It opens /approvals. When nothing is waiting, it shows plain "Approvals" with no count.
  - **Avatar** (44px, initial): opens the account menu:
    - Reed's name and email (muted)
    - **Team** (Reed only)
    - **Theme: Dark / Light / Match my device**, as three radio rows
    - divider, **Sign out**
- **Rail.** 232px, `bg-bg`, right border.
  - Eyebrow with the brand name, then the four brand sections. Items are 44px tall, with an icon and label.
  - Active item: `bg-surface-2`, text colour, a 3px amber bar on the left inside.
  - For Reed, a divider and the eyebrow "STUDIO", then Approvals (with count) and Team. Editors don't see this group.
- **Work area.** Max 1280px, gutters 32px, top padding 32px.
- **1024–1279.** The rail collapses to 72px icons only, each with a tooltip and `aria-label`.

## Phone (< 768)
```
┌ top bar 56 ─────────────────────────────┐
│ [● Iron Paws          ⌄]  [🔔²]  (R)     │
├──────────────────────────────────────────┤
│  page (gutters 16, bottom padding = bars)│
├ action bar 68 (only when a page has one)┤
│ [      Make the takes · 8 credits      ] │
├ tabs 64 + safe area ─────────────────────┤
│  ▣ Videos  ⚡ Quick clip  👥 Cast  🎨 Brand │
└──────────────────────────────────────────┘
```
- **Top bar.** 56px, with the brand switcher taking the free width.
  - The menu opens as a bottom sheet.
  - The bell is a 44px icon button with `aria-label="Approvals, 2 waiting"` and is shown for Reed only.
  - The avatar opens the account menu as a sheet.
- **Bottom tabs.** 4 tabs, each a 20px icon over an 11.5px label: **Videos · Quick clip · Cast · Brand**.
  - The active tab is amber.
  - The bar adds `env(safe-area-inset-bottom)`.
- **Action bar.** Sits above the tabs, `bg-surface`, top border, 12/16 padding. It holds the screen's one amber button at full width, with the reason line under it when disabled.
- **Page padding.** The page reserves `--tabbar-h + --actionbar-h + 16` at the bottom so the last item can scroll clear.
- **768–1023 (tablet).** Phone layout with a 2-column content grid.

## Shared overlays
- **Sheet (phone).**
  - From the bottom, radius 20 at the top, a grabber, title row (section, 17) and an `X` close button.
  - Height fits the content, at most 90dvh, and scrolls inside.
  - The sheet's own amber button sits at the bottom of the sheet.
- **Side panel (desktop).** From the right, 380px, full height below the top bar. Used for the Script and for editing a screen.
- **Dialog.** For confirmations only:
  - 420px, radius 20, a headline (24) and body (meta).
  - Buttons right-aligned: the ghost cancel ("Keep it") on the left, the action on the right.
  - Destructive actions use the `danger` button and say what's lost: "Delete the screen "Home"? Videos already made keep it."
- **Toast.**
  - Bottom centre on desktop, above the action bar on phones.
  - `bg-surface-3`, `shadow-raised`.
  - Icon (`Check` for success, `CircleAlert` for error), one line, optional **Undo** (ghost, dense).
  - It stays 4 seconds, or 8 with Undo, and pauses on hover or focus.
  - One live region (`role="status"`).
- **Focus.** Overlays trap focus. Escape closes them. Focus returns to the control that opened them.

## States
- **Loading the app:** the top bar and rail render at once, and the work area shows the page's skeleton. A blank page never shows.
- **Signed out:** goes to Sign in, and returns to the same page after signing in.
- **No connection:**
  - A warning banner at the top of the work area: "You're offline. Reconnect to keep working; nothing was lost."
  - Paid buttons are disabled with the reason "Offline".
- **No brands yet:** an empty state, "No brands yet" / "Reed adds brands. fomo and Iron Paws come with the studio."
