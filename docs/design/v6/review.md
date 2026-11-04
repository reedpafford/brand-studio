# Review of the v6 boards

Two independent passes ran over all 77 boards:
- an outside design review (the impeccable-finish-reviewer agent), which saw only the boards, the brief and the rules;
- the impeccable detector on the board HTML.

Below: what they found, what was fixed, and what's still open for Reed.

## What the outside review found, and what changed

| # | Found | Fixed |
|---|---|---|
| 1 | The same video had different facts on different boards. For example, "Bloated after pizza" appeared as a UGC video, a husband-and-wife skit, and a 28 s delivered cut, in two different folders. | One fact sheet per video. Bloated after pizza is a UGC presenter video: 6 clips, up to $7.40, in Week of 3 Nov. The skit is now its own idea, "Caught with the pizza boxes". Movie boards (S3-13, S4-04, S6-04) are labelled "when Movie is on". |
| 2 | The beer-gut video's scenes showed up on other videos. | Each video draws its own scenes and clip count: UGC 6, Skeleton 18, the skit 14. |
| 3 | Budget sums didn't add up ($16.30 + $2.00 ≠ $18.40; the credit figures were off). | Redos are now "up to $2.10". Credits come from dollars with one rule: spent 159 credits (97%), up to 179, so 15 past a 164 budget, with redos up to 20. |
| 4 | An editor could see a dollar amount, "Waiting for your OK", and "free" where it wasn't free. | The editor sees credits and "Waiting for the owner"; sound effects read "under 1 credit". |
| 5 | The dot in the tree didn't match the header (Working vs Delivered or Stopped). | The open video's dot follows its header on every board. |
| 6 | Some prices before a charge lacked "up to". | Every money price on a button now reads "up to" (rule 36). |
| 7 | Counts drifted: folder sizes, Needs you (3 vs 4), how many videos Mark is in, the Movie's progress. | One set of numbers: Week of 3 Nov 10, Dr. Pickle rants 124, Needs you 4, Mark in 6 videos, Dana in 2, the Movie at 47 of 118. Clip 44 is "Dana leans in". The Skeleton send is under Resilia. Presenters & voices shows 7. |
| 8 | Two states looked like other states: "off" in S2-03, and "building" in S7-04. | S2-03 shows UGC tagged "Off on this site" with the reason; S7-04 greys out the timeline until the first cut exists. |
| 9 | Broken bits: checkboxes covered labels (S1-07), sound-effect chips were cut off, a delivered video still showed Stop (S6-01), and a retry button was crowded (S6-05). | All fixed. |
| 10 | Grey boxes where pictures matter: the "same person?" check, the plan, the "making" row, the app screens. | Real faces on "same person?"; the plan lists each shot in words; the "making" row shows its still with a progress bar; the app screens say "3 of 10 shown". |
| 11 | Phone: filmstrip frames too small to tap; New video missing the other ways in and the folder; library tabs and the Script tab missing. | Phones show one frame per scene with its count. P-03 has Paste / Saved script / Use a reel and the folder. P-13 has every tab; P-09 has Script. |
| 12 | Some screens had two indigo buttons, and Needs you had none. | One indigo press per screen. In Needs you, it's the owner's money approval. |
| 13 | Status words and jargon: "Done" vs "Delivered", "92 Hz", "−18 dB", "used 1 of 3", "bottle". | "Delivered" everywhere, and "Working · revising" style sub-states. Jargon replaced ("Quieter by: a lot (−18 dB)", "1 of 3 videos made", "capsule"). |

## What the detector found

| Finding | Done |
|---|---|
| Low-contrast grey text: counts, times, placeholders | Raised to the readable grey; placeholders now 4.9:1 |
| White on the Resilia and Iron Paws brand marks | Darkened both colours to pass 4.5:1 |
| 9 px "test sample" tags | 11 px; shown only on pictures 120 px or wider. Every board's label strip says the pictures are paid test samples unless marked as site output. |
| "Cramped padding" on media, chips, rail rows and tabs | Not a problem: these are fixed-height controls with centred content, as in the app today |
| "Overused font: Inter" | Kept: Inter only is rule 33 |

## Kept, because both passes liked it

- One live progress card made of real frames that opens to every step.
- The delivery note: what I made, what I watched and redid with timecodes, what I'm unsure of, what I need from you.
- "Changed after watching" outlines.
- Ask cards: saved items first, price on Generate, "made for this video, not saved".
- The pinned "questions waiting" bar.
- Editor holds that say "the owner", with Withdraw.
- The locked-line alternatives and the one-press split.
- The cut editor's words under the player, with the director's edits marked and Undo on each.

