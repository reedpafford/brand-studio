# New video (`/b/:brandId/projects/new`) and Edit brief

One column, max 680px, centred on desktop. On phones the amber button sits in the action bar.

## Order (required first)
1. **Title** (input). Placeholder: "e.g. Bo tries salmon".
2. **What's it for?** (textarea, 4 rows, counter "0 / 2,000"). Helper: "A few lines is enough. Claude turns it into a script."
3. **Planned length (seconds)** (number, 44px, `inputmode=numeric`). Helper: "Budget: {2×s} credits (twice the length)." There is no length limit. The only hard limit is the per-video cap, checked when the video is made: if the server refuses the plan, its words show below the field in `danger`, with a `CircleAlert` icon, e.g. "This plan would cost more than one video can (729 credits). Shorten it or ask Reed." Editors never see dollars.
4. **Who's in it**: character chips with a picture, checkbox-style, 44px tall, in a wrapping row. Characters without an approved sheet:
   - show greyed, using the disabled colours
   - add the meta line "Needs an approved sheet" under the chip
   - can't be picked, but are focusable, with that reason
5. **{Product}** (one group per product, e.g. "Bag"): flavour cards with a 1:1 picture and the flavour name.
   - 2 per row on phone, 4 on desktop.
   - The chosen card gets a 2px amber ring and a `Check` badge top right.
   - A product with only one flavour is chosen for you.
6. **More options** (a disclosure row, 44px, `ChevronDown`, closed by default):
   - **Where will it be posted?** (select: TikTok, Instagram Reels, YouTube Shorts, Other)
   - **Shape** (segmented: 9:16 · 1:1 · 16:9; "More shapes" reveals 4:3 · 3:4 · 21:9)
   - **Kind of video (optional)**
   - **Adapt a reference reel (optional)**:
     - A list of rows, not a wall of cards. Each row has a 16:9 thumbnail (96px), the name (card 17), the logline (meta, 2 lines), and the length.
     - Picking a row opens **What to replace** (textarea) under it. Helper: "For example: the sneaker montage becomes a fomo trading montage. Claude keeps the rest of the reel's story."
     - Tap the picked row again to clear it.
   - **Your own example video (optional)**: upload link with `Upload`. Helper: "Saved with the project so your team can see what you had in mind. Claude does not watch it yet."
7. **Amber button: Create video.** When disabled, the reason sits under it: "Add a title first", "Pick which bag first", "Pick at least one character with an approved sheet". The last applies only if the brief names a character the brand requires. Otherwise cast is optional.

## Edit brief (step 1 of a video)
- The same fields, pre-filled, with **Save brief** (amber) and **Cancel** (ghost).
- While editing, the step's Next button hides.
- When a script exists, a meta line sits above the buttons: "Saving doesn't rewrite the script or the steps after it. Redo them if the change matters."
- **Read view** (not editing):
  - Each field as label + value. Cast shows as picture chips; the flavour as a small picture + name. The reel shows as "Adapting: {name}", with "Replace: …" under it.
  - **Edit brief** (secondary, `Pencil`).
  - The Next button: **Next: Script**.

## States
| State | What shows |
|---|---|
| Loading | Field skeletons. The cast and flavour rows show 4 chip skeletons. |
| No characters | In "Who's in it": "No characters for {brand} yet." with the link **Add one in Cast & places**. |
| No reels | The reel row is hidden. |
| Error on create | Danger banner above the button, with the server's words. The fields keep their values. |
| Success | Go to the video at Script. Toast: "Video made. Next: the script." |
