# Script library (`/b/:brandId/scripts`), the brand's home

This replaces `phase3/screens/videos.md`. Plan: `../workflow-v2.md`, decisions a–l.

The nav item **Videos** becomes **Scripts**, using the `FileText` icon. `/b/:brandId` and `/b/:brandId/projects` redirect here. Old videos (made before scripts) stay reachable at the bottom.

## Desktop (≥ 1024)
```
IRON PAWS (eyebrow)
Scripts (page 32)                                        [Layers Bulk create]  [＋ New script]  amber
This week: 32 of 145 credits (meta, editors only)
[⌕ Search titles, descriptions and scripts     ]  [Status ▾] [Length ▾] [Reference ▾] [Versions left ▾] [Mine] [This brand ▾ (Reed)]   Sort: Recently changed ▾
24 scripts (meta)
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ ┌64×100┐ Bo tries salmon (card 17)                         Reed · 2 days ago (meta)    │
│ │poster│ Show a picky dog finally loving Iron Paws salmon… (meta, 1 line)               │
│ │      │ Ref: The altar reel · 24–30 s · 1 version left to make (meta)                  │
│ └──────┘ [✓ A · Video done] [B · In production · Sam] [C · Ready to make]              │
├──────────────────────────────────────────────────────────────────────────────────────────┤
│ …one row per script, divided by 1px borders inside one card…                            │
└──────────────────────────────────────────────────────────────────────────────────────────┘
[Show more]   (30 at a time)
▸ Videos made before scripts (4)       (disclosure, closed)
```
- **Row:** the poster, then the title, then up to two meta lines, then the version chips.
  - A script made from a reel starts its meta line with a neutral **Reel** chip (`Film`), as built in #449. Once the server sends the length, it reads "Reel · 45 s".
  - **Poster** (64×100, radius 10): the first frame of the newest finished video, else the reference reel's thumbnail, else `surface-2` with `FileText` in muted colour.
  - **Title:** a link to the script page (see "Opening a script").
  - **Description:** one line, ellipsed.
  - **Meta line:** the reference reel's name if any, then the length range from the saved breakdowns ("24–30 s"; "Length set at Breakdown" if none), then "{n} versions left to make" (only on published scripts).
