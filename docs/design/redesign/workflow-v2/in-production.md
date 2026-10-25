# In production (Reed only)

Reed, 2026-10-25: one list, across every brand, of each version being made. Each row shows the script, the version, the editor, the step it's on, the last activity, the credits used against the budget, and whether it's stuck or failed. A row opens that video.

## Where it sits
- **Studio group, Reed only:** the rail's STUDIO group becomes Approvals · **In production** (`Clapperboard`) · Team · Usage. On phone it's in the account menu, under Approvals.
  - The rail item shows a count badge when something needs attention: "In production 2". It uses the same badge as Approvals.
- **Route:** `/production`, outside the brand, like Approvals and Usage. Editors who open it see "Page not found".
- **What's listed:** every version that has been started (reserved) and isn't "Video done". Done videos drop off; they're on the Usage tracker.
  - Videos made before scripts aren't listed.
- **Money:** Reed sees credits and dollars here, as on Usage. Editors never reach this page.

## Words
| Word | Means |
|---|---|
| **Step** | The video's current step: Breakdown · Assets · Storyboard · Clips · Downloads (the five steps of `video-flow.md`). |
| **Last activity** | The newest job or edit on the video, as a plain age: "4 min", "2 h", "yesterday", "12 Oct". |
| **Credits** | "134 of 420 credits": what the video has used over its whole life, against its budget (2× the 480p estimate). Then the dollars in meta: "$13.78". |
| **Didn't finish** | The video's newest job failed and nothing has run since. The same word and tone as the library chip. |
| **Stuck** | A job has been waiting or running for over 30 min. |
| **No activity** | No job or edit for 48 h. |

**Needs attention** means Didn't finish, Stuck or No activity. A row only ever shows one flag, in that order.

## Desktop (≥ 1024)
```
STUDIO (eyebrow)
In production (page 32)
9 videos being made · 2 need attention (meta)

[⌕ Search scripts      ]  [Brand: All ▾]  [Editor: Anyone ▾]  [Needs attention]         Sort: Needs attention first ▾
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Video                         Brand        Editor  Step         Last activity  Credits                   │
│ ┌36×56┐ Bo tries salmon · B   ● Iron Paws  Sam     Clips        3 h            380 of 420  $39.06        │ ›
│ └─────┘ [! Didn't finish · Clips: the take didn't finish. Credits were returned.]                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────┐ Altar remake · A      ● fomo       Ana     Storyboard   52 min         96 of 210   $9.87         │ ›
│ └─────┘ [⚠ Stuck · Drawing the frames for 52 min]                                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────┐ Gut check · C         ● Iron Paws  Sam     Assets       3 days         12 of 180   $1.23         │ ›
│ └─────┘ [⚠ No activity for 3 days]                                                                        │
├──────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────┐ Midnight snack · A    ● Iron Paws  Reed    Breakdown    4 min          0 of 120    $0.00         │ ›
│ └─────┘                                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
[Show more]  (25 at a time)
```
- **The table** is one card divided by 1px rows, as on Usage. The whole row is a link to the video at its current step (`/b/:brandId/projects/:id`), with `ChevronRight` at the end.
  - `aria-label`: "Bo tries salmon, version B, Sam, at Clips, didn't finish".
