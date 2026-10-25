# Making a video from a version: Breakdown, Assets, Storyboard, Clips, Downloads

This replaces the six steps in `phase3/screens/video.md` for new videos. Old videos (made before scripts) keep the six-step page as built. Plan: `../workflow-v2.md`, decisions a, b, c, h, j, k and l. Mock: `assets-downloads.png`.

## Frame
The #179 frame (the one-line phone header, step picker, one Next, Back) with **5 steps: Breakdown · Assets · Storyboard · Clips · Downloads**.
- **Header:** ‹ Scripts, then the title: "Bo tries salmon · B". Under it (meta): "Variation of A · reserved for Sam".
- **Credits:**
  - **Reed's library versions:** the budget meter appears once Breakdown has run, showing "84 of 420 credits".
  - **An editor's own script:** "This week: 32 of 145 credits" instead, on every step.
- **Script button:** opens this version's words (read-only).
- **Reserved:** opening someone else's reserved version shows the version panel, never this page (decision c).

## 1. Breakdown
#186's editor, with these changes:
- **The video's copy:** it starts from Reed's saved breakdown when there is one, with a banner (`Info`): "Planned by Reed. Changes here only affect this video." (decision k). Otherwise it runs automatically when the step opens: "Planning shots… 10 s", with no button to press.
- **Shape and platform** move here from the old brief, as a row above the shots:
  - **Shape:** segmented 9:16 · 1:1 · 16:9, with "More shapes" for the rest
  - **Where will it be posted?:** a select
  - Changing the shape after storyboard frames exist warns: "Frames were drawn for 9:16. Changing the shape redraws them."
- **Budget (decision h):** the step bar's meta reads "4 clips · 28 s · about 210 credits · budget 420". The budget is set when the breakdown is made, at twice its estimate.
  - If twice the estimate would go over $75: a danger banner, "This version would cost more than one video can (729 credits). Shorten it here: join or remove shots." The amber Next stays disabled with that reason.
  - Editors on their own script see their weekly line instead of a budget.
- **Checks:** the montage check counts hand and screen inserts, and no problem is a dead end.
  - Every problem has **Go to**, plus either a fix in place or **Keep it anyway** (ghost). Keep it anyway marks the problem "Kept · Reed will see it" (meta) and stops it blocking Next.
  - Only the $75 cap blocks for good.
- **Next: Assets.**

## 2. Assets (new)
Everything this version needs on screen, approved before anything is drawn.
- **Sections:** Cast · Places · Products · App screens. Each is a grid of cards: 3 per row on desktop, 1 per row on phone.
- **Cast** comes from the script's cast list (writing step 5, Reed #197): one card per role, shared by every version. **Background people** (guests, crowds, extras) aren't listed; they're made inside each scene.
- **Locked role** (decision e):
  - the look's sheet (9:16 front), the role and kind ("Mia · Main"), and a badge `Lock` "Locked by Reed"
  - already approved, with no buttons
