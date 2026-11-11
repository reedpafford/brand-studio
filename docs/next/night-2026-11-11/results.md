# One-pass test videos, Palace Guard (brand 8): results
Reed, 11 Nov: test all styles on the live site, priority talking head with B-roll and movie ad; under $6 a video all-in; first 30 s or less; JC42 (RP8) whole, one take, under $3. "Track usage, and all important metrics to measure performance as well as output quality."
Scripts doc: https://docs.google.com/document/d/1eh8zJw2cJLXNVU7rkht3zItOfsZuwUlwR3zo44LQ7bA (tabs marked "(claude test)"; copies in `doc/`, excerpts in `excerpts/`).
Numbers come from the site's own records: `/api/spend/videos/{id}` and `/api/jobs` (read in the signed-in tab). Earlier-path numbers for the same scripts are in `sanaa/.context/team/ROUND3.md` (RP1 345, RP3 353+355, RP7 347).

## Per video (fill one row as each finishes)
| # | Test | Format · Look | Video id | Price shown before Make it | Real cost $ (film / pictures / voice-song / Claude) | Jobs | Claude calls | Clips | Remakes | Seconds delivered | $ per second | Send → plan (min) | Make it → delivered (min) | Stopped for me? (what) | Words right? | Faces/outfits hold? | Product right? | Hook in 2 s? | Edit/pacing notes | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Movie ad RP5 (V1 hook + store scene) | Dialogue · Movie | 366 | $2.85 on Home, $5.45 on the plan | $6.71 (film ~$4.90 incl. a failed clip billed ~$0.82; 6 pictures ~$0.90; Claude ~$0.67) | 37 | 1 plan + 5 small checks + 1 watch | 6 | 0 (1 clip failed at Google and was sent again) | 60 | $0.11 | 2.5 | 12 | No | "Some words differ" (not yet listened by me) | Yes: Paige, the men, both places hold across clips | Product picture attached to clip 2 by the director itself | Yes: mom running with phone, van behind | Planned 60 s, not 30; Omni 720p | Delivered, over $6 by $0.71 |
| 2 | Talking head RP2 (Hook 1 + 3 lines) | Presenter · UGC | 370 | $8.84 on Home, $5.36 on the plan | $5.83 (no watch run) | ~40 | 4 plan calls (3 failed) | 7 (4 talker, 2 B-roll, 1 real footage) | 0 | 33 (64 s of clips paid for) | $0.18 | 11 (plan failed twice) | 3 to clips; cut blocked 26 min until I pressed Make the cut | Yes: plan failed twice; cut refused (real-footage clip never approved) | Not yet listened | Yes: dad identical in all 4 clips (each starts from one still) | n/a | Yes: dad to camera at once | B-roll covers about 2/3 of the cut, more than the guide wants; half the paid talker seconds are hidden under it | Cut made by hand; fix in PR #1546 |
| 3 | Pixar talking (RP5 V2, mom's POV) | Dialogue · Disney Pixar | 373 | $3.43 on Home, $4.32 on the plan | $4.57 (2 takes of one 19 s Seedance 2.5 clip ~$3.80) | 15 | 1 plan + 2 checks | 1 | 1 (officer's line not heard on take 1) | 19 | $0.24 | ~4 (waited behind another plan) | 11 | Yes: kitchen place had no picture (blank RP4 place) | Yes after the remake; two gasps added | 1 person, 1 place | n/a | Phone buzzing on the counter | One 19 s clip | Delivered |
| 4 | Pixar song RP3 (Mood 1, first 2 verses) | Song · Disney Pixar | | | | | | | | | | | | | | | | | | |
| 5 | Narrated RP6 (Hook 1 + 3 lines) | Narrated · Movie | | | | | | | | | | | | | | | | | | |
| 6 | Zack D RP7 (Hook 1 + 5 lines) | Zack D · Zack D | 383 | $4.52 on Home, $2.81 on the plan | about $3.70 (36.7 credits: 3 Seedance 2.0 480p clips ~$2.18, 6 pictures ~$0.90, narration + Claude the rest) | 30 | 1 plan + small checks + 1 watch | 3 | 0 | 27 | ~$0.14 | ~10 (queued behind other plans) | 9 | Yes: store-lot place had no picture (blank RP4 place) | Not yet listened | Not yet watched | n/a | Not yet watched | 3 clips for 28 s; is it one continuous camera? check | Delivered |
| 7 | JC42 RP8 (Hook 2 + whole body, one still + scrolling text + voice) | off-site assembly | | | | | | | | | | | | | | | | | | |

## Second round (after tonight's fixes)
| # | Test | Video | Planned | Real cost | Clips | Seconds | Send → delivered | Stopped for me? | Words (whisper) | What changed on screen |
|---|---|---|---|---|---|---|---|---|---|---|
| 1b | Movie ad, same excerpt as 366, after #1550 (plan places every shot) | 389 | $5.46 | $5.82 | 7 | 62 | 19 min | No | All lines, in order; the cart kid says "I got it" once too often | Staging is clearly better: over-the-shoulder shots with the man small at the far end, the three men seen from above walking away, Paige followed from behind down the aisles, the men now three different people. Still weak: the lot's wide has Paige standing stiff facing us; the store's ceiling changes between its five clips (the Movie guide half, #1548, is not merged: it makes a scene one clip). Frames: `night/data/sheet-389-0.jpg`, `-1.jpg`; cut: `night/data/cut-389.mp4` |