- **Version chips:** one per version, in order A, B, C. They're buttons, 36px on desktop and 44px below 1024, wrapping on narrow rows. The label is "{letter} · {status}"; A is the original. The status is always in words, with tone as a second signal:

  | Status | Tone | Icon | When |
  |---|---|---|---|
  | Writing | neutral | `Pencil` | Not published (the author sees it; Reed also sees editors' drafts) |
  | Ready to make | accent | none | Published, no video started |
  | In production · {name} | warning | `Clock` | Reserved by that editor (decision c) |
  | Video done | success | `Check` | Its video is made, or its clips are downloaded |
  | Didn't finish | danger | `CircleAlert` | The video's last job failed and nothing is running |

  `aria-label`: "Version B, in production by Sam".
- **Filters** are dense selects (menus) in one row, and the search field is 360px wide.
  - **Status:** Any · Writing · Ready to make · In production · Video done · Didn't finish.
  - **Length:** Any · Under 15 s · 15–30 s · 30–60 s · Over 60 s.
  - **Reference:** Any · No reference · each reel by name.
  - **Versions left:** Any · At least one · None.
  - **Mine:** a toggle button (`aria-pressed`) showing scripts you wrote, your private drafts included.
  - **Brand** (Reed only): This brand · All brands. With All brands, each row's meta starts with the brand dot and name.
  - **Sort:** Recently changed (default) · Newest · Title A–Z.
  - Active filters show their value in the button ("Status: Ready to make"), plus a ghost **Clear filters** at the end of the row.
  - The filters live in the URL (`?status=ready&len=15-30&mine=1`), so a filtered view can be shared or bookmarked.
- **Search** matches the title, the description and the words of every version. It waits 300 ms after typing stops. A match inside a script's words shows a third meta line with the matching words in the script font, marked with `bg-mark`.
- **Defaults:**
  - **Reed:** no filters. Reed sees every script, editors' drafts included (Producer, decision f: private means private from other editors).
  - **An editor:** a "Yours" section at the top, shown whatever the filters say, with two groups:
    - **Making now:** the versions they've reserved and haven't finished (one row per script, with the version's chip). The chip opens their video at its current step.
    - **Drafts:** their own unpublished scripts.

    Each group shows only when it has something. Under it, the list with **Status: Ready to make** applied. Without this, a version disappears from an editor's default view as soon as they start it.
- **Count line:** "24 scripts" (meta), or "3 of 24 scripts" when filtered.

## Opening a version (the chip)
| Chip | Who | Opens |
|---|---|---|
| Writing | the author | The writing flow at the first unfinished step |
| Ready to make | anyone | The **version panel** (below) |
| In production · you | you | Your video at its current step |
| In production · someone else | anyone | The version panel, read-only, with "Sam is making this version." and no button |
| Video done | anyone | The video at **Downloads** |
| Didn't finish | the editor making it, or Reed | The video at the step that failed |

**Version panel:** a side panel (380px) on desktop, a sheet on phone. It contains:
- **Title:** "Bo tries salmon · Version B", with "Variation of A" (meta) under it if it's a variation.
- **The words:** the first 8 lines in the script font, then **Show all**.
- **Characters:** picture chips. Locked ones show a `Lock` icon and "Locked look"; others show "Look made at Assets".
- **Breakdown:** "Planned by Reed · 28 s · 4 clips", or "Planned automatically when you start".
- **Estimate:** "About 210 credits to make (budget 420)" (meta). For editors' own scripts: "About 210 credits · This week: 32 of 145".
- **The amber button: Make this version.** It reserves the version and opens the video at Breakdown. Toast: "Version B is yours. Next: the breakdown."
  - If it's reserved by someone else, it's disabled with the reason "Sam is making this version".
  - If the version isn't published, it's hidden (decision j).
  - Past an editor's weekly allowance: "That's more than this week's 145 free credits. It resets on Monday." There's no Ask Reed (decision l).
- **Duplicate script** (secondary, `Copy`, author or Reed). It makes a new draft with the same description and words, and opens it at the Script step. Toast: "Duplicated as a new draft."

## Opening a script (the title)
- **A draft:** the writing flow.
- **Published:** the **script page**: the Publish step's summary, read-only, showing every version's card with its chip. The header has `Lock` "Published · final", and the secondary **Duplicate script**.

## Delete script
The server route is `DELETE /scripts/{id}`.
- **Who sees it:**
  - Reed: on any script.
  - An editor: only on their own unpublished drafts.
  - Anyone else: hidden, not disabled.
- **Where:**
  - In the script page's `Ellipsis` menu (the writing frame header, and the published script page): **Delete script** (danger text, `Trash2`).
  - On each library row the person may delete: an `Ellipsis` icon button (36px desktop, 44px phone, `aria-label="More for Bo tries salmon"`) at the row's right, with the same item.
- **Confirm first** (dialog on desktop, sheet on phone):
  - No video made from it: "Delete "Bo tries salmon"?" with "Its versions and cast go too." Buttons **Delete** (danger) / **Keep it** (ghost).
  - A video was made from any version: "Archive "Bo tries salmon"?" with "It leaves the library. The videos made from it stay, with their clips and downloads." Buttons **Archive** (danger) / **Keep it**.
  - **Running work** (#467): when something is still being made for the script itself (its words, a reel read, variations, Directions, the plan), both bodies end with "Anything still being made for this script stops and isn't brought back." Undo and Restore don't restart it. Videos already started from it carry on, so the line doesn't mention them. The line is left out when nothing is running.
- **After:**
  - The row leaves the list, and the script page goes back to Scripts.
  - Toast: "Deleted "Bo tries salmon"." (or "Archived …") with **Undo**, for 8 s. Undo brings it back exactly as it was and puts the row back in place.
  - If the call fails: toast "Couldn't delete it. Nothing changed." with **Try again**.
- **Server:** Undo needs the script to still exist. So a delete only marks it (`deleted_at` or `archived`), and a restore route (`POST /scripts/{id}/restore`) clears it. Marked scripts can be removed for good later, after a day.

## Deleted and archived (gaps #11)
- **Filter:** a toggle button **Deleted and archived** (`aria-pressed`, `Archive` icon) at the end of the filter row. On phone it's in the Filters sheet, under Mine.
  - On, it shows only scripts that were deleted or archived. The other filters and search still apply.
  - Reed sees every one. An editor sees only their own.
- **Each row:**
  - The usual poster, title and meta. The version chips are shown but don't open anything.
  - A badge after the title:
    - "Deleted · 2 days ago" (neutral), with the meta line "Removed for good on 24 Nov" (30 days after the delete)
    - or "Archived" (neutral), with "Its videos are kept"
  - **Restore** (secondary, dense on desktop, 44px on phone) on the right.
- **Restore:**
  - It brings the script back exactly as it was, with its versions, cast and reel.
  - Toast: "Restored "Bo tries salmon"." with **Open** (ghost). The row leaves this view.
  - If a published version was being made when it was archived, it comes back with its chip as it was.
- **Empty:** "Nothing deleted or archived." with ghost **Show all scripts**.
- **Server:** `GET /scripts?removed=1` (each row gains `removed: deleted | archived`, `removed_at`) and `POST /scripts/{id}/restore`.

## Phone (390) and tablet (< 1024)
- **Title row:** "Scripts" (page 26), plus an `Ellipsis` icon button that holds Bulk create.
- **Allowance:** meta under the title (editors only).
- **Search and Filters:** one row: the search field takes the width, and a **Filters** button sits to its right, both 44px.
  - The button is secondary when nothing is filtered. With filters on it turns primary and shows the count: "Filters (2)".
  - It opens one sheet titled "Filters" with every filter as a 44px select (Status, Length, Reference, Versions left, Mine, then Sort, and Brand for Reed), and a ghost **Clear filters** at the bottom while any are on.
  - Accepted from #226 in place of a scrolling chip row: one button is easier to find and doesn't hide filters off the edge.
- **Rows** are stacked cards (16 padding): the poster (56×88) on the left, then the title (card), one meta line ("Ref · 24–30 s"), and the chips wrapping under it at 44px.
- **Action bar:** **＋ New script**.
- **Tablet (768):** the same as phone. Rows are cards in 2 columns.

## Videos (gaps #13)
A **Scripts · Videos** segmented control under the page title (44px on phone) switches the page to the brand's videos (`?view=videos`). Scripts stays the default.
- **Who sees what:** an editor sees the videos they're making or made (`mine=true` is always on). Reed sees everyone's, with a **Mine** toggle.
- **Filters:** a search field ("Search videos", 300 ms after typing stops; it matches the script title and, for B and C, the version's title), then **Status: Any · Making · Video done**, and an **Archived** toggle. The same Filters sheet applies on phone.
- **Rows** use the In production row's shape (poster, "{script title} · {letter}", meta "{who} · {step or 'Video done · 24 Oct'}"). The status shows as a chip: "In production" (warning, `Clock`) or "Video done" (success, `Check`). An archived row is muted, with an "Archived" badge.
  - The row opens the video at its current step (Downloads when done).
  - On an editor's own script, the meta adds "On your week".
- **Count line:** "6 videos", or "2 of 6 videos" when filtered.
- **Empty:** for an editor, "You haven't started a video yet. Pick a version that's Ready to make." with **Show scripts** (ghost). With filters: "Nothing matches these filters." with **Clear filters**.
- Earlier-way videos are listed here too, with "(earlier way)" in the meta, so the closed "Videos made before scripts" disclosure moves into this view.
- **Server:** `GET /projects?brand_id&q&mine&status=making|done&archived` (#374). Rows carry `finished_at`, `archived_at`, `own_script`, `script_draft_id` and `created_by_name`.

## Videos made before scripts
- A closed disclosure at the bottom: "Videos made before scripts (4)". It only shows when there are any.
- Open, it shows the old video cards (`MediaCard`, as #180). Each opens its project in today's six-step video page. Nothing is migrated or hidden.

## States
| State | What shows |
|---|---|
| Empty (Reed) | `FileText` icon. **No scripts for {brand} yet.** "Write a script once and make up to three videos from it." Amber **＋ New script**, and secondary **Bulk create**. |
| Empty (editor, nothing published) | **No scripts ready to make yet.** "Reed publishes scripts here. You can also write your own." Amber **＋ New script**. |
| No match | "Nothing matches these filters." Ghost **Clear filters**. |
| Loading | 5 row skeletons in the row's shape: a poster block and three lines. The filter row renders straight away. |
| Error | Danger banner "Couldn't load your scripts. Check your connection." **Try again**. Rows already shown stay. |
| Success | Coming back from Publish: toast "Published. 2 versions are ready to make." The script is first in the list, with a 1.5 s amber outline. |

## Words and icons
- **Icons:**
  - `FileText` for Scripts
  - `Layers` for Bulk create
  - `Plus` for New script
  - `Search`, `Lock`, `Copy`, `Clock`, `Check`, `CircleAlert`, `Pencil`
- **Never shown:** internal ids, "v3", "project".

## Data the screen needs
This is for the Producer; it's new server work.
- `GET /scripts?brand_id&q&status&length&reference_id&versions_left&mine&sort&cursor` returns, per script:
  - `id`, `title`, `description`, `author {id, name}`, `updated_at`
  - `reference {id, name, thumbnail}`
  - `poster_file_id`
  - `published`
  - `versions[]`: `letter`, `status`, `editor {id, name}`, `video_id`, `length_seconds`, `saved_breakdown`
  - `total` for the count line
- `GET /scripts/{id}/versions/{letter}` for the version panel: words, characters with locks, breakdown summary, and estimate.
- `POST /scripts/{id}/versions/{letter}/start` reserves the version and makes its video. It refuses if the version is reserved or unpublished, or the allowance is exceeded.
- `POST /scripts/{id}/duplicate`.
- `GET /projects?brand_id&legacy=1` for "Videos made before scripts".
