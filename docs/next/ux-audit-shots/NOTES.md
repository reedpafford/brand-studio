# UX audit screenshots: notes

Taken 28 Oct 2026 on the `ux-audit` branch, run locally with `web/e2e/start-server.sh` (throwaway SQLite database, `BS_FAKE_PROVIDERS=true`, `BS_GENERATION_ENABLED=false`) and the Vite dev server. Nothing was paid for and nothing remote was touched.

People: **Reed** is the owner. **Maya** is an editor, invited and signed in through the local API. Brand: **Iron Paws**, which the app sets up by itself.

Files are named `NN-<width>-<screen>.jpg`. At 390 px each shot shows the whole page in one tall window, so the fixed action bar and bottom tab bar are at the bottom of the image. At 1280 px each shot is a full-page capture. "Amber buttons" counts the filled amber (primary) buttons, and the desktop count includes the amber current-step pill.

**What the stand-ins change.** Some text on screen comes from the free stand-ins, not from real output: the breakdown is always "INT. TEST — DAY", with "A plain test shot for script line N", Hook "Local test breakdown." and "Plain grey."; Variation B has its spoken words in reverse order; stills and clips are grey boxes. These notes do not count any of that as a problem. All credit figures are the stand-ins' prices, and Usage shows "$0.00" because nothing was really charged.

---

## Script Library (brand home)

### 01-390-library-owner.jpg / 01-1280-library-owner.jpg
Reed's Scripts page for Iron Paws with two scripts: "Morning walk" (A · Writing) and "Crusty eyes pitbull" (A · Ready to make).
- **Amber buttons: 1** ("New script"), which is fine. At 1280 it sits next to "Bulk create" and "Import a reel", and there are 8 filter controls (Status, Length, Reference, Versions left, Mine, Deleted and archived, Brand, Sort) before the list starts.
- The Sort box cuts off its own value: "Recently changec".
- At 390 "Bulk create" is an icon-only button (a stack of layers) next to the title, with no words.
- Under the list there is a separate button: "New video (the earlier way)". It asks a new user to choose between two ways of making a video, and "the earlier way" means nothing to them.
- "Length set at Breakdown" uses a step name as if it were plain English.
- Script titles are 23 px tall links. The whole row can be tapped, so this matters less.

### 02-390-library-videos-view.jpg
The "Videos" side of the Scripts | Videos switch, after Maya finished one video.
- The page heading still says "Scripts" while "Videos" is selected.
- The video is shown as "✓ Video done". At this point its storyboard was "out of date" and its Clips and Downloads steps were locked (see 26–30). In production says "0 videos being made" (41) and Usage counts it as Finished (42), so three screens say it is finished when it is not.

### 13-390-library-editor.jpg
The same library as Maya (editor) sees it.
- The Status filter starts at "Ready to make" for editors (you can see it behind the panel in 14-1280), so Maya sees 1 script while Reed sees 2. Nothing on screen says that a filter is already on.
- Editors also get "New script", "Import a reel", Bulk create and "New video (the earlier way)". That is 4 ways to start something new, with "New script" as the only amber button.

## Version panel

### 14-390-version-panel-editor.jpg / 14-1280-version-panel-editor.jpg
Maya opens "Version A, ready to make".
- **Two different prices next to each other:** "About 21 credits to make" and the button "Make this version · 3 credits". It is not clear which one she will pay.
- At 390 the script text fills the sheet, and "Make this version" is pushed to the bottom edge, mostly out of view. She has to scroll inside the sheet to find the only action.
- Internal wording: "Everyone is made at Assets"; "Planned automatically when you start".

## Writing flow (owner)

### 03-390-write-script-empty.jpg / 03-1280-write-script-empty.jpg
Script step of a new, empty script.
- **Amber buttons: 0.** "Save script" and "Next: Directions" are both greyed, both with the reason "Write or paste the script first". The only button that works is "Have Claude write it for me · 6 credits", and it is grey, not amber.
- At 390 that button's label wraps to two lines ("Have Claude write it for me · 6 / credits").
- In the desktop step bar, "Variations" can be opened while Directions, Cast, Breakdown and Publish are locked ("Write the script first"). You can reach Variations before the script has any words.
- "Draft · only you can see it" appears both as a badge and in the page's own words.

