# QA-Live 6: Kel's faces, screens and charges (2026-10-27)

Read-only pass on the live site as the QA owner. Nothing was saved, redone, approved or paid.
One caveat: opening a video's Clips list runs the app's free, automatic clip repair (the same one a deploy runs), so the clip prompts below are as they stand now.

## Which videos

Kel has **one** finished video ("Video done"): **#4 "Turned down in Paris, then she begs at the red light" (A)**, finished 2026-10-26 23:27 UTC.
No second one exists. So these are also covered: Kel's two newest videos where every clip has a picked take (no final video made yet):
**#13 "Marriage Rejection — The red light" (B)** and **#14 "Marriage Rejection — The yacht wake" (C)**. They are the videos the screen questions are about (made around the 04:00 release).

Contact sheets in `frames/` (`p<video>_<clip>.jpg`): 2–3 frames per shot, each labelled with the clip, shot and second in the take. `sheets_carl_gothgf_moggingbf.jpg` holds the approved sheets (unchanged since 2026-10-25, before every take).

## Summary

1. **#13 and #14: the hero, Noah, has no character at all.** The breakdowns give his shots no character, and the script's cast has only "Girlfriend". So no sheet of Noah is ever attached, and every clip invents him again from its storyboard still: a young brown-haired man in clip 1, a black-haired man in #13 clip 2, a redhead caricature in #14 clip 2, and an older stubbled man in #13 clip 4. The rival is never cast either and changes face inside #14 clip 1. The Girlfriend, the only one with a sheet, holds.
2. **#4: Nate holds** to his sheet (Carl) across all three clips, with small drift only at the very end of clip 1 and in dark montage shots. His sheet is [Image3] in clip 1 (after the Girlfriend) and [Image2] in clips 2–3. It held either way.
3. Drift is worst in long clips with many shots (16–19 shots in 16–19 s), in flashbacks and dissolves, and in montage clips with no character picture.
4. **Screens:** every app screen in the takes is on the phone in hand (or on desktop monitors), except one full-frame invented screen in #4. But **"Use the real image" is on for all 12 screen shots of #13 and #14.** When their videos are made, those stretches will be covered by the flat screenshot, which is exactly what #546 tries to avoid. Only a person pressing the switch on the Clips screen turns it on, and the app records neither who nor when.
5. Failed takes cost no credits. Every charge below is for a take that was delivered.

## (A) Faces, per clip

Cuts are counted by ffmpeg scene detection (montage flicker can add some).

### #4 Turned down in Paris (A), breakdown 7. Characters: Nate = Carl (char:3), Girlfriend = Goth GF (char:1), older man = Mogging BF (char:2)

| Clip | Length | Shots | Cuts in take | Characters | References in order | Picked take | Face |
|---|---|---|---|---|---|---|---|
| c1 | 18 s | 1.1–1.11, 2.1, 2.2, 3.1–3.3 (16; none marked montage) | 16 | GF, older man, Nate | [Image1] frame:c1, [Image2] Girlfriend, **[Image3] Nate**, [Image4] older man. Hero not first | take 1 (id 2) | Matches the sheet to 12.1 s. Drifts at 16.1 s (3.1, backlit, hair reads dark and curly) and 17.4–17.7 s (3.3, narrower face, darker hair). Flashback 2.1–2.2 (13.8–15.0 s) washes out in the dissolve |
| c2 | 12 s | 4.1–4.12, 5.1–5.3 (15; quick wordless montage) | ~23 (day–night flicker) | Nate | [Image1] frame:c2, **[Image2] Nate**, [Image3] Token chart down, [Image4] Token chart up, [Image5] Home (rich) | take 1 (id 1) | Matches (cap added by the prompt). Mild drift in the dark night shots 4.7–5.1, 5.0–9.2 s (grey face, eyes change) |
| c3 | 17 s | 6.1–6.14 (14) | 9 | Nate, GF, older man | [Image1] frame:c3, **[Image2] Nate**, [Image3] Girlfriend, [Image4] older man, [Image5] Home (rich) | take 2 (id 17; take 1 id 3 not kept) | Matches throughout, including the extreme close-up 6.8 at 9.5 s |

Note: Carl's role text says "tan skin, dark curly hair" but his approved sheet shows fair skin and light-brown hair. The takes follow the sheet.

### #13 Marriage Rejection — The red light (B), breakdown 66. Characters: Girlfriend = Goth GF (char:1) only. **Noah and the rival have no character**

