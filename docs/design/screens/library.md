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

## Phone (390)
Tabs become a segmented control under the title. Grid: 2 columns. "+ New" is a 56px round button bottom-right above the tab bar (the only floating button in the app). Detail page is one column: images carousel, details, history collapsed in a disclosure.

## Copy
- Empty: "No characters for fomo yet." / "Add a character once, use them in every video." / [New character].
- Places and Props: same, with "place"/"prop".
- Search no results: "Nothing matches "<q>"." [Clear search].
