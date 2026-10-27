# QA-Live 6 phase 2: a full editor run on the live site (2026-10-27)

As **QA Editor** (an editor account Reed approved), from Reed's reel DeiD2HlPrBt to a finished 62 s video: script 29 → video #16.
Reed approved the paid run (cap $15) in this session and steered the cast during it: Lexi = **Goth GF**, the helper (trader friend) = **Kimchi**, both from Cast & places, and the other looks redrawn in Goth GF's style. He didn't like the first, childlike sheets.
**Spent:** 94 credits charged, $11.35 provider cost. The breakdown is in `ops/SPEND.md`.

## Files
- `cast_now.jpg`: the cast after the redraw (Goth GF, poor guy, boss, Kimchi came later, customer). `looks_redraw1.jpg`, `looks_redraw2.jpg`: first and second redraws.
- `storyboard_stills.jpg`, `stills_kimchi.jpg`: the six stills, then the three redrawn after the swap to Kimchi.
- `p16_c1.jpg` … `p16_c6.jpg`: 2–3 frames per shot from each picked take, labelled with the shot and second.
- Screenshots: `27_video_page`, `29_problems`, `33_assets_making`, `35_problems_back`, `49_clips_failed`, `55_downloads`.

## What worked
- Reel import: the link was downloaded free and read for 1 credit against "about 7" quoted (2 failed watch tries were retried by themselves).
- Cast read: 5 roles, each with age, gender and job (guesses marked), no duplicates, Lexi and "the waitress" kept as one role.
- Assets made the 5 missing looks by themselves after a 3 s countdown, "up to 17 credits (usually 9)". Approve all worked.
- Every clip puts the hero's sheet first. Every "Use the real image" switch starts off. App screens are on the phone in hand in prompts, stills and takes. The CTA ends on the phone held to camera with the fomo logo. Numbers never blocked.
- All 6 takes succeeded first time (no copyright refusals), and the final video was made free.

## Findings
1. **Kept problems are wiped by every cast change.** Making the looks, swapping Lexi to Goth GF and swapping the helper to Kimchi each saved a new breakdown version (77 → 82 → 83 → 84). Each one cleared every "Keep anyway" and sent the editor back to Breakdown with 7 blocking problems and Next: Assets disabled. I kept the same 7 four times.
2. **The "Check the cast" lines are false alarms on reaction shots.** For example, shot 1.11 "Lexi takes the hit" is flagged because its script line (9) is the boss's "You're fired!". All 7 were like this. The free one-click fix "Put the right cast in each shot" would put the speaker into each reaction shot, which is wrong. The wording "the shot shows no look yet (Lexi…)" is also confusing before Assets.
3. **The price shown before starting is far too low.** The version panel said "About 32 credits to make" and the scripts list "about 32 s". The 62 s plan cost 94 credits (62 for takes alone). See #419: the price must be shown first.
4. **Rule 4:** the editor saw "Draft · only you and Reed can see it", and the login page says "Forgot your password? Ask Reed." (fixed by #631 during the run).
5. Reference titles were cut after "$" ("Mom finds her son's $2"), fixed by #632 during the run.
6. **The first auto looks were childlike** (big heads, small bodies), and the boss had only front and back views. #630 landed during the run. A redraw with a note on a video's own look attaches its last sheet, so it barely changes. The boss and customer needed a second, stronger note, and the boss still uses two rows. There's no way to redraw a look in another sheet's style.
7. **"Make all stills" depends on the page staying open.** It asks for the stills one by one, so leaving the page stopped it after 2. "Redraw 3 stills" works server-side, but the page then asks again and gets 3 × 409.
8. Storyboard chips show "● Character" for unlocked roles instead of their names.
9. **Server restarts kill running work.** Clip prompts 471 died at the 19:53 deploy and 472 at about 19:57 (no deploy at that time). "The server restarted or lost contact… Nothing was charged; try again." The third try (476) took 5 min for 66 shots and cost the provider $1.02 against a 3-credit ($0.31) charge.
10. Clips has no "Looks good" for all (6 single presses), and the pressed button keeps its label. The prompt on screen reads "References: First frame is the first frame." Clip 6's References line lists the tags out of order (the mapping is right).
11. **After the swap to Kimchi, his outfit came from the old role text** (backwards cap, white tee, gold chain) rather than his sheet's white shirt. Rule 10 says the sheet sets the outfit. His face held.
12. **The hero is missing from some montage shots** (frame c3, shots 5.1–5.2 are the trader friend's hands), against rule 17.
13. **Faces in the takes:** clips 1, 3, 4, 5 and 6 hold to the sheets. Clip 2 (20 s, 19 shots, the longest) drifts. Lexi turns softer and younger in the rain at 0.8–1.5 s (2.1), 5.1–5.4 s (2.4) and 9.6–12.3 s (2.8–2.11), and Kimchi's face widens at 17.8–18.4 s (4.2). Long clips are still where faces drift.