### 04-390-write-directions.jpg
Directions step.
- The explanation box contains "Edit the script" as a ghost button, next to "Suggest directions · 3 credits". That makes 3 actions, plus "Next: Variations" in amber.
- The script is shown in a narrow monospace box at 390, so every line wraps ("SCENE 1 — EXT. PARK — / MORNING").
- After "Suggest directions" ran (the shot was deleted because it looked the same), the only feedback is one small grey line: "This script already reads well. Nothing to suggest." Nothing else on the page changes.

### 07-390-write-variations-written.jpg / 07-1280-write-variations-written.jpg
Variations step after writing 1 variation (6 credits).
- **Amber buttons: 0.** "Next: Cast" is greyed: "Approve or remove variation B first." "Approve all", "Approve", "Edit" and "Regenerate · 6 credits" are all grey too, so nothing shows what to do next.
- At 390 the toast "Variations ready. Read them side by side." sits over the action bar and covers "Next: Cast". Also, "side by side" is impossible at 390, where A and B are tabs.
- **"A · Original" is badged "Words final"** while the script is still a Draft.
- "Changes only" is a 20 px checkbox, which is under 44 px.
- Before writing (screen not kept), the step reads "Optional. Most scripts go out as one version." with None | 1 | 2 (36 px tall at 1280).

### 08-390-write-cast.jpg
Cast step.
- Each role says "Made at Assets" and has a button "Lock to a look". Both are internal phrases.
- Every role has "A practice look." as its description (stand-in text).
- Each role has an extra "…" menu on its own line.
- "Find roles again · 3 credits" is the top action, even though the roles were already found.

### 10-390-write-breakdown-preview.jpg
Breakdown step after "Make the breakdown · 3 credits".
- Tabs read "A · Planned" and "B". The line under them reads "Planned · 14 s · 1 clip · about 24 credits to make", while the version panel later says "About 21 credits to make" for a similar script.
- **Edit buttons everywhere:** Hook, scene heading, look, every shot and "End" all have their own "Edit", about 12 on one screen. Each shot also has a "Line N" button and a "…" menu. At 1280 these are all 36 px tall.
- The last shot (1.7) has no "…" menu, so its "Line 7 / Edit" sits out of line with the rows above.
- Internal words: "Clip c1", "End line", shot ids "1.1"–"1.7".
- "Make it again · 3 credits" sits beside another "…" menu.

### 11-390-write-publish.jpg
Publish step.
- **Amber: "Publish 2 versions"**, but variation B was never approved. Its card says "Words: When you publish". The Variations step blocked Next with "Approve or remove variation B first.", but going to Publish through the step picker skips that check, so an unread variation gets published.
- Cast chips say "Woman · made at Assets", "Bruno · made at Assets".
- "Breakdown: Runs when an editor starts" (B) next to "Planned · 14 s" (A).

### 12-390-write-step-picker-sheet.jpg
The phone step picker, opened from "Step 6 of 6 · Publish".
- Script, Cast and Breakdown have ticks. Directions and Variations show numbers, even though both were visited and Variations was written. Directions was "nothing to suggest", and Variations has an unapproved B, so the ticks don't match what was done.
- Rows have no reason or status text, unlike the video step picker (29).

## Editor video page

