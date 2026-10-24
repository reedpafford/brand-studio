# Videos (the brand's home, `/b/:brandId/projects`)

## Desktop
```
[Reed only] ┌ banner (accent-soft) ───────────────────────────────────────────────┐
            │ 🔔 2 requests are waiting for you                   [Review] (amber) │
            │    Sam's quick clip and a clip redo · 135 credits                    │
            └──────────────────────────────────────────────────────────────────────┘
IRON PAWS (eyebrow)
Videos (page 32)                                                      [＋ New video]  amber
In progress (section 20)                                  4 videos · 1 finished this week (meta)
┌poster 9:14┐ ┌poster┐ ┌poster┐ ┌poster┐        4 columns ≥1280 · 3 at 1024
│[Clips]    │ │      │ │      │ │      │        badge top-left = the step it's at
│           │ │      │ │      │ │      │
│Bo tries…  │ │      │ │      │ │      │        title (card 17) + line (meta, white 80%)
│2 of 3 …   │ │      │ │      │ │      │        meter: credits used of budget
└───────────┘ └──────┘ └──────┘ └──────┘
Finished (section)                          same cards, badge "Ready · 24 s", play button
```
- **Poster.** The newest picture the video has: the final video's first frame, else the latest approved take, else the latest frame, else the brand's first screen on `surface-2` with a `Clapperboard` icon.
- **Card.** The whole card is one link to the video at its current step. `aria-label` is "{title}, {step}, {line}".
- **Step badge** (on-media style): Brief, Script, Shots, Storyboard, Clips, Final video.
- **Second badge**, when relevant:
  - `warn` "Waiting for Reed to approve"
  - `danger` "Didn't finish · credits returned"
  - neutral "Out of date" (final video)
- **Line under the title,** by step:

  | Step | Line |
  |---|---|
  | Brief | "Brief written" |
  | Script | "Draft ready to read" or "{n} words" |
  | Shots | "{n} clips planned" or "{n} problems to fix" |
  | Storyboard | "{a} of {n} frames approved" |
  | Clips | "{a} of {n} clips approved" |
  | Final video | "Ready · {s} s · {shape}" |

- **Meter.** Thin, in the caption area: credits used against the budget. It turns `danger` over 100%. The text "20 of 32 credits" appears only on hover or focus (desktop) and on the phone list. Editors never see dollars.
- **Order.** Most recently changed first. Finished videos sit below "In progress", newest first, showing 8, then **Show all {n}**.
- **Reed's banner** shows only when something is waiting. **Review** goes to /approvals.

## Phone
- The banner, then the title row ("Videos" page 26, plus meta "4 in progress" on the right).
- Posters in 2 columns, gap 12, 9:14, with the title on the picture.
- Action bar: **＋ New video**.

## States
| State | What shows |
|---|---|
| Empty | `Clapperboard` icon in muted colour. Headline **No videos for {brand} yet**. Body: "Start from a brief: what it's for, who's in it and how long. Claude helps with the script." Amber **＋ New video**. |
| Loading | 4 poster skeletons (2 on phone) and a title-bar skeleton. No spinner. |
| Error | Danger banner: "Couldn't load your videos. Check your connection." with **Try again**. Cards already shown stay. |
| Success | Arriving from New video: toast "Video made. Next: the script." and the new card is first, with a 1.5s amber outline. |
