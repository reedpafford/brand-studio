# Writing step 1: Description, plus New script and Bulk create

This replaces `phase3/screens/new-video.md`. Plan: `../workflow-v2.md`, decisions f, g, j and l.

## The writing frame (all 7 steps)
The video frame from #179 is reused.
- **Header:**
  - ‹ Scripts
  - the title, with `Pencil` to rename
  - a status badge: "Draft · only you can see it", or "Published · final" with `Lock`
- **Step picker:** Description · Script · Directions · Variations · Characters · Breakdown · Publish.
  - Directions, Variations and Breakdown are optional. When skipped, they show a muted "Skipped" instead of a tick, and they don't block Next.
- **Credits:**
  - **Reed:** no meter until Breakdown, which sets the budget (decision h). Before that, the header shows nothing about money.
  - **An editor:** "This week: 32 of 145 credits" (meta) in the header, on every step.
- **Back and Next:**
  - Desktop: **Back** (ghost, `ChevronLeft`) on the left and **Next: {step}** (amber) on the right of the step bar.
  - Phone: Back is a 44px icon button to the left of Next in the action bar.
  - Step 1 has no Back.
- **Script panel:** the Script button (side panel or sheet) shows from Variations on.

## New script (`/b/:brandId/scripts/new`)
This is step 1 before the script exists. The fields are those of the Description step. **Create script** (amber) creates the draft and moves on to Script. Toast: "Draft saved. Next: the script."

## Description (`?step=description`)
One column, max 680px.
1. **Title** (input). Placeholder: "e.g. Bo tries salmon".
2. **What it's for** (textarea, 4 rows, counter "0 / 2,000"). Helper: "A few lines is enough. Claude writes the script from this."
3. **Reference reel (optional):** the compact list from new-video.md.
   - Each row has a 16:9 thumbnail (96px), the name, the logline (2 lines) and the length.
   - Picking a row opens **What to change** (textarea): "For example: the altar becomes a car showroom. Claude keeps the rest of the reel's story."
   - Tap the row again to clear it.
   - A search field sits above the list once there are more than 6 reels.
4. **Notes (optional)** (textarea, 3 rows). Helper: "Anything Claude should know: tone, a line to keep, what to avoid."
5. **Brand:** shown, not editable ("For Iron Paws"). Scripts belong to the brand they're made in.

What's gone, compared with New video:
- **Planned length:** the breakdown sets it (decision h).
- **Who's in it:** characters come from the script, and are locked in step 5.
- **Flavour picker:** a script names its product. Flavours are chosen at Assets, from the brand's Products.
- **Platform and shape:** they move to the video (Breakdown step), because one script can become several videos.

The amber button is **Create script**, or **Next: Script** once the draft exists. When it's disabled: "Add a title first" or "Say what it's for first".

**Done state:** after saving, the step shows a read view, with each field as label and value, plus **Edit description** (secondary, `Pencil`). Once the script is published, the read view stays and there's no Edit (decision i).

## Bulk create (a sheet on phone, a dialog 640px wide on desktop)
This is for making many drafts at once. **Nothing is written** until you press Write all (decision g).

**Step 1, Add scripts:** a list of rows, starting with 3 empty rows.
- Each row has:
  - **Title** (input)
  - **What it's for** (textarea, 2 rows)
  - **Reference** (select: None, or a reel by name)
  - a remove button (`X`, `aria-label="Remove row 2"`)
- **＋ Add a row** (ghost). Up to 20 rows.
- **Paste a list** (ghost, `ClipboardPaste`) opens a textarea: "One script per line: Title — what it's for". Each line becomes a row, and an empty title takes the first 6 words.
- The amber button is **Make {n} drafts**. When it's disabled: "Give every row a title and what it's for (2 rows need it)". The rows that need it are outlined in `danger`.

**Step 2, Drafts made:**
- A list of the new drafts, each with the chip "Writing".
- Then a summary card: "{n} drafts. Claude can write all their scripts now."
- The estimate: "About {N} credits ({n} scripts × {k})".
- **For Reed:** the amber button is **Write all scripts · N credits**, and the secondary button is **Not now** (the drafts stay in the library as "Writing").
- **For an editor** (weekly allowance):
  - the button reads the same when the total fits
  - otherwise it's disabled with "That's more than this week's 145 free credits (32 used). Write fewer, or write them one by one."
  - there's no Ask Reed (decision l)
- After **Write all**, the dialog closes and the library shows each row "Writing…" with a count-up. Toast: "Writing 6 scripts. They'll show as drafts when they're ready."

**Errors:**
- If a row fails: that draft's chip becomes "Didn't finish · credits returned", with **Try again** in its version panel.
- If the call fails: a danger banner in the dialog, "The drafts weren't made. Nothing was charged." with **Try again**. The rows keep their text.

## States (Description)
| State | What shows |
|---|---|
| Loading | Field skeletons, and 4 row skeletons for the reels |
| No reels | The reference block is hidden |
| Error on save | Danger banner above the button, using the server's words. The fields keep their values. |
| Success | Toast "Draft saved. Next: the script." The picker ticks Description. |

## Data the screens need (server)
- `POST /scripts` takes `brand_id`, `title`, `description`, `reference_id?`, `reference_change?` and `notes?`, and returns the draft.
- `PATCH /scripts/{id}` makes the same fields editable until the script is published.
- `POST /scripts/bulk` takes a list of the same fields and returns the drafts.
- `POST /scripts/bulk/write` takes script ids and returns jobs. It goes through the estimate first. For editors it's refused past the allowance, with a reason.
