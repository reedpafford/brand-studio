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

## Still open for Reed

1. **The director redoing things on its own (rule 11).** Rule 11 says automatic checks never redo anything on their own. Your 3 Nov director brief says the director watches every take and redoes what's weak within the budget. The boards follow the brief because it's newer. OK?
2. **Adding an upload to the brand (rule 12).** When you upload a person in an ask card, there's one unticked box: "Also add him to Resilia's Cast & places" (S4-03). Generated looks never get it. Keep the box, or drop it for now?
3. **Approve all (rule 21).** v6 has no per-item approval list: the director approves clean work itself, and only flags come to you. So "Approve all" appears nowhere. The "Check prompts before takes" setting would sit in the Locks menu; it isn't drawn. OK?
4. **What changes from v5 (rule 33).** Free folders in the rail replace "Project ▾". The video page becomes chat plus a preview panel instead of the tab row. New video replaces the Freestyle form. Scripts, Media, Usage, Team and Settings stay as v5.
5. **A story choice with a default.** S4-02 says "I'll go with A at 11:00 if I don't hear back". Should the director pick on its own after a while, or wait as long as it takes?
6. **Phone boards.** There are 15, not about 25. The other states use the same layouts as desktop: same card, narrower.
7. **Not reviewed against the 57-board v5 canvas.** It's in the UX-Auditor's session, which I couldn't reach.
