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

## House-style sheet (characters; places work the same way)
Videos only ever use an **approved sheet**. Photos you upload are source material, not what appears on screen.

**Flow for a character:**
1. **Upload a photo.** It shows labelled "Source photo, not used in videos" (muted caption under the image).
2. Straight after the upload, a card appears under it: "Turn this photo into a house-style sheet?" with **[Make house-style sheet · 3 credits]**. It's offered, not started automatically, so the cost is always seen before it's spent. Over the weekly allowance the button reads "Ask Reed to approve · 3 credits".
3. **Drawing:** a sheet-shaped skeleton next to the photo with "Drawing…". The button is disabled with the reason "A sheet is being made."
4. **Result:** the sheet (front · side · back, house style, 9:16) next to the photo, with **[Approve]** and **[Redo · 3 credits]**. Redo opens "What should change? (optional)", inline on desktop and in a bottom sheet on phones.
5. **Approve:** the sheet gets a 2px accent border and "✓ Approved sheet". It's saved as a new version ("v4 · sheet approved") with a toast and Undo. This sheet is what storyboards and clips use. Approving a new one replaces the old one.

```
│ ┌ Images ─────────────────────────────────────────────┐
│ │ [photo]                 [sheet: front|side|back]    │
│ │ Source photo,           ✓ Approved sheet            │
│ │ not used in videos      [Redo · 3 credits]          │
│ └─────────────────────────────────────────────────────┘
```
- **Without an approved sheet:**
  - The character's library card and page show a warning badge "Needs a sheet".
  - The page also offers **[Make house-style sheet · N credits]** when there's a photo, or "Upload a photo to make a sheet" when there isn't.
- **Places:** same flow, with a 16:9 sheet (a wide view + two angles) and the caption "Source photo, not used in videos". Props don't get sheets.
- **Failed:** "Didn't finish · credits returned" with **[Try again]**. The photo is untouched.
- **Unsaved edits** are saved first, as their own version.
- **Phone:** the photo and sheet stack vertically, and the buttons are full width and 44px tall.

**Where it blocks:** Storyboard and Clips can't make anything with a character or place that has no approved sheet.
- Storyboard: the frame card shows a warning "Mia needs an approved sheet. [Open Mia]". Make still / Make all skip that frame, and **Make all stills** says "2 frames wait for a sheet."
- Clips: same wording on the clip card. **Make missing** skips those clips and says which character blocks them.
- **[Open Mia]** goes to the character's page and comes back to the same stage afterwards (a `?back=` link).

## Phone (390)
Tabs become a segmented control under the title. Grid: 2 columns. "+ New" is a 56px round button bottom-right above the tab bar (the only floating button in the app). Detail page is one column: images carousel, details, history collapsed in a disclosure.

## Copy
- Empty: "No characters for fomo yet." / "Add a character once, use them in every video." / [New character].
- Places and Props: same, with "place"/"prop".
- Search no results: "Nothing matches "<q>"." [Clear search].
