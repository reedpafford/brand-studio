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

## Language of the takes (asked by the Producer; free, transcribed locally with Whisper "small")
- **#15 "Mom gave him three days…", clip c1:** take 1 (id 64, file 315, 19:18 UTC) speaks **English** (p 0.98), word for word.
  Take 2 (id 66, file 322, 19:23 UTC, made by "Change this…", note "She says '3 days' twice. Also have it open with her slamming the door open.", rewrite job 440, take job 441) speaks **Mandarin Chinese** (p 1.00). It's a line-by-line translation of the script: "内恩 我的钱都哪去了" = "Nate, where did all my money go?", "三天" = "Three days", ending "妈妈" = "Mom".
- Both prompts are in English and name no language (`p15_c1_take1_prompt.txt`, `p15_c1_take2_prompt.txt`). The only differences are the door slam in shot 1 and the audio line. So the language switch came from the video model, not the text.
- Every other take checked is English: all 6 of video #16 and #15's c2–c6 (files 311–314, 316).

## Takes refused as a copyright risk (for the Director)
- **23 refusals across 5 clips:** #13 c1 ×7, #14 c1 ×7, #12 c2 ×5 (still has no take), #9 c2 ×2, #11 c2 ×2. Jobs 108, 113, 246, 281–282, 310, 312–313, 318, 321, 330, 337, 369, 371–373, 384, 388, 394–397, 399.
- **The editor sees** "The service couldn't finish this. Ask the owner for details." **The stored detail is** "Prediction failed: Async prediction failed: Exception: The request failed because the output video may be related to copyright restrictions. Request id: 0217930…/0217929…".
- **References lines** (as stored now): #13 c1 and #14 c1 "[Image1] is the first frame. [Image2] is the Girlfriend."; #12 c2 "… [Image2] is Nate. [Image3] is the Girl."; #9 c2 "… [Image2] is Carl. [Image3] is the girlfriend. [Image4] is the rival."; #11 c2 "… [Image2] is Nate. [Image3] is the girlfriend."
- **Every refused clip has Goth GF (char 1).** Her sheet, like Carl's and Mogging BF's, was made from an uploaded picture. Those pictures are 3D character renders, not photos of real people (`source_pictures_gothgf_carl_moggingbf.jpg`).
- **No voice sample** is attached to any of them.
- **Brand or studio words:** "Pixar-style 3D animation, big glossy eyes…" in every Style line. No car, watch or fashion brands.
- **Neither is enough on its own:** Goth GF and "Pixar-style" are also in clips that went through, including all 6 takes of #16 and #4 c1. The refused clips are all the opening breakup or rejection clips. That's a pattern, not a proven cause.

## Refusal rates across the whole site (98 take attempts on 56 clips)
- Most refused: a tie between Kel's #13 c1 and #14 c1, 7 copyright refusals each. #13 c1 also had 2 "service unavailable" failures and worked on its 10th try; #14 c1 worked on its 8th.
- Per take attempt, from the app's job records (references as stored now):
```
all clips with takes               clips 56  refused clips 5  tries  98  refusals 23  (23% of tries)
with a photo-made look             clips 50  refused clips 5  tries  91  refusals 23  (25% of tries)
photo-made looks only              clips 37  refused clips 5  tries  75  refusals 23  (31% of tries)
with a drawn look                  clips 13  refused clips 0  tries  16  refusals  0  (0% of tries)
drawn looks only                   clips  0  refused clips 0  tries   0  refusals  0  (0% of tries)
no character look at all           clips  6  refused clips 0  tries   7  refusals  0  (0% of tries)
with Goth GF                       clips 36  refused clips 5  tries  74  refusals 23  (31% of tries)
photo looks, no Goth GF            clips 14  refused clips 0  tries  17  refusals  0  (0% of tries)
Goth GF plus a drawn look          clips  9  refused clips 0  tries  11  refusals  0  (0% of tries)
prompt says Pixar                  clips 56  refused clips 5  tries  98  refusals 23  (23% of tries)
```
- Every refusal is on a clip with Goth GF and only photo-made looks. Photo-made looks without her (Carl, Mogging BF, Wyatt, Kimchi) were never refused (0/17). Clips with any drawn look were never refused (0/16, a small and recent sample).
