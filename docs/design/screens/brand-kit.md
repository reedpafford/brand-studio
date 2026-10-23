# Brand kit + brand screens

Purpose: everything that makes a video "on brand", in one page an editor can check in 10 seconds.
API: `GET/PATCH /brands/{id}`, `GET/POST/PATCH/DELETE /brands/{id}/screens`, `POST /files`.

## Desktop (1440)
```
│ Brand kit · fomo                                         [Save changes] │
│ ┌ Look ───────────────────────────┐ ┌ Voice ────────────────────────┐  │
│ │ Logo      [img] Replace          │ │ Tone notes                     │  │
│ │ Colours   ■ ■ ■ [+]  (first one  │ │ [textarea, 6 rows]             │  │
│ │           tints the brand stripe)│ │ Never say  [chip×][chip×][+]   │  │
│ │ Fonts     [chip×][+]             │ │ Legal line [__________________]│  │
│ │ End line   [__________________]│  │   e.g. "Download fomo through the link in my bio."
│ │ Products   [Chicken ▣][Peanut butter ▣][+]   name + bag image each │
│ │ Style board [img] End card [img] │ │                                │  │
│ └──────────────────────────────────┘ └────────────────────────────────┘  │
│ Brand screens (12)        [Filter: all tags ▾]          [+ Add screens] │
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐   9:16 tiles, 6 per row        │
│ │    │ │    │ │    │ │    │ │    │ │    │                                │
│ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘                                │
│ Buy BTC  Chart up …   name                                              │
│ ★ Always for: buy-moment     tags: trading · mobile                     │
```
- Two cards side by side (≥ 1024), stacked below.
- **Screens are the important part for fomo.** Each tile: image, name, tag chips, and a ★ line when `default_for` is set ("Always used for: buy moment"). Click → side sheet (480) with big preview, Name, Tags, "Always use this screen for" (chips of moments), [Delete screen] (danger, confirm).
- "+ Add screens" opens a dropzone dialog; multiple files; each upload becomes a tile with an inline name field prefilled from the filename.
- Save bar: [Save changes] is disabled until something changed; leaving with unsaved changes asks "Leave without saving?".

## Phone (390)
Look card, Voice card, then Screens as a 3-column grid of 9:16 tiles. Tapping a tile opens a full-height sheet. "Save changes" becomes a sticky bottom bar above the tab bar, only visible when there are changes.

## States and copy
- No screens: "No brand screens yet." / "Add real app screens so videos show them exactly." / [Add screens].
- Upload wrong type: inline under the tile "This file isn't an image (PNG, JPG or WebP)."
- Upload too big: "Too big. Max <N> MB."
- Colour input: hex only, with a swatch; invalid → "Use a colour like #12A150."