- **Unlocked role** (as built tonight; Producer, 2026-10-25):
  - the role, the kind, the description (meta, 2 lines), and "In 3 shots"
  - **Use a Cast & places character** (secondary) picks one of the brand's characters for this video. Picking another one swaps it.
  - **Make a look** (secondary) makes a new character in Cast & places from the role's name and description, gives it to this video, and opens its sheet panel to draw and approve it. The new character stays in the brand's library for later videos.
  - The Assets step never approves, unapproves or redraws a character that's already in Cast & places. It only picks, swaps or makes a new one. A shared character's sheet changes on its own page.
  - the badge "Needs a look" (warning) until the role's character has an approved sheet
  - Later (gaps #19): a look kept for this video only, which doesn't touch the brand's library.
- **Place:** the same as an unlocked role, with 16:9 sheets.
- **Product:** the brand's product picture.
  - For brands with flavours, a flavour picker (cards with the 1:1 picture, as the old brief had). Iron Paws picks its bag here.
  - The pick applies to every shot that shows the product.
- **App screens:** the screens named in the breakdown, read-only, with the "Always used for" badge. There's nothing to approve.
- **Step bar:** "6 assets · 4 approved". The amber button:
  - Next is disabled with "Approve every asset first (2 left)" while any aren't approved.
  - When the only things left are unmade looks: **Make 2 looks · N credits** (it makes all of them).
- **States:**

  | State | What shows |
  |---|---|
  | Loading | Card skeletons |
  | Drawing a look | Skeleton with "Drawing… 14 s" |
  | Failed look | "Didn't finish · credits returned", **Try again · N credits** |
  | Success | Toast "Every asset approved. Next: the storyboard." |

## 3. Storyboard
As specced in `phase3/screens/video.md` §4. **Make storyboard** writes the frames and draws the stills in one press. Each frame uses the approved assets, so the "needs an approved sheet" block no longer happens here: Assets prevents it.

## 4. Clips
As specced in `phase3/screens/video.md` §5, with the prompt review kept (decision b):
1. **Write clip prompts · N credits**
2. Read each prompt: **Looks good** / **Edit**
3. **Make the takes · N credits**, disabled until every prompt is marked Looks good
4. Review each take: **Looks good**, or **Needs a change → Redo**

Every redo adds a take, and the takes stay listed (they're downloadable in step 5).

## 5. Downloads (replaces Final video; decision a)
```
Downloads (section)                                      [Download all clips (.zip)]  amber
4 clips · 28 s · 9:16 · every clip approved (meta)

┌ The whole video ───────────────────────────────────────────────────────────┐
│ [player 9:16, max 360 wide]   Bo tries salmon · B.mp4 · 28 s · 14 MB       │
│                               [Download MP4] (secondary)                   │
│                               Made from Clip 1 Take 2, Clip 2 Take 1, …   │
└────────────────────────────────────────────────────────────────────────────┘
Each clip (section)
┌ Clip 1 · 8 s ─────────────────────────── [Download] (secondary dense) ┐
│ [thumb 9:16] Take 2 · picked                                          │
│ ▸ Older takes (1)  →  Take 1 · made 10:42 · [Download]                │
└───────────────────────────────────────────────────────────────────────┘
```
- **Download all clips (.zip)** (amber, `Download`): the picked take of every clip, in order, named `bo-tries-salmon-b-clip-1.mp4`, and so on. The .zip is `bo-tries-salmon-b-clips.zip`.
- **The whole video:**
  - The stitched MP4, as today. It's made free the first time someone opens the step: "Putting your clips together… 20 s".
  - If a clip changed later: "Out of date" (warning), with **Make it again** (free).
- **Each clip:** the picked take's Download, and an **Older takes (n)** disclosure listing each earlier take with its time and its own Download.
- **Done:** the version's chip becomes "Video done", and the toast says "Video done. Downloads stay here."
- **Phone:** Download all clips sits in the action bar. Clips are stacked rows, each with a 64px thumbnail.
- **States:**

  | State | What shows |
  |---|---|
  | Making the .zip | The button is busy: "Packing 4 clips…" |
  | Error | "The download didn't start. Nothing was lost." **Try again** |
  | Not reachable | Before every clip is approved: "Approve every clip first (1 left)" |

## Release this version, and Archive video (gaps #5)
Each version is made only once, so a version started by mistake must be able to go back.

**Release this version**
- **Who:** the editor who reserved it, or Reed. It's only shown while the version is in production (not once it's "Video done").
- **Where:**
  - In the video header's `Ellipsis` menu: **Release this version** (`Undo2`).
  - Also on Reed's In production rows, in a row `Ellipsis` menu.
- **Confirm** (dialog on desktop, sheet on phone):
  - Title: "Release version B?"
  - Body: "It goes back to Ready to make, so it can be started fresh. This video and its clips are archived, not deleted. The 84 credits already used stay used."
  - When nothing was spent, the last sentence is left out.
  - Buttons: **Release** (danger) / **Keep making it** (ghost).
- **After:**
  - The page goes to Scripts. The chip reads "B · Ready to make" again.
  - Toast: "Version B is ready to make again." with **Undo** (8 s). Undo reserves it for the same person and restores the video at the step it was on.
  - Starting it again later makes a new video from the version, with Reed's saved breakdown if there is one.

**Archive video**
- **Who:** Reed on any video. An editor on videos made from their own scripts.
- **When:** for a video that's "Video done" or made before scripts. (A version still in production is released instead, which archives its video.)
- **Where:** the video header's `Ellipsis` menu: **Archive video** (`Archive`).
- **Confirm:**
  - "Archive "Bo tries salmon · B"? It leaves the lists. Its clips and downloads are kept, and you can restore it."
  - Buttons: **Archive** (danger) / **Keep it** (ghost).
- **After:**
  - Toast: "Archived "Bo tries salmon · B"." with **Undo** (8 s).
  - A done version keeps its "Video done" chip, because it was made once. The chip opens the archived video read-only, with a banner "Archived" and **Restore** (secondary).
- **Finding it later:** Usage → a brand → Videos gets the status **Archived**. Each archived row has **Restore**.

## Data the screens need (server)
- **Release and archive:**
  - `POST /projects/{id}/release`: archives the video and puts the version back to Ready to make. It refuses once the version is "Video done".
  - `POST /projects/{id}/archive` and `POST /projects/{id}/restore`. Restore after a release reserves the version again for the same person, and refuses if someone else has started it since: "Sam started version B again, so this video can't come back."
  - Archived videos keep every take and file.
- **The video:** a video made from a version, holding its own copy of the breakdown, plus shape and platform.
- **Budget:** set when the breakdown is made (twice its estimate, capped at $75). Editors' own scripts are charged to their weekly allowance instead, and refused past it.
- **Kept problems:** a "keep anyway" flag per breakdown problem.
- **Assets:** `GET /videos/{id}/assets` lists the cast slots (from the script's cast, locked ones with their sheet), places, products and screens, each with its state. Per asset: make a look from the role description (paid), use a library character, approve, and pick a flavour.
- **Downloads:** the takes listed per clip, with times; `GET /videos/{id}/clips.zip` for the picked takes; and the stitched video, as today.