| Clip | Length | Shots | Cuts | Characters (per breakdown) | References | Picked take | Face (Noah, no sheet) |
|---|---|---|---|---|---|---|---|
| c1 | 16 s | 1.1–1.15 (15) | 13 | GF only | [Image1] frame:c1, [Image2] Girlfriend | id 45 | Young, brown wavy hair, navy shirt. Steady within the clip. Flashback 1.14 (12.4 s) slightly different. Rival: slick black hair, leather jacket |
| c2 | 6 s | 2.1–2.7 (7, montage) | 5 | none | [Image1] frame:c2, [Image2] Token chart down, [Image3] Token chart up | id 47 (id 34 not kept) | **A different man**: black hair, pale (2.0–5.8 s) |
| c3 | 5 s | 2.8–2.14 (7, montage) | 6 | none | [Image1] frame:c3, [Image2] Desktop trading, [Image3] Home (rich) | id 35 | Brown messy hair, close to c1 but not the same (1.2–2.5 s) |
| c4 | 15 s | 3.1–3.16 (16) | 13 | GF only | [Image1] frame:c4, [Image2] Girlfriend, [Image3] Home (rich) | id 36 | **A different, older man** with dark hair and stubble that changes between shots: slick at 5.8 s (3.8), messy at 7.4–7.9 s (3.10), spiky at 11.4–12.6 s (3.14–3.15). The rival is also a new face (3.7, 5.3 s). The GF matches |

The script line names him ("Noah?"), and the breakdown even says "Noah" in the actions, but `character_ids` is empty for every Noah shot.

### #14 Marriage Rejection — The yacht wake (C), breakdown 71. Same cast: Girlfriend only

| Clip | Length | Shots | Cuts | Characters | References | Picked take | Face |
|---|---|---|---|---|---|---|---|
| c1 | 19 s | 1.1–1.17 (17) | ~20 | GF only | [Image1] frame:c1, [Image2] Girlfriend | id 59 | Noah: brown wavy hair, tux. Steady at 2.7–12.0 s. **Flashback 1.15 (14.2–14.8 s) is a different young man** in a hoodie, and his hair darkens at 16.1–17.4 s. **The rival changes inside the clip**: tall and slick-haired in a navy suit at 6.0 s (1.9), a heavy mustached face at 9.6 s (1.12) |
| c2 | 7 s | 2.1–2.8 (8, montage) | 5 | none | [Image1] frame:c2, Token chart down, Token chart up | id 53 | **A redhead caricature with a big nose**, not the c1 Noah (0.6–6.8 s) |
| c3 | 5 s | 2.9–2.15 (7, montage) | 5 | none | [Image1] frame:c3, Desktop trading, Home (rich) | id 52 | Curly brown hair, a third look (1.2–4.8 s) |
| c4 | 16 s | 3.1–3.14 (14) | 12 | GF only | [Image1] frame:c4, [Image2] Girlfriend, [Image3] Home (rich) | id 54 | Noah close to c1 (white suit). The rival is the mustached man. The GF is softer and rounder at 2.3–3.0 s (3.3–3.4), otherwise matches |

