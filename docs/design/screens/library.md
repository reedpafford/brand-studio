# Library: characters, places, props

Purpose: reusable people, locations and objects, shared by one or more brands, with history.
API: `/library/{character|place|prop}?brand_id=`, `/versions`, `/unarchive`, `/permanent`.

## Desktop (1440)
```
│ Library · fomo                                                          │
│ [Characters] Places  Props          ⌕ Search      [Show archived ☐]  [+ New character] │
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐     cards 200 wide, 1:1 image │
│ │ img  │ │ img  │ │ img  │ │ img  │ │ img  │                               │
│ │ Mia  │ │ Dex  │ │ …    │ │      │ │      │     name (md) + brand dots    │
│ │ ●● v3│ │ ●  v1│ │      │ │      │ │      │     version                   │
│ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘                               │
```
Click a card → detail page, two columns:
```
│ ← Characters   Mia                                    [Use in Quick clip] │
│ ┌ Images ───────────────┐  ┌ Details ─────────────────────────────────┐  │
│ │ [big sheet image]      │  │ Name     [Mia______________]             │  │
│ │ [thumb][thumb][+ Add]  │  │ Brands   [● fomo ×][● Iron Paws ×][+]    │  │
│ └────────────────────────┘  │ Notes    [textarea]                      │  │
│                             │ Outfits  Gym ×  Office ×  [+]            │  │
│                             │ Voice    [▶ sample.mp3] Replace          │  │
│                             │                            [Save]        │  │
│                             └──────────────────────────────────────────┘  │
│ History:  v3 today by Reed · v2 Oct 20 by Sam [Restore] · v1 …            │
│ ⋯ Archive (editors)  ·  Delete forever (owner, only when archived)        │
```
- Saving creates a new version; History shows who and when; [Restore] makes a new version from the old one (toast "Restored v2 as v4. Undo").
- Archive: toast "Mia archived. Undo". Archived items appear only with "Show archived", greyed, with [Unarchive] and (owner) [Delete forever] → confirm "Delete Mia forever? This removes all versions and can't be undone." [Keep] [Delete forever].

## Make sheet (characters and places)
A paid Nano Banana image that sits beside Upload in the **Images** box. It isn't offered for props.
```
│ ┌ Images ───────────────┐
│ │ [sheet] [thumb] [+ Add]│
│ │ [Make sheet · 3 credits]  Upload image │
```
- **What it makes:**
  - Character: one 9:16 turnaround (front, ¾ left, side, ¾ right, back) on a plain neutral background.
  - Place: one 16:9 sheet with a wide view and two closer angles.
  - Both are built from the name, the notes, the existing images (as references) and the brand's style board.
- **Button text:** "Make sheet · N credits" (the `image` rate), or "Make a new sheet · N credits" once a sheet exists. When it would go past the weekly allowance: "Ask Reed to approve · N credits", the same rule as Quick clip.
- **Drawing:** a skeleton tile appears first in the images row with "Drawing…", and the button is disabled with the reason "A sheet is being made."
- **Done:** the sheet becomes the **first** image, since the first image is what storyboards and clips use. It's saved as a **new version**, and History reads "v4 · sheet made by Claude". There's a toast "Sheet added as v4. Undo", where Undo restores v3.
- **Failed:** the tile reads "Didn't finish · credits returned" with **[Try again]**, and nothing else changes.
- **Unsaved edits** on the page are saved first, as their own version, before the sheet is made, so nothing is lost. The confirm reads: "Save your changes and make a sheet?"
- **Phone:** the button sits full width under the images carousel and is 44px tall.

## Phone (390)
Tabs become a segmented control under the title. Grid: 2 columns. "+ New" is a 56px round button bottom-right above the tab bar (the only floating button in the app). Detail page is one column: images carousel, details, history collapsed in a disclosure.

## Copy
- Empty: "No characters for fomo yet." / "Add a character once, use them in every video." / [New character].
- Places and Props: same, with "place"/"prop".
- Search no results: "Nothing matches "<q>"." [Clear search].