## Reed's answers (3 Nov)

1. **The director redoing on its own:** the brief wins. Rule 11 needs updating or removing; that's for the Producer (see `build-plan.md`).
2. **The upload box:** dropped for now. S4-03 no longer has it. Uploads are used for that video; people are added to a brand in Cast & places.
3. **No Approve all:** agreed.
4. **The changes from v5:** approved ("these are awesome").
5. **A story choice:** after a while, the director picks its suggestion, as S4-02 shows.

Still to know: there are 15 phone boards, because the other states reuse the desktop layouts. The 57-board v5 canvas wasn't reachable for comparison.

## Gaps the builders found (3 Nov), approved

Reed said "yes to all" to the five options on [S-gaps-01](boards/S-gaps-01.jpg):
- the B-roll look picker;
- "Just its look" for a reel;
- the upload button (for this video only);
- the status words ("Needs you" with a reason; "Needs a fix" when a run stops on its own; "Stopped" only when a person stops it);
- sorting by Newest, Oldest or Name A–Z.

## Gaps the builders found, part 2 (3 Nov), approved

Reed said "yes to all" to [S-gaps-02](boards/S-gaps-02.jpg):
- the folder's ⋯ menu, with "Archived ideas · N" (hidden at 0);
- card checkboxes on hover, and on every card once one is ticked;
- Unsorted opens on desktop, and the folder list on a phone;
- the set-up list only while a brand is empty;
- P-02's phone tabs fixed to All · Needs you · Working · Delivered.

## Gaps the builders found, parts 3 to 8 (4 Nov), approved

Reed said "yes to all" to [S-gaps-03](boards/S-gaps-03.jpg) and [S-gaps-04](boards/S-gaps-04.jpg):
- the Locks menu, the video's ⋯ menu, and the phone Preview's tab row always showing;
- Scripts first under Library in the rail, the quick search, the phone's Library and More tabs, and an editor's My requests.

[S-gaps-05](boards/S-gaps-05.jpg), the library and video settings, drawn to his answers:
- the Brand kit is short (name, logo, colours, tone and rules), and products can be apps (their screens) or physical things (their photos);
- Import from website is dropped everywhere;
- a saved presenter is a face and a voice, and each video picks how they appear (talks to camera, in a corner over the B-roll, or acts in the story);
- every app voice is listed with a free sample, and a brand's own voices are only the ones uploaded or cloned on purpose;
- each video's settings sit at the top of the Plan tab, with the new price and Undo;
- a person approves a library sheet before videos use it.

[S-gaps-06](boards/S-gaps-06.jpg), the open folder, approved with these details:
- the list view's Status column is 230 px, so the reason fits;
- the Move menu opens upward from the Move to… button, left-aligned to it, and stays inside the window;
- phones can select several ideas, with a count and a way out;
- an empty Unsorted reads "Nothing in Unsorted · New ideas land here until you put them in a folder." with New video;
- a phone folder has a ⋯ beside search, so Archived ideas and the folder's menu are reachable.

[S-gaps-07](boards/S-gaps-07.jpg), the Cast tab:
- **Places: yes, extended.** Characters and places sit together in the video's Cast. Each is picked from the library, uploaded, or made for this video only, and labelled with where it came from. Looks the director makes in the chat land in the same list. Items made for a video never go into the brand's library by themselves. Places are settings; Plan decides scenes and action.
- **Approving looks: neither a per-card OK nor no OK.** Instead there is one combined "Approve cast & places":
  - the full set is shown with previews, made within the budget already approved;
  - the person requests changes and checks the revised previews, then presses once;
  - storyboards and clips that use the set wait, and the app enforces that pause;
  - a later change needs the combined OK again, while unchanged items stay approved and unrelated work carries on;
  - clips already made are kept, with the ones needing an update and their price shown first;
  - the person making the video approves, with no extra owner OK for an editor on a published library script;
  - library sheets keep their own approval.
- S5-03's line is now: "The director prepares the characters and places. Review them together, request any changes, then approve the cast and places to continue."

[S-gaps-08](boards/S-gaps-08.jpg), the Clips tab:
- 12 clips or fewer show as a grid, and more than 12 as the list grouped by scene. On a phone the grid is two columns with a clear way back.
- Earlier stills stay reachable, with no per-still approval list, and the Cast & places check still applies. Each press says whether it needs a new take, with the real "up to" price (credits for editors), and a suitable existing take is reused. A change that would alter an approved character or place goes back to Cast.
- "Use this take · free" rebuilds the cut automatically, and the previous cut stays playable until the new one is ready. Any paid review follows the budget and approval rules.