### Patterns
- **Missing hero sheet (#13, #14): the main cause.** With no picture, each clip's storyboard still decides Noah's face, so he changes at every clip boundary.
- Long clips (15–19 shots in 15–19 s, #4 c1, #14 c1) drift late in the clip and in flashbacks.
- Montage clips carry no character picture at all (only screens), so the hero is free to change (#13 c2, #14 c2 and c3).
- A misordered hero sheet (#4 c1, [Image3]) did not cause drift here.

## (B) Screens

| Video | Shot (time in take) | Shown as | Use the real image |
|---|---|---|---|
| #4 c2 | 4.3 (1.0–1.5 s), 4.6 (4.2 s), 4.8 (6.3–6.5 s), 4.10 (7.1 s) | Phone in hand | off |
| #4 c2 | 4.11 (8.0–8.2 s) | **Full frame**, invented UI (gibberish text, "$1,280,000") | off |
| #4 c3 | 6.14 (14.9–16.3 s) | Phone in hand to camera. The real Home screen reads $348,920.15, not the script's $1,280,000 | off |
| #13 c2 | 2.2 (1.1–1.4 s), 2.6 (4.7–5.0 s) | Phone in hand | **on** |
| #13 c3 | 2.8 (0.3–0.6 s) desktop monitors, over the shoulder; 2.14 (4.2–4.6 s) phone in hand | | **on**, both |
| #13 c4 | 3.12 (9.5–10.4 s) and 3.16 (13.5–14.5 s), phone in hand | | **on**, both |
| #14 c2 | 2.3 (1.2–1.5 s), 2.6 (4.7–5.0 s), phone in hand | | **on**, both |
| #14 c3 | 2.9 (0.3–0.6 s) monitors; 2.14 (3.4–3.8 s) phone in hand | | **on**, both |
| #14 c4 | 3.13 (11.1–12.0 s) and 3.14 (13.4–15.2 s), phone in hand | | **on**, both |

**Who turned it on, and when:** only `PUT /projects/{id}/clips/{clip}/inserts/{shot}` sets it, from the switch on the Clips screen. Nothing else (seed, deploy, migration, AI) does. The switch stores only true or false: no person, no time. Kel is the only editor on both videos (owners can press it too).
Why it was offered at all before #552: the cut-in used to be offered only on shots with **no characters**. Because Noah is uncast, every one of his phone shots counted as a "no characters" insert shot.
No final video exists yet for #13 or #14, so no cut-in has been applied to anything yet. Making the video would cover these 12 stretches with the flat screenshot.

**Timing.** #546 merged 03:38 UTC and #552 merged 04:35 UTC (deploy shortly after each). Breakdown versions have no stored time, so these are the times of the jobs that made them:
- #4: breakdown 7 (an edited save) made after the breakdown job finished at 2026-10-26 02:44:59 and before the clip prompts at 03:24:37. Long before both changes.
- #13: breakdown 66, job 270, 2026-10-27 03:57:07–03:59:00. Storyboard 04:00:45–04:01:12, clip prompts 04:02:28–04:05:15. After #546 merged (its "phone in his hand" wording is there), before #552.
- #14: breakdown 71, job 374, 07:55:07–07:56:56. Storyboard 07:58:35, clip prompts 08:00:19. After both.

## (C) Money: clip charges (all by Kel; failed takes are not charged)

| Video | Charge id | Job | Clip | Credits | Time (UTC) | Kept? |
|---|---|---|---|---|---|---|
| #4 | none listed | 42 | c1 | 18 | 2026-10-26 03:36 | yes |
| #4 | none listed | 43 | c2 | 12 | 2026-10-26 03:35 | yes |
| #4 | none listed | 44 | c3 | 17 | 2026-10-26 03:37 | no (replaced) |
| #4 | 42 | 119 | c3 | 17 | 2026-10-26 08:16 | yes |
| #13 | 176 | 278 | c2 | 6 | 2026-10-27 04:10 | no (replaced) |
| #13 | 177 | 279 | c3 | 5 | 04:10 | yes |
| #13 | 178 | 280 | c4 | 15 | 04:11 | yes |
| #13 | 225 | 339 | c1 | 16 | 06:52 | yes |
| #13 | 230 | 345 | c2 | 6 | 07:01 | yes |
| #14 | 263 | 386 | c3 | 5 | 08:08 | yes |
| #14 | 264 | 385 | c2 | 7 | 08:08 | yes |
| #14 | 265 | 387 | c4 | 16 | 08:08 | yes |
| #14 | 272 | 400 | c1 | 19 | 08:58 | yes |

Totals: #4 64 credits, #13 48, #14 47. Nothing has been refunded.
#4's first three takes have no row in Usage → charges, so they would be refunded by job (the earlier QA-Live run logged the same gap).
Failed takes, not charged: #13 c1 eight times (six "copyright restrictions", two "Service is temporarily/currently unavailable") and #14 c1 six times ("copyright restrictions").

## (D) "Marriage Rejection" (script 2)
- Made by Reed at 2026-10-25 20:56 UTC, variations at 21:08. That is before the cast read existed (#333 merged 22:42, #340 22:56).
- **A cast read never ran on it.** All ten cast-read jobs on the live site are for other scripts (13, 19–28).
- Its cast has one role, "Girlfriend" (Goth GF, locked), added by hand. The groom (Noah) and the rival were never roles, so the breakdowns of A (#5, Mary), B (#13) and C (#14) leave them uncast, Assets asks for no look, and no sheet is attached. That is why Seedance invents the man.

## (E) "Mom gave him three days; a friend in a supercar scaled it" (#15, Mary)
Six failed clip prompt jobs, all with the same stored text. The editor sees "The service couldn't finish this. Ask the owner for details." The detail is **"Claude's answer was cut off or unreadable."**

| Job | Started | Finished |
|---|---|---|
| 419 | 14:38:24 | 14:42:43 |
| 420 | 14:51:32 | 14:55:55 |
| 421 | 14:56:37 | 15:00:49 |
| 422 | 15:07:18 | 15:11:46 |
| 423 | 15:17:01 | 15:21:06 |
| 424 | 15:34:11 | 15:38:29 |

Each ran about 4 to 4.5 minutes. The breakdown (76) has **6 clips and 82 shots** (c1 19 shots, c2 18, c3 4, c4 23, c5 7, c6 11; 79 s). Failed jobs cost no credits, but each Claude call still cost us about $0.11.

## (F) Mary's broken videos
- **#15 "Mom gave him three days…"** is stuck at Storyboard → Clips. In production it shows "Writing the clip prompts. It didn't finish. Open the video to try again." The job says "The service couldn't finish this. Ask the owner for details." It has failed six times (above).
- **#5 "Marriage Rejection" (A)** is stuck at Clips: c1–c3 have takes (not approved). c4 (17 s) has no take and is blocked by two problems: "Shot 11 starts at 11 s. The shot before ends at 12 s." and "Shot 11 has no line but doesn't say no one speaks". Its free "Fix this clip's prompt" has not been used. The same uncast-Noah problem as (D) applies.
- Mary's other videos, #9 and #11, are done with every clip approved.
