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
  - **Cast mismatch** ("Shot 1.1: the script has Nate proposing, but the shot shows Mogging BF.") has a free **Put the right cast in each shot** (`change-notes.md` §2).
  - **Advice is shown apart from problems** (Reed, 2026-10-25). This applies to the breakdown, storyboard frames and clips alike.
    - Problems that need fixing stay as they are: danger rows with **Go to**.
    - Advice (lines the server marks "Advice: …") goes under one closed disclosure, **Advice (3)**. It's neutral in tone (`text-muted`, `ChevronRight`/`ChevronDown`, no danger colour), sits under the problems, and its count leaves out advice already kept.
    - Open, each advice line shows without the "Advice: " prefix. It has **Keep anyway** (ghost dense, 44px on phone), and **Go to** when it points at a shot.
    - A kept line stays in the list, muted, with "Kept" for Reed ("Kept · Reed will see it" for an editor).
    - Advice never blocks Next. When there are no problems and no advice, nothing shows.
- **Next: Assets.**

## 2. Assets (new)
Everything this version needs on screen, approved before anything is drawn.
- **Sections:** Cast · Places · Products · App screens. Each is a grid of cards: 3 per row on desktop, 1 per row on phone.
- **Cast** comes from the script's cast list (writing step 5, Reed #197): one card per role, shared by every version. **Background people** (guests, crowds, extras) aren't listed; they're made inside each scene.
- **Locked role** (decision e):
  - the look's sheet (9:16 front), the role and kind ("Mia · Main"), and a badge `Lock` "Locked" (an editor can lock roles on their own script, so it doesn't name Reed; as built in #407)
  - already approved, with no buttons
- **Unlocked role** (as built tonight; Producer, 2026-10-25):
  - the role, the kind, the description (meta, 2 lines), and "In 3 shots"
  - **The description's facts** (Reed, 2026-10-26): it leads with age range, gender and what they do, as a meta line before the rest: "Late 20s · woman · nurse". When the script doesn't say and the facts were inferred, each inferred fact is followed by "(a guess)" in `text-faint`: "Late 20s (a guess) · woman · nurse". The same line shows on the writing flow's Cast step (`variations-characters-publish.md` §5).
  - **Use a Cast & places character** (secondary) picks one of the brand's characters for this video. Picking another one swaps it.
  - **Make a look · up to N credits** (secondary; README rule 2, "When the price can vary"), with "Usually 2. Anything not used comes back." (meta) under it, makes a look for this video only, from the role's name and description, and draws its sheet in the same press, so the price is inside the button (README rule 2). The card then shows the sheet with **Approve**. See "Looks for this video only" below. It never adds anything to Cast & places.
    - Past a limit, an editor sees it disabled with the reason (README rule 2).
    - A step that's free says so in meta beside the button ("Free"), so nothing priced ever looks free, and nothing free looks priced.
  - The Assets step never approves, unapproves or redraws a character that's already in Cast & places. It only picks or swaps one. A shared character's sheet changes on its own page.
  - **Look check** (as built in #494): when a look's sheet doesn't match the role, a note (`warning-soft`) says so in words: "This look reads as a man in his 50s, but Mia is a woman in her late 20s." Its **Fix it with a note** (secondary dense, `Wand2`; as built in #496) only fills **Change this…** with the problem; the paid **Change it · up to N credits** is still the press that spends. Approve stays available. The same note shows in the library sheet panel. Locked roles don't get it.
  - the badge "Needs a look" (warning) until the role has an approved sheet, either a library character's or this video's own look
- **Place:** the same as an unlocked role, with 16:9 sheets. A place made here is also for this video only.

### Missing looks are made on their own (Reed, 2026-10-26)
When Assets opens and a **main or recurring** role has no character, its per-video look is made automatically. Background people never get looks.
- **Price first:** before anything starts, a note (`Info`) at the top of Cast reads "Making looks for Nate, Mia and the Rival · up to 12 credits" (usually 6), with "Starting in 5 s" (meta, counting down) and **Not now** (ghost). Not now stops it, and the cards keep their own **Make a look · up to N credits**. With nothing pressed, it starts after 5 s.
- **Within the money:** it starts only if all of it fits the video's budget (Reed's library versions) or the editor's week (their own script). If it doesn't fit, nothing is made: the note says why in plain words, and the cards keep their **Make a look · up to N credits** (disabled with the reason for an editor; README rule 2).
- **While drawing:** each card shows "Drawing… 14 s". When they land, the note becomes "Made 3 looks · 7 credits. Check each one, then approve." (what it really cost) (`Info`).
- **Still reviewed:** each look lands as "Needs your approval", with **Approve**, **Change this…** (redo with a note), or **Use a Cast & places character** (swap). Next stays disabled until every role is approved, as before.
- Once a role has a look (made, picked, or turned down with Not now), opening Assets again never makes it again.
- **Naming the role, never an id:** anything that says a look is missing names the role and points here. In a problem line, the sentence is followed by an inline link, **Approve a look in Assets** (as built in #476). Elsewhere, it's "Nate needs a look." with **Approve a look in Assets** (secondary). It's never "char:3" or "slot 2". This applies to Storyboard, Clips, the breakdown's problems and server messages shown as they are.

### Looks for this video only (gaps #19; Reed, 2026-10-26)
Only characters and places made in **Cast & places** go into the brand's library. A look made while making a script or a video stays with it.
- **Who owns it:**
  - Made on a video's Assets: that video only.
  - Made in the writing flow's Cast step (`variations-characters-publish.md` §5, Make one): that script, for every version made from it.
  - It's never listed in Cast & places, never offered in another script's or video's picker, and never shown in Usage's library counts.
- **On the card:**
  - The role, the look's 9:16 sheet, and a neutral badge "This video only" ("This script only" for a script's look).
  - Its own sheet buttons, because it belongs here: **Approve**, and a **Change this…** box to redraw it (`change-notes.md` §1). It's paid like any sheet. Its earlier versions stay, and picking one back is free.
  - **Use a Cast & places character** still swaps the role to a library character. The per-video look is kept, with "Not used" (meta), so swapping back is free.