| 2b | Talking head, same excerpt as 370, after #1547 + #1557 | 390 | $4.62 | $5.14 | 6 (4 talker, 1 B-roll, 1 real footage) | 31 | 10 min from the working plan (two failed plans before #1557 cost $0.60 and a stop) | Before #1557: yes. After: no | All lines. Clip 1 adds a made-up sentence ("If I have to hear about another detention, then I'm going to change") and "save her life, you life" (fix: #1560 mutes such words free) | The dad is on screen about three quarters of the time; B-roll is 10 s of pictures that add something (the runner, the empty path, an untouched bed, a mother and daughter unloading a car). Frames: `night/data/sheet-390.jpg` |
| 4 | Pixar song RP3 (Mood 1, first two verses) | 377 | $2.62 | $3.86 | 3 | 21 | Stopped three times on site faults since fixed (#1546 style card, picture outage, #1558 false same-person) | Yes, each fixed | Lyrics clear and right | Paige in the store, the man with a cart, volleyball practice, the store at dusk. Frames: `night/data/sheet-377.jpg` |
| 5 | Narrated RP6 (Hook 1 + 3 lines), House look (Movie is Dialogue only) | 379 | $3.03 | $4.29 | 3 | 26 | Stopped three times on site faults since fixed (#1546 extra word, picture outage + #1555, cast OK) | Yes, each fixed | Word for word | Rich pictures: a rose on a windshield behind police tape, a crime scene, a detective at a pin map, the woman smelling the rose. Frames: `night/data/sheet-379.jpg` |
| 7 | JC42 RP8, three hooks | 385-388 (narrations only) | n/a | $1.11 | one still + scrolling text | 655 / 660 / 686 | built on my computer | n/a | The site's own sentence times drive the scroll | `~/Desktop/Palace Guard Ads/RP8 – v1.mp4`, `– v2.mp4`, `– v3.mp4` |
| L | Long script: the whole RP8 body (9,884 characters, 12 minutes) as a Narrated video, plan only | 391 | $61.31 (not pressed) | $3.22 | plan: 58 clips, 270 shots | narration 557 | narration 1.7 min, timing 4 min, plan 8.6 min | Stopped by me before Make it | Narration read in two parts and joined (#1553) | The plan for all 12 minutes was written in one answer and passed its check first try |

| 6b | Zack D RP7 again, with the Zack D voice (#1552) | 392 | $3.49 | $2.13 so far | 2 of 5 made | n/a | stopped at 12 min | Yes: Seedance 2.0 refused the three clips with the man ("the input image may contain real person"); fix #1562 sends them again with the people in words | Narration is in the Zack D voice (the site's style voice, MiniMax clone) | Not delivered yet |
| 8 | Narrated RP6, Skeleton look | 393 | $2.70 | $3.27 | 3 | 26 | 14 min, no stop | No | Word for word | True to the style: a glass skeleton woman finds the rose, the camera dives inside the body. Frames: `night/data/sheet-393.jpg` |
| 9 | Narrated RP6, Claymation look | 394 | $2.75 | $3.46 | 3 | 26 | 17 min, no stop | No | Word for word | Clay police, a clay map filling with roses, the woman at her car. Frames: `night/data/sheet-394.jpg` |

## What the transcripts say about round one (whisper on each cut, 11 Nov)
- 366 movie: every line, in order, nothing added.
- 370 talking head: every line; clip 1 stumbles ("I voted for aid for a closed border").
- 373 Pixar talking: every line. Acting and staging look strong (frames `night/data/sheet-373.jpg`).
- 383 Zack D: every line, read by the default voice (the Zack D voice is wired in since #1552). Three separate clips, not one continuous camera (frames `night/data/sheet-383.jpg`).

## Site and UI notes (anything that slowed, confused or broke)
- Four of six videos stopped and waited for a person. Causes and fixes: PR #1546 (cut refused when a clip isn't approved; narration with a word more refused; song style card over 500 characters; blank brand places; pilot clip).
- 04:39-04:50Z the site's API hung (pages loaded, data calls timed out) with six videos + the sanaa runner going; it came back by itself. Jobs kept running through it.
- The director's Claude steps (plans, checks, watches) run one at a time for the whole site: six videos queued behind each other.
- Home's first price is rough: $2.85 → $5.45 (movie), $8.84 → $5.36 (talking head, it counts B-roll over every second).
- "Nothing was charged" shown on a failed clip and failed plans that the spend totals do count.
- Talking head plan failed its line check twice (two paid tries) before it worked; cause unknown (failed answers aren't kept).
- Movie look: only with Dialogue; its "No sample yet" card selects only by its name. Narrated test used House instead.
- Cast: "These may be the same person" on The girl / First man (Zack D), wrong.
- Frames: `movie-366-frames.png`, `talkinghead-370-frames.png` in this folder.

## Totals
