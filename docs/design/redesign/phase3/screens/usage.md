# Usage (Reed only): the brand tracker

Reed, 2026-10-25 (DECISIONS #237): per brand, what was spent, how many videos got finished, and what a finished video costs. Click a brand to see its scripts and videos. New brands show up on their own. It has to stay usable with many brands, scripts and editors. Mock: `usage.png`. This replaces `docs/design/screens/usage.md` (the pre-redesign page, never built).

## Where it sits
- **Studio group, Reed only:** the rail's STUDIO group becomes Approvals · Team · **Usage** (`ChartColumn`). On phone it's in the account menu, under Team.
- **Routes:**
  - `/usage` is the tracker.
  - `/usage/brands/:brandId` is one brand.
  - Editors who open either see "Page not found", as on Approvals.
- **Dollars appear on Usage and Approvals only.** Editors keep seeing credits everywhere else (decision l). Nothing on this page changes what editors see.
- **One period for the whole page:** a segmented control **This week · This month · All time**, kept in the URL (`?period=week|month|all`, default `week`). Weeks start Monday, like the editor allowance. Months are calendar months.

## Words (used the same everywhere)
| Word | Means |
|---|---|
| **Spent** | Dollars charged in the period, for anything tied to the brand: videos, quick clips, scripts written, looks made for its videos. `≈` in front when some charges are estimates (the provider didn't report a cost); the tooltip says so. |
| **Finished** | Videos that became "Video done" in the period: the final MP4 was made, or the clips were downloaded, whichever came first. Counted once, on that day. |
| **Cost per finished video** | Everything spent on the videos finished in the period, over their whole life (every take and redo), divided by how many there are. Quick clips and script writing aren't in it. "—" when nothing finished. |
| **In progress** | Videos started (a version reserved, or an earlier-style video created) and not finished yet. It's a count for now, not for the period. |
| **Scripts** · **Versions left** | Scripts in the brand's library (drafts included, as Reed sees them) and published versions nobody has started. Now, not for the period. |

## `/usage` (desktop ≥ 1024)
```
Usage (page 32)                                     [This week | This month | All time]
Week of 20 Oct (meta)

┌ Spent ────────┐ ┌ Finished ─────┐ ┌ Cost per finished video ┐ ┌ In progress ┐
│ $84.12        │ │ 6 videos      │ │ $11.40                  │ │ 9 videos    │
└───────────────┘ └───────────────┘ └─────────────────────────┘ └─────────────┘

Brands (section)            [⌕ Search brands      ]  [Sort: Most spent ▾]  [ ] Show archived
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Brand          Spent    Finished  Cost/video  In progress  Scripts  Versions left  Last  │
│ ● Iron Paws    $52.30   4         $11.05      3            12       7              2 h  │ ›
│ ● fomo         $30.62   2         $12.10      5            9        4              today│ ›
│ ● Night Owl    $0.00    0         —           0            0        0              —    │ ›  (new brand: shows at once)
└─────────────────────────────────────────────────────────────────────────────────────────┘
Not tied to one brand: $1.20 · character looks used by several brands (meta)
[Show more]  (25 at a time)

▸ Every charge (disclosure, closed)
```
- **Stat cards:** four cards in a row. The label is meta, the number is page-26 tabular. Under each number, a meta line compares it with the period before:
  - "+$12.40 on last week"; "+$12.40 on last month" for This month
  - nothing for All time
  - plain text, no red or green
- **Brands table:**
  - The whole row is a link to the brand (`aria-label="Iron Paws: $52.30 spent, 4 finished"`), with `ChevronRight` at the end.
  - Numbers are right-aligned and tabular.
  - "Last" is the last activity (any job or edit) as a plain age: "2 h", "yesterday", "12 Oct".
  - A column header that reads "for the period" shows the period under it in meta ("this week"). In progress, Scripts and Versions left don't.
- **Sort:** Most spent (default) · Most finished · Cost per video (high first) · Last activity · Name A–Z.
- **Search:** filters by brand name.
- **Show archived:** archived brands are hidden unless this is on. When shown, the row carries a neutral "Archived" badge.
- **Paging:** 25 brands, then **Show more**. The count line above the table reads "12 brands", or "3 of 12 brands" when searching.
- **New brands** appear at once with zeros and "—". Nothing to set up.
- **Not tied to one brand:** a meta line under the table, only when it's above $0. It covers charges that can't belong to one brand (a character sheet whose character is in two brands).
- **Every charge:** a closed disclosure.
  - Open, it's the plain list of charges, newest first, 50 at a time: When · Who · Brand · What ("Clip 3 take 2 · Bo tries salmon · B", "Script variations · Bo tries salmon", "Quick clip") · Credits · $ · Status.
  - Filter: **Brand** (select, Any first).
  - This is the old "By job" table, kept for checking a single charge.

## `/usage` (phone 390, tablet < 1024)
- **Header:**
  - "Usage" (page 26)
  - the period segmented control at full width, 44px
  - "Week of 20 Oct" (meta)
- **Stats:** a 2×2 grid of the four cards. The number is card-17 size, and there's no comparison line.
- **Brands:** stacked cards (16 padding), 1 column on phone and 2 on tablet. Each card is a link to its brand:
  ```
  ● Iron Paws                                   ›
  $52.30 spent · 4 finished · $11.05 each
  3 in progress · 12 scripts · 7 versions left
  ```
  An archived brand shows its badge after the name.
- **Search and sort:** full-width search, then **Sort** and **Show archived** in one Filters sheet, as on Scripts.
- **Show more** is full width. **Every charge** rows stack: what (card), then "Sam · 2 h · 27 credits · $2.36" (meta).
- No action bar: there's nothing to do here but look.

## `/usage/brands/:brandId`
```
‹ Usage
● Iron Paws (page 32)                                [This week | This month | All time]
Week of 20 Oct (meta)
[ Spent $52.30 ] [ Finished 4 ] [ Cost per finished video $11.05 ] [ In progress 3 ]
12 scripts · 7 versions left to make · 3 editors made videos this period (meta)

[ Videos 31 | Scripts 12 ]  (tabs, kept in the URL: ?tab=videos|scripts)
```
**Videos tab** (default):
```
[⌕ Search videos]  [Status: Any ▾]  [Who: Anyone ▾]  [Sort: Last activity ▾]
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ Video                      Who    Status             Spent    Credits  Finished/Last │
│ Bo tries salmon · B        Sam    ✓ Video done       $11.80   134      Tue 21 Oct    │ ›
│ Midnight snack run · A     Reed   ◷ In production    $6.20    70       2 h           │ ›
│ Paws launch (earlier way)  Reed   ! Didn't finish    $3.10    35       3 days        │ ›
└─────────────────────────────────────────────────────────────────────────────────────┘
[Show more]  (25 at a time)
```
- **Video:** "{script title} · {letter}" for videos made from a script, otherwise the video's own name with "(earlier way)" in meta. The row opens the video at its current step (Downloads when done).
- **Status:** the library's chips and words (In production · Video done · Didn't finish), always in words.
- **Spent** and **Credits:** the video's whole life, not just the period. The period narrows **which** videos are listed:
  - Status "Video done": videos finished in the period.
  - Any other status: videos with activity in the period.
  - All time lists everything.
  - The meta line above the table says which: "Videos with activity this week".
- **Filters:** Status (Any · In production · Video done · Didn't finish), Who (Anyone, then each person who has a video here), and search by title.
- **Sort:** Last activity (default) · Most spent · Finished (newest) · Title A–Z.

**Scripts tab:**
```
[⌕ Search scripts]  [Status: Any ▾]  [Author: Anyone ▾]  [Sort: Recently changed ▾]
│ Script              Author  Versions                          Left  Spent    Changed │
│ Bo tries salmon     Reed    [A ✓] [B ◷ Sam] [C]               1     $19.40   2 days  │ ›
│ Gym day with Bo     Sam     [A · Writing]                     —     $0.31    today   │ ›
```
- **Versions:** the library's version chips, compact (dense, 32px on desktop, 44px on phone). Each chip opens what it opens in the library.
- **Spent:** writing the script (drafts, variations, reading the cast) plus every video made from it, over its whole life.
- The row opens the script (its writing flow if a draft, the script page if published).
- **Filters:** Status (Any · Writing · Ready to make · In production · Video done), Author, search. **Sort:** Recently changed · Most spent · Title A–Z.

**Phone:**
- The header and the 2×2 stats are as on `/usage`.
- The brand meta line wraps.
- The tabs are full width.
- Rows are stacked cards. A video card shows its title (card), the status chip, then "Sam · $11.80 · Tue 21 Oct" (meta). A script card shows its title, the chips wrapped at 44px, then "Reed · $19.40 · 1 left".
- Filters live in one Filters sheet, as on Scripts.

## States
| State | What shows |
|---|---|
| Loading | The period control and table header render at once. Stat cards show skeleton numbers, plus 5 row skeletons (cards on phone). |
| No brands at all | `ChartColumn` icon, **No brands yet.** "Add a brand from the brand menu. It shows up here by itself." No button. |
| Nothing in the period | The table still lists every brand with $0.00 and 0. Above it (meta): "Nothing was spent this week." |
| Search finds nothing | "No brand matches "{q}"." Ghost **Clear search**. |
| Brand with no videos | Videos tab: "No videos for Iron Paws yet. They show up here when someone starts a version." Scripts tab, empty: "No scripts yet." with a link **Open Scripts**. |
| Error | Danger banner "Couldn't load usage. Check your connection." **Try again**. Rows already shown stay. |
| Not the owner | "Page not found." |
| Estimates | A number with `≈` has a tooltip (a sheet on tap, on phone): "Some of this is an estimate: the provider didn't report the exact cost." |

## Words and icons
- **Icons:** `ChartColumn` for Usage; `ChevronRight` for row links; `Search`; the library's `Check`, `Clock` and `CircleAlert` for status.
- **Money:** "$52.30": always two decimals, with a comma for thousands ("$1,204.50"). No cents column, no currency code.
- **Never shown:** job ids, model names, provider names, "project", "usage row". The charges list says what was made in words.

## Data the screens need (server)
For Builder-Server. Every endpoint is owner-only; editors get 404. Generation doesn't change.

**1. A brand on every charge.**
- `jobs.brand_id` (nullable FK, indexed) is set when the job is created:
  - the project's brand, else
  - the request's `brand_id` (quick clip, improve), else
  - the script's brand (writing, variations, cast reading), else
  - the library item's brand when it has exactly one.
  - Otherwise it stays null, and counts as "Not tied to one brand".
- A migration backfills existing jobs by the same rule.

**2. When a video was finished.**
- `projects.finished_at` (nullable datetime) is set once, never cleared:
  - the first time a final video is made, or
  - the first time `GET /videos/{id}/clips.zip` (or the project's clips .zip) is served in full.
- The backfill is the earliest `final_videos.created_at`.
- The library's "Video done" (`app/script_library.py` `version_status`) reads `finished_at`, so downloads count there too.

**3. `GET /usage/summary?period=week|month|all`**
```
{ period, starts_at, previous: {spend_usd, finished, cost_per_finished_usd} | null,
  spend_usd, spend_estimated, finished, cost_per_finished_usd | null, in_progress,
  unassigned_spend_usd }
```

**4. `GET /usage/brands?period&q&archived=0|1&sort=spend|finished|cost|activity|name&cursor&limit=25`**
```
{ total, next_cursor,
  items: [{ brand_id, name, colour, archived,
            spend_usd, spend_estimated, finished, cost_per_finished_usd | null,
            in_progress, scripts, versions_left, last_activity_at | null }] }
```
- Every brand in the workspace is listed, including those with no activity.
- **Rules for the figures:**
  - `spend_usd` sums `usage.cost_usd` for the brand's jobs, with the usage row created in the period.
  - `finished` counts projects with `finished_at` in the period.
  - `cost_per_finished_usd` is the lifetime spend of those projects' jobs divided by `finished`.
- **Paging:** totals are per brand, so paging is over brands and the client never adds anything up.

**5. `GET /usage/brands/{brand_id}`**
- The brand's own summary, with the same fields as an item in 4 plus `previous`.
- `editors_active`: how many people made videos in the period.

**6. `GET /usage/brands/{brand_id}/videos?period&status=any|in_production|done|failed&person_id&q&sort=activity|spend|finished|title&cursor&limit=25`**
```
{ total, next_cursor, people: [{id, name}],
  items: [{ project_id, title, script_id | null, version_letter | null, legacy,
            person: {id, name} | null, status, spend_usd, spend_estimated, credits,
            finished_at | null, last_activity_at }] }
```
- `status` uses the library's words: `in_production`, `done`, or `failed` (the last job failed and nothing is running).
- `people` fills the Who filter.

**7. `GET /usage/brands/{brand_id}/scripts?status&author_id&q&sort=changed|spend|title&cursor&limit=25`**
- The same rows as `GET /scripts`, plus `spend_usd` and `spend_estimated`: the script's own jobs plus every project made from its versions.
- Returns `authors: [{id, name}]` for the filter.

**8. `GET /usage/charges?brand_id&cursor&limit=50`**
- Replaces the unpaged `GET /usage` (latest 500).
- Each item:
  ```
  { at, person {id, name} | null, brand {id, name} | null, what, credits, cost_usd, estimated, status }
  ```
  `what` is the plain words: "Clip 3 take 2 · Bo tries salmon · B".

**Tests to include:**
- A new brand appears with zeros.
- An editor gets 404 on every endpoint above.
- A clips .zip download sets `finished_at` once.
- A character sheet shared by two brands lands in "not tied to one brand".
- Week and month boundaries.
- Cursor paging returns every brand exactly once.
