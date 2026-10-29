# UX audit part 6: library, Quick clip, Cast & places, Brand and studio screens

Taken 29 Oct 2026 on the `ux-audit-6` branch, locally only. The API ran through `web/e2e/start-server.sh` (a throwaway SQLite database, `BS_FAKE_PROVIDERS=true`, `BS_GENERATION_ENABLED=false`), next to the Vite dev server on :5173. Nothing was paid for and nothing remote was touched. The servers were stopped afterwards.

Files are named `P6-NN-<width>-<screen>-<role>.jpg`. A 390 shot shows the whole page in one tall window, so fixed bars and bottom sheets appear at the bottom of the image. A 1440 shot is a full-page capture. "Amber" means filled amber (primary) buttons. "Small" means controls under 44 px tall, as measured in the page.

## What was set up (all through the local API or UI, with free stand-ins)

- **People:** Reed (owner, via /setup), Maya (editor), and Sam (a second editor), both invited and accepted through the API. There is one pending invite for jo@example.com.
- **Brands:** fomo and Iron Paws (both come with the app), plus a new empty brand, **Night Owl Coffee**.
- **Iron Paws scripts:**
  - "Crusty eyes pitbull" is published with versions A, B and C. A is "Video done" (Maya made it through to the MP4), B is "In production · Sam" (stopped after the breakdown), and C is "Ready to make".
  - "Itchy paws at night" is published, with A in production by Maya (stopped at Assets).
  - Reed has two drafts, "Morning walk" and "Vet visit idea" (the second has no words).
  - Maya has her own draft, "Maya's park idea".
  - "Bath time chaos" was created and then deleted.