- **Save to Cast & places** (secondary dense, `Users`, in the card's `Ellipsis` menu on phone):
  - **Who sees it:** Reed always. An editor only when Team's **Editors can save looks to Cast & places** is on (`phase3/screens/studio.md`; off by default). With it off, editors don't see the button at all.
  - **Needs an approved sheet.** Before that, it's disabled with "Approve the sheet first".
  - **Asks for a name** (dialog on desktop, sheet on phone): "Save to Cast & places", with **Name** filled with the role ("Mia"), and the meta line "It becomes a normal character any script can use. This video keeps its look either way." **Save** (amber in the dialog) / **Cancel** (ghost).
    - A name already used by a brand character gives the server's words under Name: "Bo is already in Cast & places. Pick another name."
  - **After:** a copy goes into Cast & places as a normal character, with its approved sheet. The video now uses the library character, and the badge becomes the usual library look. The toast says "Mia saved to Cast & places." with **Undo** (8 s). Undo removes the copy and puts the video back on its own look.
  - It's free: copying makes nothing new.
- **Delete this look** (in the card's `Ellipsis` menu, `Trash2`, danger): only on a look made for this video (or script), never on a Cast & places character.
  - **Who:** Reed, or whoever made the video (an editor on their own video).
  - **Only while no role uses it**, which is when the card reads "Not used" (the server refuses otherwise: "Swap the role to another look first."). While the look is in use, Delete isn't offered, so the press never fails. Stills already drawn with it keep their pictures.
  - No dialog: it can be undone.
  - **After:** the look leaves the card, and the role stays on the look it uses now. The toast says "Deleted Mia's look." with **Undo** (8 s), which brings the look back with its sheets and approval.
  - The credits used to draw it stay used.
- **Where per-video looks show:** this video's Assets, Storyboard and Clips chips (the chip reads the look's name, with "This video only" in its tooltip). Nowhere else.
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
As specced in `phase3/screens/video.md` §4, with the plain-English **Change this…** box under each still and the automatic frame rewrite after a cast change (`change-notes.md` §1, §3). **Make storyboard** writes the frames and draws the stills in one press. Each frame uses the approved assets, so the "needs an approved sheet" block no longer happens here: Assets prevents it.

## 4. Clips
As specced in `phase3/screens/video.md` §5, with the prompt review kept (decision b). Each clip has the **Change this…** box, and Edit moves to **Advanced: edit the prompt** (`change-notes.md` §1):
1. **Write clip prompts · N credits**
2. Read each prompt: **Looks good** / **Edit**
3. **Make the takes · N credits**, disabled until every prompt is marked Looks good
4. Review each take: **Looks good**, or say what should change in **Change this…** (**Change it · N credits**)

Every redo adds a take, and the takes stay listed (they're downloadable in step 5).
- **Looks good is kept on the server** (`prompt_ok` per clip, #366), not in the browser. So it holds on every device and for everyone who opens the video. Saving your own edit to a prompt counts as Looks good (you read it to edit it). A prompt that is written again clears it. **Make the takes** stays disabled with "Mark every prompt as Looks good first (1 left)" until every clip is ok. **Undo** clears the flag.

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
  - Body: "It goes back to Ready to make, so it can be started fresh. This video and its clips are archived, not deleted. The 84 credits already used stay used. Anything still being made stops and isn't brought back." (the last sentence as built in #431)
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
  - "Archive "Bo tries salmon · B"? It leaves the lists. Its clips and downloads are kept, and you can restore it. Anything still being made stops and isn't brought back." (the last sentence as built in #431)
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
- **Looks for one video or one script (gaps #19):**
  - A look made on Assets (or in a script's Cast step) is stored against that video (or script), not the brand's library: `owner: {video_id} | {script_id}`, never listed by `GET /library/*`, never offered in pickers elsewhere.
  - Per look: `GET` with its sheet versions and state, `POST …/sheet` (paid, with the change note), `POST …/approve`, `POST …/pick` for an earlier version.
  - `DELETE` on a per-video look, with a restore route for Undo (Builder-Server is adding them). It refuses a Cast & places character.
  - **Auto-make:** `POST /projects/{id}/assets/make-missing` (paid, all or none) makes a look for every main or recurring role with none, and refuses with the plain reason when the budget or week can't cover it. `GET /projects/{id}/assets` adds `missing_looks: {roles: [names], credits}` for the note, and a per-slot `declined` flag so Not now sticks.
  - **Role facts:** each cast slot carries `age_range`, `gender` and `occupation`, each with `inferred: bool`.
  - **No raw ids in messages:** the server's sentences about a missing look name the role ("Nate needs a look").
  - `POST /videos/{id}/assets/{slot}/save-to-library` `{name}`: copies the approved look into Cast & places as a normal character and points the slot at it. It returns the new character id, and the Undo is `DELETE` on it, which puts the slot back on the look. It refuses with 409 "Approve the sheet first" or "{Name} is already in Cast & places. Pick another name."
  - A team setting `editors_can_save_looks` (default false) on `GET/PUT /credits/limits` or `/team/settings`. The save route refuses editors with 403 while it's off.
- **Downloads:** the takes listed per clip, with times; `GET /videos/{id}/clips.zip` for the picked takes; and the stitched video, as today.