### 15-390-video-breakdown.jpg / 15-1280-video-breakdown.jpg
Maya's video at Breakdown, right after "Make this version · 3 credits".
- **Amber: "Next: Assets" (1)**, which is fine. On arrival a toast also says "Version A is yours. Next: the breakdown."
- **Assets already has a tick** in the step bar before Maya has opened it (there were 0 assets).
- Length doesn't match: the library and version panel say "about 11 s". This screen says "1 scene · 8 shots · 1 clip · 22 s of 22 s planned" and "Clip c1 · 22 s".
- The meter says "3 / 67 credits · 5%". Nowhere does it say what 67 is (the video's budget).
- Shape is 6 boxes (9:16 … 21:9), 36 px tall at 1280. "Where will it be posted?" defaults to "Other".
- "Redo · 3 credits" is the only other big button, and it throws away the plan.
- The same Edit clutter as 10: Line N / Edit / … on every shot, all 36 px at 1280.

### 16-390-video-assets-loading.jpg
Assets while the list is loading. The load was slowed down by the test script so it could be caught.
- **"Loading assets…" shows 3 times on one screen:** under the heading, in the pane, and as the reason under the greyed "Next: Storyboard". There are also three empty grey boxes.

### 19-390-video-assets-done.jpg
Assets when finished, for the first time through.
- "0 assets · 0 approved", yet the page shows a Cast card and two product cards.
- Cast: "Pitbull — Not in this video's shots", even though every spoken line is "PITBULL (V.O.)". The stand-in breakdown is probably the cause.
- **The bag flavour must be tapped first.** Before that, Next said "Pick a bag flavour first". The cards (Chicken / Peanut butter) look like pictures, not choices, and nothing above them says "pick one".
- Amber: "Next: Storyboard" (1).
- No auto-looks countdown appeared the first time, because there was nothing to make (see 27 for the countdown).

### 20-390-video-storyboard-before.jpg
Storyboard before anything is made.
- Amber: "Make storyboard · 4 credits" (1). Next is greyed: "Make the storyboard first". This screen is clear.

### 21-390-video-storyboard-stills.jpg / 21-1280-video-storyboard-stills.jpg
Storyboard with one still made, before approval.
- **Amber buttons: 0.** "Approve all", "Approve", "Make another · 1 credit" and "Redo storyboard · 4 credits" are all grey. "Next: Clips" is greyed: "Approve every storyboard frame first (1 left)".
- **Three different prices for "try again":** "Make another · 1 credit", "Change it · 4 credits", "Redo storyboard · 4 credits".
- The heading is said twice: "Storyboard" (page) and "Storyboard · 1 frame · 0 approved" right below.
- With only one frame, "Approve all" and "Approve" do the same thing.
- Internal words: "c1 · shot 1.1", "Advanced: edit the prompt".
- "Change it · 4 credits" is greyed with "Say what should change", which is fine. At 1280, Approve, Make another and Advanced are 36 px tall.

### 22a-390-video-clips-no-prompts.jpg
Clips before prompts exist.
- Amber: "Write clip prompts · 3 credits". The toast "Approved 1 frame. Undo" covers the action bar and "Next: Downloads".

### 22-390-video-clips-before-looks-good.jpg
Clips with the prompt written, before "Looks good".
- **"Make clip · 22 credits" is greyed with no reason under it.** The reason is far away, in a line above the card: "Read each prompt and press Looks good before the takes are made (1 left)."
- **Amber buttons: 0.**
- The raw model prompt is shown to the editor: "Audio: only the spoken lines and room sound. No subtitles. [Storyboard frame] is the first frame. Summary: Test clip. Shot 1 | 0-3 s. …", plus "Show all".
- The word "Clips" appears twice ("Clips" heading, then "Clips · 1 · 0 approved"). There is also a "Not made" badge and "c1 · 22 s".
- "Change the prompt · 3 credits" is greyed: "Say what should change".

### 23a-390-video-clips-making.jpg
Straight after the take was started ("Make the takes · 22 credits").
- The badge says "Queued 2s". The meter already reads "31 / 67 credits · 47%", which was 9 a moment earlier: the money is shown as spent before the clip exists.
- **A green "✓ Looks good" badge shows on a clip that hasn't been made yet.** It means the prompt was OK'd, but it reads as if the clip was approved.
- "Make clip · 22 credits" is greyed again with **no reason** while it is queued.
- "Undo" sits next to it with no hint of what it undoes (the prompt "Looks good").

### 23-390-video-clips-takes.jpg / 23-1280-video-clips-takes.jpg
Clips with one take made.
- **Amber buttons: 0.** "Approve all", "✓ Looks good", "Make another take · 22 credits" and "Download" are all grey or links. "Next: Downloads" is greyed: "Approve every clip first (1 left)".
- **"Looks good" now means something else.** Before, it meant "the prompt is OK". Now "✓ Looks good" approves the take. Same words, different job.
- **Prices:** "Change it and make a new take · 3 credits" next to "Make another take · 22 credits". A changed take looks 7× cheaper than a plain retake.
- "Takes: (•) Take 1" is a single radio button, 20 px tall at 390. The take's "Download" is a small underlined link beside a 22-credit button.

### 24-390-video-downloads.jpg / 24-1280-video-downloads.jpg
Downloads with the finished video. It was put together on its own after approval.
- **The amber button is "Download all clips (.zip)", but the main thing is the finished video,** whose "Download MP4" is a grey secondary button. An editor who wants the video will press the wrong one.
- "Made from: Clip 1 Take 1", "Take 1 · picked". The "Approved 1 clip. Undo" toast also covers the action bar on arrival (in the earlier shot, deleted).

### 25-1280-video-breakdown-unsaved-edit.jpg
Maya edits shot 1.1's action after the video is finished.
- The bar "You have unsaved changes. [Save changes] [Discard]" floats **over the shot list** and hides shots 1.2/1.3 behind it.
- Next is greyed: "Save your changes first."
- Nothing warns that saving will make the storyboard, clips and finished video out of date.

### 26-1280-video-breakdown-after-edit.jpg
After "Save changes".
- The step bar now reads "Storyboard · out of date". Clips and Downloads are locked with "Redo the out of date frames first". The finished MP4 can't be reached from here any more.
- Under the line "22 s of 22 s planned" a tiny "· edited" is the only change in the Breakdown itself.

### 27-390-video-assets-countdown-after-edit.jpg / 27-1280-video-assets-countdown-after-edit.jpg
Opening `?step=storyboard` after the edit **lands on Assets** instead. The edited shot now has the Pitbull in it, so a look is needed.
- **The auto-looks countdown starts by itself:** "Making looks for Pitbull · up to 4 credits (usually 2) — Starting in 1 s — Not now". Maya pressed nothing, and in 5 seconds credits are spent unless she finds "Not now".
- The 1280 shot was taken once the countdown had fired: the banner says "Making looks for Pitbull · up to 4 credits (usually 2)" while the card below still offers "Make a look · up to 4 credits" and says "Needs a look". The two say opposite things.
- Price wording: "up to 4 credits (usually 2)", "Usually 2. Anything not used comes back."
- The meter read 31 → 34 here → 36 on the next screen. The banner on the next screen says "Made 1 look · 2 credits".
- Amber buttons: 0 at 390.

### 28-390-video-assets-look-to-approve.jpg
The look is made. (The URL asked for `?step=downloads`, and the app sent Maya to Assets.)
- "Made 1 look · 2 credits. Check each one, then approve." "Needs your approval", "This video only".
- **Amber buttons: 0.** Approve all, Approve and "Use a different character" are all grey. "Change it · up to 2 credits" is greyed: "Say what should change".
- The look picture is an empty grey box (stand-in).

### 29-390-video-step-picker-locked.jpg
The phone step picker on Assets after the edit.
- Storyboard, Clips and Downloads each repeat the same reason, "Approve every asset first (1 left)", 3 times. Nothing tells the editor that her finished video is behind these locks.

### 30-390-video-storyboard-out-of-date.jpg
Storyboard after approving the new look.
- Badge: "Breakdown changed: redo this frame". **There is no "Redo this frame" button.** The choices are "Make another · 1 credit", "Redo storyboard · 4 credits", or "Change it · 4 credits" (greyed).
- **"Approve" is greyed with no reason.**
- "Next: Clips" is greyed: "Redo the out of date frames first".
- **Amber buttons: 0.**

## Studio pages (owner)

### 40-1280-approvals.jpg
- "Nothing waiting." The page then explains its own history: "Editors are never sent here any more: past a budget or their week, their button gives the reason. Requests from before 26 Oct show here until they're handled."
- The top bar has its own "Approvals" button (a bell at 390) on every page, as well as the sidebar link, for a page that is almost always empty.

### 41-390-in-production.jpg
- "0 videos being made" / "Nothing is being made right now." Maya's video was out of date and needed a redo at this point, so this page can't be used to spot videos that are stuck.
- Search box placeholder: "Search scripts" on a page about videos.

### 42-390-usage.jpg / 42-1280-usage.jpg
- **Usage is in dollars ("Spent $0.00", "Cost per finished video $0.00", "$0.00 each"). Every other screen uses credits.** No screen shows how credits convert to dollars, apart from Team (43).
- "Finished 1 video" for the video that is out of date (see 02).
- "0 versions left" for Iron Paws, which still has the unpublished "Morning walk".
- At 1280 the period tabs (This week / This month / All time) and brand-name links are 36 px and 18 px tall. "Every charge" is a collapsed section at the bottom.

### 43-390-team.jpg / 43-1280-team.jpg
- Amber: "Invite someone" (1).
- Credit limits are in credits with a dollar figure under them: "145 credits ≈ $14.91 a week", "Most one video can cost 729 credits ≈ $74.94 … A video's budget is twice its estimate, up to this."
- "Free generation for each editor's own scripts and quick clips" is unclear: "free" next to a credit allowance.
- "Save" and "Save limits" are both greyed with "No changes yet".

### 44-390-quick-clip.jpg
- "This week: 24 of 145 credits" at top right (owner).
- **"Improve prompt" is greyed with no reason** (its reason should be that the box is empty).
- Technical words: "Seedance 2.5 · 4–30s · up to 720p", "adaptive", "480p / 720p".
- "Generate · 8 credits" is greyed: "Describe the clip (8 or more characters)".
- **Amber buttons: 0.**

### 45-390-cast-and-places.jpg
- One page, three names: the bottom tab says "Cast", the desktop sidebar says "Cast & places", and the page heading says "Library" (tabs Characters / Places / Props).
- "No characters for this brand yet." The Pitbull look Maya just made doesn't show here (it was "This video only").
- "Show archived" is a 13 px checkbox.

### 46-390-brand.jpg
- **The End line example mentions the wrong brand:** "Example: "Want to trade like me? Download fomo through the link in my bio."" is shown on Iron Paws' Brand page.
- The "Add" buttons for Fonts and Never say are greyed with **no reason**. "Save changes" is greyed: "No changes yet".
- The tabs "Products 1" and "App screens 2" are on a dog-food brand.
- **Amber buttons: 0.**

---

## Things I could not reach (and why)

- **Auto-looks countdown on a first visit to Assets.** The stand-in breakdown put no character in any shot ("Not in this video's shots"), so the first time through there was nothing to make. The countdown was caught after editing a shot instead (27).
- **A breakdown with problems listed.** The stand-in breakdown never reports problems, so there is no "problems" screen.
- **A failed job / stale failure message.** The stand-ins don't fail, and I didn't change app code to force a failure.
- **An "out of date" Clips or Downloads page.** After the edit, both stay locked behind Assets/Storyboard, and their URLs redirect (28 was requested as Downloads and landed on Assets). What the editor actually sees is shown in 26–30.
- **Approvals with something waiting.** The page says editors are no longer sent there.
- **The earlier "New video (the earlier way)" page, Bulk create and Import a reel** were not captured, to stay within the shot budget.
- Dropped as near-copies of other shots: the Directions result, the empty Variations step, the empty Breakdown step, the toast-only Downloads view, the Storyboard on its first load, Downloads after the edit (it redirected to Storyboard), and desktop copies of plain screens.
