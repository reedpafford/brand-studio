# Quick clip (`/b/:brandId/clip?character=&screen=&prompt=`)

One clip, inside the brand, with no video around it. Two columns on desktop, one on phone. Behaviour (models, brand pieces, Improve prompt, limits) stays as in `docs/design/screens/quick-clip.md`; this spec sets the layout, wording and states.

## Desktop (≥ 1024)
```
Quick clip (page 32)                                        This week: 132 of 600 credits (meta)
┌ panel 400, bg-surface, radius 14 ────┐  ┌ History ─────────────────────────────────────────┐
│ Model                                │  │ History (section)        [All ▾]  [▤ List][▦ Grid] │
│ [Seedance 2.5 · 4–30 s · up to 1080p ⌄]│  │ ┌ media 9:14 ┐┌──────┐┌──────┐                    │
│ What happens                0 / 2,000 │  │ │[Making 1m] ││Ready ││Didn't│  3 columns, gap 16  │
│ [textarea 6 rows, body role         ] │  │ │            ││  ▶   ││finish│                    │
│ Who's in it, what happens, how the    │  │ │"Bo noses…" ││      ││      │  first line of the  │
│ camera moves. (meta)                  │  │ │8 s · 9:16  ││      ││      │  prompt (2 lines)   │
│ [Sparkles Improve prompt]  (ghost)    │  │ └────────────┘└──────┘└──────┘                    │
│ Brand pieces (2 of 4)                 │  │                                                     │
│ [Bo ×] [Bag · Salmon ×] [＋ Add]       │  │                                                     │
│ Shape   [9:16][1:1][16:9]             │  │                                                     │
│ Length  4 s ━━━●━━━━ 30 s     8 s     │  │                                                     │
│ Quality [480p][720p][1080p]           │  │                                                     │
├ sticky footer (inside the panel) ─────┤  │                                                     │
│ [      Generate · 68 credits        ] │  │                                                     │
│ (reason line)                         │  │                                                     │
└───────────────────────────────────────┘  └─────────────────────────────────────────────────────┘
```
- **Panel:** fields in this order, 20px padding, 20px between fields. The panel has no scroll of its own: the page scrolls. The footer is `sticky bottom-0` inside the panel (solid `bg-surface`, top border), so Generate stays in view at the bottom of the window but never covers a field (the #172 layout).
- **Model:** a secondary select-style button showing the model's name and its one line. It opens a popover (sheet on phone) listing each model: name (card), one line (meta), "from N credits a second" (meta). No provider names.
- **Brand pieces:** chips with a 24px picture and an `X` remove (`aria-label="Remove Bo"`). **＋ Add** opens a menu with tabs Characters · Places · Props · Screens · Upload. Screens set to "Always used for" a moment are added for you when the prompt mentions it, with a `Smartphone` icon and the meta line "Added because you mentioned the buy moment".
- **Improve prompt:** dialog as today. The result is editable; **Use this** (amber inside the dialog) and **Keep mine** (ghost). Meta: "Nothing is made until you press Generate." After use, a ghost **Undo improve** sits next to the button.
- **Generate · N credits** is the screen's amber button. Over the weekly allowance it reads **Ask Reed to approve · N credits**. Disabled reasons (first that applies): "Loading a brand piece…", "Describe the clip (8 or more characters)", "A clip is already being made", "Offline".
- **Allowance:** "This week: 132 of 600 credits" (meta, top right of the page). Editors never see dollars.

## History
- **Cards** (grid, default on desktop): media-first in the clip's shape, status badge top left, the first line of the prompt (card role, 2 lines) and "8 s · 9:16 · 720p" (meta) over the shade. A `Play` button only when ready.
- **List** (default on phone): rows with a 64px-wide thumbnail, status badge, the prompt (2 lines), meta line, then **Download** and **Reuse** (secondary dense), and the `Ellipsis` menu (see Remove and search).
- The prompt shown is **what the person typed**, never the model's internal prompt (no `[Image1] is the first frame…`).
- **Newest first.** A clip that was just started appears at the top with a 1.5s amber outline.
- **Tap a ready clip:** lightbox with the player, the prompt (body role), the brand pieces as chips, and **Download** (amber in the lightbox), **Reuse** (secondary: fills the panel with this clip's prompt, settings and brand pieces; toast "Settings copied. Press Generate to make another."). Ready cards on the grid and list also carry Download and Reuse.
- **Filter:** All · Ready · Making · Didn't finish · Removed (select, dense).

## Remove and search (gaps #14)
- **Search:** a field "Search your clips" (`Search` icon) at the start of the History header row, before the filter. It searches what the person typed, 300 ms after typing stops (`GET /jobs?q=`). It lives in the URL as `?q=`, so the address can be shared. On phone it's full width above the list, 44px tall.
  - No match: "No clips match "salmon"." with a ghost **Clear search**.
- **Remove from history** (`Trash2`) sits in an `Ellipsis` menu on each card and row (`aria-label="More for clip 12"`, 44px on phone). It's there once the clip has finished (Ready, Didn't finish or Cancelled), and only for the person who made it, or Reed.
  - While a clip is still being made or waits for Reed, the menu item isn't shown: **Cancel** is the way to stop it. If the server still answers "Wait for it to finish first.", that sentence shows as the toast.
  - No dialog, because it can be undone. The clip leaves the list at once.
  - The toast says "Removed from your history. Its credits stay used." with **Undo** (8 s), which is `POST /jobs/{id}/restore`. Nothing on the screen may suggest that removing gives credits back, and the allowance line doesn't change.
- **Removed** (the last filter option, `GET /jobs?removed=true`): the removed clips, newest first, muted, each with "Removed {date}" (meta) and **Restore** (secondary dense). Restore gives the toast "Clip back in your history." Search works here too.

## Phone (390)
- One column: the panel fields (no card around them, gutters 16), then **History** with the list.
- The amber **Generate · N credits** sits in the action bar with its reason line. The allowance line moves under the page title.
- Model, ＋ Add and Improve prompt open as sheets.
- Shape and Quality are segmented controls at full width, 44px tall.

## States
| State | What shows |
|---|---|
| Empty history | `Zap` icon. **Your first {brand} clip starts here.** "Describe a moment, add a brand piece, press Generate." Ghost **Start describing** (focuses the prompt). The panel works as usual. |
| Loading | Panel field skeletons and 3 history card skeletons (2 list rows on phone). |
| Making | Badge "Queued", then "Making 1m 12s" (elapsed time; the API has no progress). **Cancel** (ghost dense) on the card. |
| Error (a clip) | Badge "Didn't finish · credits returned", one plain line ("The video service was busy."), **Try again · 68 credits** (secondary). |
| Error (page) | Danger banner "Couldn't load your clips. Check your connection." **Try again**. The panel still works. |
| Waiting for Reed | `warn` badge "Waiting for Reed to approve" on the card. |
| Success | Toast "Your clip is ready." with **Show** (ghost dense) that scrolls to it. |
| Nothing removed | Filter set to Removed with none: "Nothing removed." with a ghost **Show all**. |