- **Video:** a poster (36×56, radius 10), then "{script title} · {letter}" (body, 600). The poster is the newest picked take's first frame, else the newest storyboard frame, else `surface-2` with `Film` in muted colour.
- **Brand:** the brand dot and name. The column is hidden when Brand is set to one brand.
- **Editor:** the name of whoever reserved the version ("Reed" when it's his).
- **Step:** in words.
- **Last activity:** right-aligned and tabular.
- **Credits:** "380 of 420" tabular, with the dollars in meta after it.
  - At 90% of the budget or more, the credits turn `text-warning`, and the tooltip says "Close to the budget. Going over needs your approval."
  - Over the budget can't happen without Reed's approval. A request waiting on it is on Approvals, not here.
- **Flag line:** only when the row needs attention. It's a second line under the title with one badge plus its reason (meta), in plain words:

  | Flag | Badge | Icon | Reason line |
  |---|---|---|---|
  | Didn't finish | danger | `CircleAlert` | "Didn't finish · {step}: {the server's words}" e.g. "Clips: take 2 of clip 3 didn't finish. Credits were returned." |
  | Stuck | warning | `TriangleAlert` | "Stuck · {what's running} for {time}" e.g. "Drawing the frames for 52 min", "Waiting to start for 40 min" |
  | No activity | warning | `Clock` | "No activity for {n} days" |

  What's running uses the job's plain name: "Planning the breakdown", "Making the looks", "Drawing the frames", "Making the takes", "Making the video". Never a job id or a model name.
- **Filters:** one row, the dense desktop selects used elsewhere.
  - **Brand:** All (default), then each brand by name.
  - **Editor:** Anyone (default), then each person with a video in the list, Reed included.
  - **Needs attention:** a toggle button (`aria-pressed`). On, it shows only flagged rows.
  - **Search:** script titles, 300 ms after typing stops.
  - **Sort:** Needs attention first (default: Didn't finish, then Stuck, then No activity, then the newest activity) · Last activity · Most credits used · Closest to budget.
  - Filters live in the URL (`?brand=2&editor=5&attention=1`). A ghost **Clear filters** shows at the end of the row while any are on.
- **Count line:** "9 videos being made · 2 need attention" (meta). "· 2 need attention" is left out when it's 0. When filtered: "3 of 9 videos".

## Phone (390) and tablet (< 1024)
- **Header:** "In production" (page 26), then the count line (meta).
- **Search and Filters:** one row, the search field plus a **Filters** button (44px, `shrink-0 whitespace-nowrap`), as on Scripts. The sheet holds Brand, Editor, Needs attention and Sort as 44px controls, with a ghost **Clear filters** at the bottom while any are on.
- **Rows** are stacked cards (16 padding, 12 apart), each a link to the video:
  ```
  ┌──────────────────────────────────────────┐
  │ ┌56×88┐ Bo tries salmon · B (card)      › │
  │ │     │ ● Iron Paws · Sam (meta)          │
  │ │     │ Clips · 3 h ago (meta)            │
  │ └─────┘ 380 of 420 credits · $39.06 (meta)│
  │ [! Didn't finish] (badge)                 │
  │ Clips: take 2 of clip 3 didn't finish.    │
  │ Credits were returned. (meta)             │
  └──────────────────────────────────────────┘
  ```
  The flag badge and its reason go under the picture row, at full width.
- **Tablet (768):** the same cards, 2 columns.
- No action bar: there's nothing to do here but look and open.

## States
| State | What shows |
|---|---|
| Loading | The filter row renders at once, then 5 row skeletons (cards on phone) in the row's shape: a poster block and two lines. |
| Nothing being made | `Clapperboard` icon. **Nothing is being made right now.** "Videos show up here when someone starts a version from the library." No button. |
| Nothing needs attention (toggle on) | `Check` icon (success). **Nothing needs attention.** "Every video is moving." Ghost **Show all**. |
| No match | "Nothing matches these filters." Ghost **Clear filters**. |
| Error | Danger banner "Couldn't load the videos being made. Check your connection." **Try again**. Rows already shown stay. |
| Not the owner | "Page not found." |
| Fresh data | The list refreshes every 30 s while the page is open, and when the tab comes back into focus. Nothing jumps: new flags appear in place, and the order changes only on a reload or a filter change. |

## Words and icons
- **Icons:** `Clapperboard` for the page, `Film` for the poster fallback, `CircleAlert`, `TriangleAlert`, `Clock`, `Check`, `Search`, `ChevronRight`.
- **Never shown:** job ids, model or provider names, "project", raw statuses ("queued", "running", "failed").

## Data the screen needs (server)
This is for Builder-Server. It reads existing tables only, and nothing about generation changes.
- `GET /production?brand_id&editor_id&attention&q&sort&limit&offset` (owner only; 404 for editors, like Approvals). It returns `X-Total-Count`, plus per row:
  - `project_id`, `brand {id, name}`, `script {id, title}`, `letter`, `editor {id, name}`
  - `step`: `breakdown | assets | storyboard | clips | downloads`
  - `last_activity_at`
  - `credits_used`, `budget_credits`, `spent_usd`
  - `poster_file_id`
  - `flag`: `failed | stuck | idle | null`, with `flag_since`, `flag_job` (a plain job name, e.g. "Making the takes") and `flag_problem` (the failed job's plain sentence)
- **Flags, worked out on the server:**
  - `failed`: the video's newest job failed and no job has started since.
  - `stuck`: a job has been queued or running for over 30 min.
  - `idle`: no job or edit for 48 h, and the video isn't done.
  - When more than one applies, the order is failed, then stuck, then idle.
- `GET /production/summary` returns `{in_production, needs_attention}` for the header count and the rail badge.
- Videos that are "Video done", and videos made before scripts, aren't returned.
