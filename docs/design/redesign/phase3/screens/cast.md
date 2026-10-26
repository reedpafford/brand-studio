# Cast & places (`/b/:brandId/library`, item pages under it)

Characters, places and props for this brand, each usable in any video. Data and rules (versions, archive, house-style sheets) stay as in `docs/design/screens/library.md`; this spec sets the layout, wording and states.

## List
### Desktop
```
IRON PAWS (eyebrow)
Cast & places (page 32)                                                  [＋ New character]  amber
[Characters 4] [Places 2] [Props 1]   (tabs)          [Search ⌕            ]  [ ] Show archived
┌ 1:1 ──┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐        5 columns ≥1280 · 4 at 1024, gap 16
│[Needs │ │      │ │      │ │      │ │      │        badge top left only when it needs something
│ sheet]│ │      │ │      │ │      │ │      │
│Bo     │ │Mia   │ │      │ │      │ │      │        name (card 17) on the picture
└───────┘ └──────┘ └──────┘ └──────┘ └──────┘
```
- **Tabs** with counts. The amber button follows the tab: **New character**, **New place**, **New prop**.
- **Card:** media-first, 1:1. The picture is the approved sheet's front view, else the newest photo, else `surface-2` with the kind's icon (`Users`, `MapPin`, `Box`). Name over the shade. Brand dots (8px) in the bottom right when the item is shared with other brands.
- **Badge** (top left), only when there's something to know: `warn` "Needs a sheet", neutral "Drawing…", neutral "Archived". No version labels ("v3") anywhere.
- **Search** filters as you type. **Show archived** is a checkbox row (44px).

### Phone
- Title row, then tabs as a segmented control at full width, then search (full width), then the grid in 2 columns (gap 12).
- **New character** sits in the action bar. There is no floating button.
- "Show archived" moves into an `Ellipsis` menu next to the search.

## Item page (`/b/:brandId/library/:kind/:id`)
### Desktop
```
‹ Cast & places
Bo (page 32)  [Approved sheet ✓] (success badge)                [Use in a new video]  amber
┌ Pictures (7 cols) ───────────────────────┐ ┌ Details (5 cols) ─────────────────────┐
│ [approved sheet, 9:16, large]            │ │ Name      [Bo                    ]    │
│ ✓ Approved sheet · used in videos         │ │ Brands    [● Iron Paws ×] [＋]        │
│ [photo] [photo] [＋ Add photo]            │ │ Notes     [textarea              ]    │
│ Source photos, not used in videos (meta)  │ │ Outfits   [Gym ×] [＋]  (characters)  │
│                                           │ │ Voice     [▶ sample.mp3] Replace      │
│                                           │ │                     [Save changes]    │
└───────────────────────────────────────────┘ └───────────────────────────────────────┘
History (section) ▸ collapsed: "Changed today by Reed · 4 earlier changes"
[Ellipsis] Archive · Delete forever (Reed, archived only)
```
- **The amber button**, by state:
  - Approved sheet: **Use in a new video** (opens New video with Bo picked).
  - Photo, no sheet: **Make house-style sheet · 2 credits** (1.5 rounded up). Past the week, it's disabled with "That's more than this week's 145 free credits. It resets on Monday." (README rule 2).
  - No photo: **Add photo** (`Upload`).
  - Props have no sheets, so their amber button is **Save changes** when there are edits, otherwise none.
- **Save changes** is secondary when the amber slot is taken, and is disabled until something changed (reason "No changes yet").
- **History** is collapsed into one line. Open, it lists changes as "Today 10:42 · Reed changed the notes" with **Restore** (ghost dense). No version numbers. Restoring shows the toast "Restored. Undo".
- **Archive:** toast "Bo archived. Undo". **Delete forever** (Reed, archived only) uses the danger dialog: "Delete Bo forever? Every change is removed and it can't be undone." **Keep it** / **Delete forever**.

### The sheet flow
Same steps as today, in the Pictures column:
1. After a photo upload, a card under it: "Turn this photo into a house-style sheet? Videos only use approved sheets." with the amber button (see above).
2. **Drawing:** a sheet-shaped skeleton with "Drawing… 14 s". The button shows busy with the reason "A sheet is being made."
3. **Result:** the sheet with **Approve** (secondary, `Check`) and **Redo · 2 credits** (ghost). Redo asks "What should change? (optional)".
4. **Approved:** 2px amber ring, success badge "Approved sheet", toast "Sheet approved. Bo can be in videos now." with **Undo**. The amber button becomes **Use in a new video**.
- Places work the same with a 16:9 sheet. Props have no sheets.
- When the page was opened from a blocked frame or clip (`?back=`), a banner on top reads "Back to Bo tries salmon" (ghost, `ChevronLeft`), and approving the sheet changes the amber button to **Back to the video**.

### Phone
- One column: pictures as a swipeable row (the sheet first, then photos, with dots), then Details, then History collapsed.
- The amber button sits in the action bar. Save changes, when there are edits, takes the action bar instead.

## States
| State | What shows |
|---|---|
| Empty (per tab) | `Users` (or `MapPin`, `Box`) icon. **No characters for {brand} yet.** "Add a character once and use them in every video." Amber **New character**. |
| No search results | "Nothing matches "{q}"." Ghost **Clear search**. |
| Loading | 10 card skeletons (4 on phone). Item page: a picture skeleton and field skeletons. |
| Error | Danger banner "Couldn't load your cast. Check your connection." **Try again**. A failed sheet: "Didn't finish · credits returned" + **Try again · 2 credits**; the photo stays. |
| Success | New item: lands on its page with the toast "Bo added. Add a photo next." Save: toast "Saved. Undo". |