- **fomo:** "First trade nerves" is published, with A in production by Reed.
- **Quick clips:**
  - Four finished: 3 on Iron Paws (2 by Reed, 1 by Maya) and 1 on fomo.
  - One **cancelled** (Maya's): the worker was stopped, the clip was queued, then cancelled through the API.
  - One **failed** (Reed's): it was queued with an uploaded photo while the worker was stopped. The photo was then deleted from the local throwaway storage folder and the worker restarted, so the job failed with "FileNotFoundError". The fake providers never fail an image or video job on their own, so this local trick was the only free way to get a failed row.
- **Cast & places (Iron Paws):**
  - Characters: Bruno (edited once, sheet made and approved) and Dana.
  - "Old mascot" was created and then archived.
  - Places: Sunny kitchen (sheet made, not approved) and Dog park.
- **Team:** the editors' weekly allowance was lowered from 145 to 5 in the Team page (UI), so Maya, who had used 5, is past it.
- **Approvals: a waiting item cannot be made.** In the server, `enqueue` (`server/app/routes/jobs.py`) says editors "are never sent to Reed … so nothing new ever waits as `needs_owner_approval`". Quick clips are hard-coded `needs_owner_approval=False` (`routes/clips.py`), and nothing sets a project to `ProjectStatus.needs_owner_approval`. Only the empty state was captured (22).
- **In production: the true empty state was not captured.** It needs zero videos in the whole studio, and this data has three. Shot 24 shows the filtered empty state (brand = Night Owl Coffee) instead.

**Text that comes from the stand-ins, not counted as problems:**
- Version B's title "Local variation 1", and variations B and C having their spoken words in reverse order.
- Grey boxes for stills, sheets and clips.
- Usage's "$0.00" everywhere, and "No charges yet." in Every charge. The fake media provider records no usage, so nothing shows as charged.
- The credit prices, which are the stand-ins' prices.

---

## 1. Brand switcher and New brand

### P6-01-390-brand-switcher-owner.jpg / P6-01-1440-brand-switcher-owner.jpg
At 390 the switcher is a bottom sheet titled "Brands". It lists "fomo", "Iron Paws" (with ✓) and "Night Owl Coffee", then a divider and "+ New brand". At 1440 it is a dropdown with the same rows.
- All three brands have the same orange dot. The dot only takes a colour once a brand colour is added ("The first colour tints the brand's dot." on the Brand page), so at a glance the dots do not tell brands apart.
- The list has no other information: no number of scripts and nothing waiting.
- On studio pages (In production, Usage, Team) the switcher still shows the last brand visited, for example "Night Owl Coffee" on P6-23 and P6-25 and "fomo" on Team (P6-32). Those pages are not about one brand.

### P6-01-390-brand-switcher-editor.jpg / P6-01-1440-brand-switcher-editor.jpg
Maya sees the same three brands, then the line "Brands are set up by the owner." in place of New brand. This is clear.

### P6-02-390-new-brand-dialog-owner.jpg / P6-02-1440-new-brand-dialog-owner.jpg
A sheet titled "New brand" with a "Brand name" field, the hint "You add its logo, colours and screens next.", and a greyed "Create brand" button with the reason "Give it a name first".
- **Amber buttons: 0** until something is typed. The reason is shown, which is good.
- At 1440 the page behind still shows "New script" in amber.

## 2. Script Library cards

### P6-03-390-library-owner.jpg / P6-03-1440-library-owner.jpg
"5 scripts". Each card shows the title, description, "<author> · <age> · about N s", and version chips.
- "Maya's park idea": "Dog meets a squirrel." / "Maya · 4 min ago · about 4 s" / chip "A · Writing" (Maya's private draft, which the owner can see).
- "Vet visit idea": "Reed · 4 min ago · Length set at Breakdown" / "A · Writing".
- "Morning walk": "… about 4 s" / "A · Writing".
- "Itchy paws at night": "… about 5 s" / "A · In production · Maya".
- "Crusty eyes pitbull": "Reed · 5 min ago · about 11 s · 1 version left to make" / chips "✓ A · Video done", "B · In production · Sam", "C · Ready to make".

Problems:
- **Nothing on a card says "draft" or "published".** A draft and a published script look the same, apart from what their chips say. "Writing" is used both for Reed's unpublished script and for Maya's private draft. The Status filter has no Draft or Published option either (see 04).
- **In-production chips name a person but not the step or the cost.** "B · In production · Sam" doesn't say that it has been at Assets for minutes. In production (23) has that information.
- "1 version left to make" counts only C. Next to three chips, a reader has to work out which one it means.
- "Length set at Breakdown" (an empty script) uses a step name as plain English. "about 4 s" wraps at 390 as "about 4 / s".
- Descriptions are cut short at 390 ("Owner and pitbull mornin…").
- Script titles are 23 px tall links. The whole card can be tapped, so this matters less. At 1440 the "…" menus are 36 px.
- **Amber: 1** ("New script"). There are 4 ways to start something: Bulk create (an icon only at 390), Import a reel, New script, and "New video (the earlier way)".
- At 1440 the Sort box cuts off its own value: "Recently changec".
- The page heading is "Scripts", the tab is "Scripts", and the side menu says "Scripts": three "Scripts" within 100 px.

### P6-03-390-library-editor.jpg / P6-03-1440-library-editor.jpg
Maya sees three groups: "Making now" ("Itchy paws at night", "A · In production · you"), "Your drafts" ("Maya's park idea"), then **"1 script"** and the "Crusty eyes pitbull" card.
- **The count "1 script" sits below two other cards**, so it reads as if the page has only one script while three are shown.
- **Maya's finished video is not marked as hers.** "A · Video done" on Crusty eyes doesn't say "you", although her video in production does ("In production · you").
- At 390 the version chips are 44 px tall boxes with big gaps (three chips take about 160 px of height) for what are really labels.
- Amber: 1 ("+ New script", in the fixed bar next to "Import a reel").

### P6-04-390-library-filters-open-owner.jpg / P6-04-390-library-filters-open-editor.jpg (390 only; at 1440 the filters are always shown, see P6-03-1440)
A sheet titled "Filters" with Status, Length, Reference, Versions left, "Mine", "Deleted and archived", Brand (owner only), and Sort.
- **There is no "Done", "Apply" or "Show N scripts" button.** Only the ✕ closes the sheet.
- **The Reference list holds 12 reel stories from other kinds of brand**, such as "A groom is dumped at the altar for a richer man" and "Nate blows his mom's money on AirPods to resell". They appear on Iron Paws and every other brand. They come from the server's built-in examples (`server/app/prompts/examples/`), not from the stand-ins.
- The Status options are "Writing, Ready to make, In production, Video done". There is no Draft or Published option.
- "Mine" and "Deleted and archived" are pill buttons placed on one line out of line with the select boxes. They switch to filled amber when on (see 05).

### P6-05-390-library-deleted-owner.jpg / P6-05-1440-library-deleted-owner.jpg / P6-05-390-library-deleted-editor.jpg
Owner: "1 script". The card reads "Bath time chaos" / "Deleted · 4 min ago" / "Removed for good on 28 Nov" / "Dog runs from the bath. Old idea." / "Reed · 4 min ago · about 4 s" / "A · Writing" / "Restore".
- **Amber buttons: 2.** At 390 they are "Filters (1)" and "New script". At 1440 they are "Deleted and archived" (the toggle when on) and "New script". A toggle that is on looks the same as the main action.
- The heading stays "Scripts". Nothing at the top says you are looking at deleted scripts, apart from the filter state.
- "Deleted · 4 min ago" and "Reed · 4 min ago" are two times on one card with no label for which is which.
- At 1440 "Restore" is 36 px.
- Editor (390): "Nothing deleted or archived." with "Show all scripts". That is fine, but Maya can only ever see her own unpublished deleted scripts, and the page doesn't say so.

### P6-06-390-library-empty-brand-owner.jpg / P6-06-1440-library-empty-brand-owner.jpg / P6-06-390-library-empty-brand-editor.jpg
- Owner: "No scripts for Night Owl Coffee yet." / "Write a script once and make up to three videos from it." There is no button inside the empty state. "New script" is in the top bar (or the fixed bar at 390), along with "Import a reel" and "New video (the earlier way)".
- Editor: "No scripts ready to make yet." / "The owner publishes scripts here. You can also write your own." This is clear.
- "Make up to three videos" is the only place that says a script can have three versions, and it doesn't say why three.

## 3. Videos view (Scripts | Videos)

### P6-08-390-videos-view-owner.jpg / P6-08-1440-videos-view-owner.jpg / P6-08-390-videos-view-editor.jpg
"3 videos" (owner) or "2 videos" (Maya). The rows are:
- "Crusty eyes pitbull" / "Maya · Video done · Oct 29" / "✓ Video done" (still thumbnail)
- "Crusty eyes pitbull — Local variation 1" / "Sam · At Assets" / "In production"
- "Itchy paws at night" / "Maya · At Assets" / "In production"

Problems:
- **The page heading still says "Scripts"** while "Videos" is selected.
- **"Video done" appears twice on one row** (in the subtitle and as a badge).
- **The same video has three names.** Here it is "Crusty eyes pitbull — Local variation 1" (the variation title, from the stand-in). In production and Usage call it "Crusty eyes pitbull · B". The library chip calls it "B". Version A is called just "Crusty eyes pitbull" here, with no letter.
- The rows show no cost and no time since the last change. In production shows both.
- The 390 search placeholder reads "Search videos", but In production's says "Search scripts" (see 23).

### P6-09-390-videos-empty-owner.jpg / P6-09-1440-videos-empty-owner.jpg
"0 videos" / "No videos yet." / "Videos made from your scripts show up here." / "Show scripts".
- **Amber: 0.** The only action goes back to scripts, which is acceptable.
- "0 videos" is said above "No videos yet.", which repeats it.
- "your scripts" is wrong for the owner when editors make the videos.

## 4. Quick clip

### P6-10-390-quick-clip-owner.jpg / P6-10-1440-quick-clip-owner.jpg
Composer:
- "Model: Seedance 2.5 · 4–30s · up to 720p"
- "What happens" (0 / 2,000) with the hint "Who's in it, what happens, how the camera moves."
- "Improve prompt", "Brand pieces 0 of 30 / + Add"
- Shape: 9:16 1:1 16:9 4:3 3:4 21:9 adaptive
- Length (8 s, slider from 4 s to 30 s), Quality (480p / 720p)
- The fixed button "Generate · 8 credits", greyed with "Describe the clip (8 or more characters)"

The header reads "This week: 27 of 145 credits". History has search ("Search your clips"), a "Show" select (All / Ready / Making / Didn't finish / Removed / Cancelled) and 6 rows:
- "Cancelled" / "A pitbull chases a ball across the dog park, wide shot." / "5 s · 9:16 · 480p · 5 credits" / "…"
- "Didn't finish · credits returned" / "The dog from this photo jumps into a bathtub full of bubbles." / "5 s · 9:16 · 480p · 5 credits" / "The service couldn't finish this. Nothing was charged; try again." / "Try again · 5 credits"
- 4 × "Ready" / prompt / "5 s · 9:16 · 480p · 5 credits" / "Download"

Problems:
- **History is not per person or per brand.** On Iron Paws, Reed's History includes the fomo clip ("A young man looks at a stock chart…") and Maya's clips. Rows don't say who made them or for which brand. The server's `GET /jobs` returns every Quick clip in the studio (`routes/jobs.py`, `list_jobs`), while the search box says "Search your clips".
- **The failed row uses three ways to say one thing:** "Didn't finish · credits returned", "Nothing was charged", and the price "5 credits" still shown on the row.
- **The cancelled row has no explanation and no action.** It doesn't say who cancelled it or whether credits came back, although the failed row does.
- No row has a date or time.
- **Amber: 0** on the whole page before typing. "Generate" stays grey until there are 8 characters.
- **"Improve prompt" is greyed with no reason**, and its price is not shown.
- The owner sees "This week: 27 of 145 credits". Team calls 145 the "Editors' weekly allowance", so it is unclear whether the owner has a limit at all.
- At 1440: the "Show" select, the "…" menus and "Try again · 5 credits" are 36 px.
- "adaptive" is lower-case jargon next to ratios.

### P6-10-390-quick-clip-editor.jpg / P6-10-1440-quick-clip-editor.jpg
This is the same as the owner's page, including Reed's failed clip with **"Try again · 5 credits" offered to Maya** for a clip she didn't make. "This week: 5 of 145 credits".

### P6-11-390-quick-clip-empty-brand-owner.jpg / P6-11-1440-quick-clip-empty-brand-owner.jpg
On Night Owl Coffee, a brand with no clips, **History shows the same 6 rows from Iron Paws and fomo.** The empty brand never shows an empty state.

### P6-12-390-quick-clip-empty-history-editor.jpg / P6-12-1440-quick-clip-empty-history-editor.jpg
Sam has never made a clip. His header reads "This week: 0 of 145 credits", but **his History still lists everyone's 6 clips**, again with "Try again · 5 credits" on Reed's failed one. The History empty state ("nothing yet") cannot be reached while anyone in the studio has made a clip.

### P6-33-390-quick-clip-past-allowance-editor.jpg / P6-33-1440-quick-clip-past-allowance-editor.jpg
After the allowance was lowered to 5 (see 32), Maya typed a prompt. The header reads "This week: 5 of 5 credits". "Generate · 8 credits" is greyed with "You've used this week's 5 credits. It resets on Monday."
- The reason is clear. There is still no amber, and no way to ask the owner for more.
- "Improve prompt" is still enabled with no price. It is unclear whether it uses the allowance.
- The header is small grey text at the top right, far from the button.

## 5. Cast & places

### P6-13-390-cast-characters-owner.jpg / P6-13-1440-cast-characters-owner.jpg / P6-13-390-cast-characters-editor.jpg
The page heading is **"Library"**, with tabs Characters / Places / Props, Search, a "Show archived" checkbox, and "New character" (amber). The cards are:
- "Bruno": grey sheet / "v4"
- "Dana": "No image" / "v1" / "Needs a sheet"

Problems:
- **One section, three names.** The side menu says "Cast & places", the phone tab says "Cast", and the page heading says "Library". There is also a "Props" tab that neither name mentions.
- "v4" / "v1" are version numbers with no meaning for Reed. Bruno shows "v4", while his History lists v3, v2 and v1 (see 15).
- Each card's brand is only a dot. Its name ("Iron Paws") is in the page text but not visible.
- The "Show archived" checkbox is 13 px.
- Amber: 1. The editor's page is the same, including "New character".

### P6-14-390-cast-places-owner.jpg / P6-14-1440-cast-places-owner.jpg
"Dog park": "No image" / "v1" / "Needs a sheet". "Sunny kitchen": grey sheet / "v2" / **"Needs a sheet"**.
- **"Sunny kitchen" has a sheet waiting for approval, but its badge says "Needs a sheet"**, which is the same as the place with no sheet at all. The real state is that the sheet needs approval.

### P6-15-390-cast-item-owner.jpg / P6-15-1440-cast-item-owner.jpg / P6-15-390-cast-item-editor.jpg
"← Characters" / "Bruno". The "House-style sheet" card contains "No photo yet", "Source photo, not used in videos", "Upload a photo", the sheet image, "✓ Approved sheet", "Undo approval", and "Redo · up to 4 credits". Below that are the fields Name, Brands (checkboxes fomo / Iron Paws / Night Owl Coffee), Notes, Outfits ("Add outfit"), Voice sample ("Add voice"), and "Save" (greyed). Then History, with "v3 · Oct 29 by Reed / Restore" three times, and "Archive character".
- **"Save" is greyed with no reason.** On the brand page and in Team, the same kind of button says "No changes yet".
- **Amber: 0.**
- "House-style sheet", "Source photo, not used in videos" and "Redo · up to 4 credits" are internal ideas. A "photo" box sits inside the "sheet" card, which mixes two things.
- **History rows only say "v3 · Oct 29 by Reed".** They don't say what changed (here, "Big ears." was added to the notes). Every row has the same "Restore" link, which is 18 px tall at 1440.
- At 390 the "← Characters" link is 23 px, and the Brands checkboxes are 13 px.
- The editor sees the same page with Save, Archive and Restore available.

### P6-16-390-cast-archived-owner.jpg / P6-16-1440-cast-archived-owner.jpg
With "Show archived" ticked: "Old mascot" / "No image" / "v1" / "Archived" / "Unarchive" / "Delete forever".
- **"Unarchive" and "Delete forever" are 18 px text links** with no visual difference. A permanent delete sits next to a harmless one at the same weight.
- "New character" disappears in this view, which is fine, but nothing says "You are looking at archived items".

### P6-17-390-cast-empty-brand-owner.jpg / P6-17-1440-cast-empty-brand-owner.jpg
"No characters for this brand yet." / "Add a character once, use them in every video." "New character" (amber) is above it. This is clear, and it is the one empty state in this part that sits right below its action.

## 6. Brand page

### P6-18-390-brand-look-owner.jpg / P6-18-1440-brand-look-owner.jpg / P6-18-390-brand-look-editor.jpg
Tabs "Look", "Products 1", "App screens 2". The Look card has Name, Logo (Upload), Colours (+ Add) with "The first colour tints the brand's dot.", Fonts (e.g. Manrope, + Add) and Style board (Upload). The Voice card has "How we sound", "Never say" (A word or phrase, + Add), "Legal line" and "End line". "Save changes" is greyed with "No changes yet".
- **The End line hint quotes another brand on Iron Paws:** "Example: "Want to trade like me? Download fomo through the link in my bio."" It says the same on Night Owl Coffee.
- **Amber: 0.** The two "Add" buttons (Fonts, Never say) are greyed with no reason. They need text typed first.
- Iron Paws has no logo, colours, voice or end line. Nothing tells Reed that videos will be made without them.
- **The editor sees the same editable page with "Save changes".** The server's `PATCH /brands/{id}` has no owner check, so Maya can change a brand's look and voice. The brand switcher tells her "Brands are set up by the owner."
- At 1440 the "…" menu next to the heading has no label.

### P6-19-390-brand-products-owner.jpg / P6-19-1440-brand-products-owner.jpg
"bag · 2 flavours" with "Chicken", "Peanut butter", "Add flavour", and "Add product" (amber).
- "bag · 2 flavours" is lower-case, and a product "name" of "bag" reads like a type. The product has no proper name such as "Iron Paws greens".

### P6-20-390-brand-screens-owner.jpg / P6-20-1440-brand-screens-owner.jpg
"App screens · 2", a "Tag" filter (All tags, bag, peanut-butter, product, end card), and two cards: "Chicken bag" ("end card +3") and "Peanut butter bag" ("end card +3"). "Add screens" is amber.
- **"App screens" on a dog-food brand holds bag photos.** The tab name only fits fomo.
- The tags are raw slugs ("peanut-butter").

### P6-21-390-brand-empty-owner.jpg / P6-21-1440-brand-empty-owner.jpg
Night Owl Coffee: the same empty Look form, and tabs "Products 0" and "App screens 0". **There is no empty state or first step.** The New brand dialog promised "You add its logo, colours and screens next", but this page doesn't say where to start, and there is no amber button. The fomo End line example is shown here too.

## 7. Studio pages (owner)

### P6-22-390-approvals-empty-owner.jpg / P6-22-1440-approvals-empty-owner.jpg
"Nothing waiting." / "Editors are never sent here any more: past a budget or their week, their button gives the reason. Requests from before 26 Oct show here until they're handled."
- **The page explains its own history.** "any more" and "before 26 Oct" mean nothing to a new owner.
- The page stays in the menu, and in the top bar as a bell or "Approvals", although nothing can reach it (see the server note at the top).

### P6-23-390-in-production-owner.jpg / P6-23-1440-in-production-owner.jpg
"3 videos being made". The cards are:
- "First trade nerves · A" / "fomo · Reed" / "Assets · 4 min ago" / "3 of 48.72 credits · $0.00"
- "Itchy paws at night · A" / "Iron Paws · Maya" / "Assets · 4 min ago" / "4.7 of 56.12 credits · $0.00"
- "Crusty eyes pitbull · B" / "Iron Paws · Sam" / "Assets · 4 min ago" / "3 of 67.38 credits · $0.00"

At 1440 there is a table: Video, Brand, Editor, Step, Last activity, Credits.

Problems:
- **Credits and dollars appear together with odd decimals**: "4.7 of 56.12 credits · $0.00". The "of" figure is the video's budget, but nothing says so.
- The search placeholder says "Search scripts" on a list of videos.
- **The "Step" column says "Assets"**, while the Videos view says "At Assets". In fact Sam's video is still on the Breakdown screen with "Next: Assets" ready (it was never opened).
- At 1440 the "Needs attention" toggle and the "…" menus are 36 px.

### P6-24-390-in-production-empty-filtered-owner.jpg / P6-24-1440-in-production-empty-filtered-owner.jpg
With Brand set to Night Owl Coffee: "0 of 3 videos" / "Nothing matches these filters." / "Clear filters". At 390, "Filters (1)" is amber, the only amber on the page, and it is a filter rather than an action. The unfiltered empty state ("Nothing is being made right now.") could not be captured (see the top).

### P6-25-390-usage-owner.jpg / P6-25-1440-usage-owner.jpg
"Usage" / "Week of 26 Oct" / This week, This month, All time. Tiles: "Spent $0.00", "Finished 1 video", "Cost per finished video $0.00", "In progress 3 videos". Then "Brands" (search, Filters), "Nothing was spent this week.", "3 brands", and a card per brand:
- "fomo / $0.00 spent · 0 finished · — / 1 in progress · 1 script · 0 versions left"
- "Iron Paws / $0.00 spent · 1 finished · $0.00 each / 2 in progress · 5 scripts · 1 version left"
- "Night Owl Coffee / …"

Below that is "Every charge" (collapsed).

Problems:
- **Usage is only in dollars**, while In production right next to it shows credits and every button shows credits. Only Team shows how they convert ("≈ $14.91 a week" for 145 credits).
- "Finished 1 video" has a "+1 on last week" note only at 1440.
- "—" for cost per video, with no explanation.
- At 1440 the period tabs are 36 px, the brand-name links 18 px, and the "Show archived" checkbox 16 px.
- The brand dots are grey here but orange in the switcher.

### P6-26-390-usage-brand-videos-owner.jpg / P6-26-1440-usage-brand-videos-owner.jpg
"Iron Paws", the same tiles, then "5 scripts · 1 version left to make · 2 people made videos this week", and tabs "Videos 3" / "Scripts 5". The list is "Videos with activity this week · 3":
- "Itchy paws at night · A / In production / Maya · $0.00 · 4 min"
- "Crusty eyes pitbull · B / In production / Sam · $0.00 · 3 min"
- "Crusty eyes pitbull · A / Video done / Maya · $0.00 · 5 min"

At 1440 the columns are Video, Who, Status, "Spent whole video", Credits ("4.7", "3", "31.33"), and "Finished / last".
- **Dollars and credits sit in neighbouring columns, with credits as decimals ("31.33").**
- "2 people made videos this week", but only Maya finished one. "made" is ambiguous.
- The Status filter offers "Didn't finish" for videos, a term that elsewhere belongs to Quick clips.
- At 1440 the video names are 16 px links.

### P6-27-390-usage-brand-scripts-owner.jpg / P6-27-1440-usage-brand-scripts-owner.jpg
The Scripts tab shows each script with chips and "<author> · $0.00 · <age>". Crusty eyes ends "· 1 left ·".
- "1 left" is a shorter form of the library's "1 version left to make".
- These are the same cards as the library but with $ added. Titles are 23 px links.

### P6-28-390-usage-charges-owner.jpg / P6-28-1440-usage-charges-owner.jpg
"Every charge" opened: a "Brand" select (Any / fomo / Iron Paws / Night Owl Coffee) and **"No charges yet."** This comes from the stand-ins, which record no charges. The same studio shows "Finished 1 video" and 31 credits used on that video, so "No charges yet." contradicts the credit figures elsewhere. With real providers this list would fill. **The Charges list with rows could not be captured for free.**
- The section is a collapsed `<details>` at the very bottom, and easy to miss.

### P6-29-390-team-owner.jpg / P6-29-1440-team-owner.jpg / P6-32-390-team-after-limit-change-owner.jpg
The page is in this order:
1. "Studio name" (Studio, "Shown on invite links.", greyed Save, "No changes yet")
2. "Credit limits":
   - "Editors' weekly allowance" 145 credits, "≈ $14.91 a week. Free generation for each editor's own scripts and quick clips. Resets on Monday."
   - "Most one video can cost" 729 credits, "≈ $74.94. For everyone, the owner too. A video's budget is twice its estimate, up to this."
   - "Save limits" (greyed) with "No changes yet"
3. "People": "Reed reed@example.com Owner", "Maya … Editor …", "Sam … Editor …"
4. "Waiting invites": "jo@example.com / Editor · expires Nov 5 / Copy a new link / Cancel"
5. "Invite someone" (amber, fixed bar at 390)

Problems:
- **The credit limit cannot be set per editor.** One "Editors' weekly allowance" applies to everyone. People rows show no credits used this week, although the server has the figures (`GET /credits/allowances`).
- **"Free generation" next to a credit allowance is contradictory.** It reads as "free", but it is counted.
- **The "Lower the weekly allowance?" warning never appeared** when the limit was lowered to exactly what Maya had used (5). It saved straight away with the toast "Limits saved. Undo" (P6-32). Maya was then blocked (P6-33), so the warning's check misses "used = new limit".
- After the change the help line reads "≈ $0.51 a week". This is the only place where credits are turned into dollars.
- "Most one video can cost" is awkward English. "A video's budget is twice its estimate, up to this" is internal policy.
- The order is odd: Studio name and limits come before People.
- At 1440 "Save", "Copy a new link" and "Cancel" are 36 px. "Cancel" on an invite is a plain text button next to a framed one.

## 8. Sign-in, invite and setup (390)

### P6-34-390-sign-in.jpg
"Brand Studio" / "Sign in" / Email / Password / "Sign in" (amber) / "Forgot your password? Ask the owner." / "Made for your team's studio." This is clear. The footer line adds nothing.

### P6-35-390-invite.jpg
"Join Studio" / "Reed invited you to Studio as an editor. Your email is jo@example.com." / "Your name" / "Choose a password (10 or more characters)" / "0 / 10" / "Create my account" (amber).
- "Studio" is the default studio name, so the heading reads "Join Studio". It would read better if Reed had named the studio. Nothing prompts him to (see Team).
- "0 / 10" is a counter under a password field.
- "editor" is not explained (what an editor can and can't do).

### P6-36-390-invite-bad-link.jpg
"This invite link is not valid any more." It gives no next step, such as "Ask Reed for a new link".

### P6-37-390-setup.jpg
**The setup page still shows the full "Set up the studio" form after the studio is set up**: "Setup code (from your server settings)", Studio name, Your name, Email, Password, and "Create owner account". The only hint is "Already set up? Sign in" at the bottom. "Setup code (from your server settings)" is server language.

---

## Also seen (the chip taps were not kept as shots; the version panel was)

- **Tapping the "A · Video done" chip as the owner opens the finished video at "Step 1 of 5 · Breakdown"**, with "Redo · 3 credits" (URL `/b/2/videos/1`). It does not open the finished cut or Downloads. Tapping "B · In production · Sam" also opens Breakdown, not the step Sam is on. These are video-step screens, so they are out of scope here.
- **Version panel** (P6-30-390-version-panel-ready-editor.jpg / P6-30-1440-version-panel-ready-editor.jpg): "Crusty eyes pitbull · Version C" / "Variation of A" / the script / "Characters: Pitbull · Look made at Assets" / "Breakdown: Planned automatically when you start" / **"About 23 credits to make"** next to the button **"Make this version · 3 credits"**. These are still two different prices next to each other, as in part 1, and the internal wording "made at Assets" is still there.
