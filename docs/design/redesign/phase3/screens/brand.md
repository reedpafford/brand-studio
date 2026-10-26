# Brand (`/b/:brandId/brand`, tabs `?tab=look|products|screens`)

One page with three tabs: **Look · Products · App screens**. `/kit` and `/screens` redirect here (to Look and App screens). Same data and API as today; Products are grouped from the screens' existing product and variant fields.

## Frame
```
IRON PAWS (eyebrow)
Brand (page 32)                                                     [Save changes]  amber
[Look] [Products 3] [App screens 12]   (tabs, 44px)
```
- The amber button follows the tab: **Save changes** on Look (disabled until something changed, reason "No changes yet"), **Add product** on Products, **Add screens** on App screens.
- Leaving Look with unsaved changes asks in a dialog: "Leave without saving?" **Keep editing** / **Leave** (danger).
- Phone: tabs as a segmented control at full width; the amber button in the action bar.
- **Archive brand** (Reed only, gaps #8): in an `Ellipsis` menu at the right of the page title.
  - Confirm: "Archive {Name}? It leaves the brand menu. Its scripts, videos and screens are kept, and you can bring it back from Usage." **Keep it** / **Archive** (danger).
  - After: the app switches to the first other brand. Toast: "Archived {Name}." with **Undo** (8 s).
  - Bringing it back later: Usage → **Show archived** → the brand's row → **Restore** (secondary dense).
  - Editors never see the menu. An editor who opens an archived brand's link gets "That brand was archived. Ask Reed if you need it." with a link to Scripts.
  - Server: `POST /brands`, `DELETE /brands/{id}` (archive), and the coming `POST /brands/{id}/restore`.

## Look
Two columns ≥ 1024 (Look 7 cols, Voice 5 cols); one column on phone.
- **Look card:**
  - **Logo:** 96px tile on `surface-2` with **Replace** (secondary dense, `Upload`).
  - **Colours:** swatches 44px with their hex (caption) under them, **＋** to add, `X` on hover/focus to remove. Meta: "The first colour tints the brand's dot." Invalid input: "Use a colour like #12A150."
  - **Fonts:** chips with `X`, **＋ Add**.
  - **Style board** and **End card:** image tiles (16:9 and 9:16) with **Replace**.
- **Voice card:**
  - **How we sound** (textarea, 6 rows).
  - **Never say** (chips with `X`, input to add).
  - **Legal line** (input).
  - **End line** (input). Meta: "The last clip of every video says this. Example: "Want to trade like me? Download fomo through the link in my bio.""

## Products
For fomo-style brands without products this tab shows its empty state; for Iron Paws it's the main one.
```
┌ Bag (section 20) · 3 flavours ──────────────────────────────── [Ellipsis] ┐
│ ┌1:1──┐ ┌────┐ ┌────┐ ┌ ＋ ──┐                                            │
│ │     │ │    │ │    │ │ Add  │   flavour cards, 4 per row (2 on phone)    │
│ │Chicken│ │Peanut│ │Salmon│ │flavour│                                     │
│ └─────┘ └────┘ └────┘ └──────┘                                            │
└───────────────────────────────────────────────────────────────────────────┘
```
- One card per product (from the screens' product field), listing its flavours (variant field) as 1:1 media cards with the flavour name over the shade.
- A flavour card's picture is the screen marked for it. Tapping it opens the same editor as an app screen.
- **Add flavour** uploads a picture and asks for the flavour name; the product is filled in.
- **Add product:** a sheet/dialog with **Product name** ("e.g. Bag") and the first flavour's picture and name.
- Renaming a product (in the `Ellipsis` menu) renames it on all its screens.

## App screens
```
App screens (section) · 12                  [All tags ⌄]
┌9:16┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐     6 per row desktop, 3 on phone, gap 12
│    │ │    │ │    │ │    │ │    │ │    │
│Buy │ │    │ │    │ │    │ │    │ │    │     name (card) over the shade
└────┘ └────┘ └────┘ └────┘ └────┘ └────┘
```
- **Tile:** media-first, 9:16, name over the shade. A neutral badge top left with `Smartphone` "Buy moment" when the screen is always used for a moment. Tags show in the editor, not on the tile.
- **Editor:** side panel 380 on desktop, full-height sheet on phone: large preview, **Name**, **Tags** (chips), **Product** and **Flavour** (optional, "e.g. Bag / Chicken"; this fills Products and the brief's flavour picker), **Always use this screen for** (moment chips), **Save screen** (amber in the panel), **Delete screen** (danger, ghost-styled at the bottom, with the dialog "Delete the screen "Buy"? Videos already made keep it.").
- **Add screens:** a drop zone dialog (sheet on phone) taking several files; each upload becomes a tile with a name field filled from the file name.

## States
| State | What shows |
|---|---|
| Empty Products | `Package` icon. **No products yet.** "Add a product and its flavours so briefs can pick them." Amber **Add product**. |
| Empty App screens | `Smartphone` icon. **No app screens yet.** "Add real app screens so videos show them exactly." Amber **Add screens**. |
| Loading | Look: field skeletons. Products and screens: tile skeletons in their shapes. |
| Error | Danger banner "Couldn't load the brand. Check your connection." **Try again**. Upload errors sit under the tile: "This file isn't a picture (PNG, JPG or WebP)." / "Too big. The most is {N} MB." |
| Success | Toast "Saved. Undo" (Look), "Screen added." (App screens), "Bag added." (Products). |
