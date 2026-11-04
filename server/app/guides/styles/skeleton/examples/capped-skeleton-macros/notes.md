# skel-72e6f2: glass-shell skeleton with fast push-ins and fly-throughs inside the body

Look and feel only. No words, product or offer from the video are recorded here.

## 1. Source
- File: `.context/drive/skeleton/skel-72e6f2.mp4`, 720x1280, 29.97 fps, 131.3 s. Reed's folder note for Skeleton: "Typically used with a voiceover and visuals zooming in and showing whatever is being said. Can be used in combination with a lot of other scripts as well."
- Studied 2026-11-03 by study-skeleton (fork), Phase 1.
- How it was read:
  - Deep-watch kit (`.context/watch/skeleton/skel-72e6f2`): optical-flow camera numbers per shot and per second, colour stats, demucs stems, spectrograms, and word times (used only for timing).
  - Two extra 10–20 fps strips: 8.9–9.6 s and 9.9–11.3 s.
  - A per-frame sharpness scan to find blur and mirror transitions.
  - My own scale meter ((a local scratch script, not in git)) proved unreliable here. The fixed caption in the middle of the frame dominates its phase correlation and pins the scale at 1.0, so I used the deep-watch flow numbers and checked them against the strips.
- What I watched:
  - All seven spectrograms; the hook strip.
  - Every strip in the first 31 s (shots 1 and 3–19; shot 2 seen in the hook strip only).
  - After 31 s, every other strip plus every fast push: 20, 22, 24, 26, 28, 30, 32, 33, 34, 36, 38, 39, 40, 42, 44, 46, 48, 49, 50, 52, 53, 54, 56, 58, 60, 62, 64, 65.
- Not watched as strips: 21, 23, 25, 27, 29, 31, 35, 37, 41, 43, 45, 47, 51, 55, 57, 59, 61, 63. These come from the contact sheet and the numbers only.
- I can't play sound. I "hear" it through the stems, spectrograms, loudness per 100 ms, pitch and word timing.

## 2. Length
- 131.3 s.
- Shots: 65 detected (4.95 cuts per 10 s). The sharpness scan found about 5 more joins hidden inside detected shots (at 21.7, 37.6, 43.3, 107.0 and 122.0 s), so the true count is about 70 shots, roughly 5.3 cuts per 10 s *(inferred)*.
- Shot length:

  | Shortest | 25th percentile | Median | 75th percentile | Longest |
  |---|---|---|---|---|
  | 0.40 s | 1.13 s | 1.84 s | 2.47 s | 5.57 s |

- 459 words. 3.71 words/s while speaking.

## 3. The hook (first 2 s)
- **0.0–0.3 s:** front medium-full shot of the character standing on a white-grey seamless studio floor. The skull is tilted down and the big cartoon eyes look at its own legs. A soft red glow shows at the pelvis.
- **0.3–0.5 s:** the camera drops fast, a whip-tilt down the body with motion blur. In about 0.2 s it lands on a locked shot of both shins inside the clear shell, knees to feet.
- **0.93 s:** hard cut to a macro of one shin bone through the glass, with sparse dark hairs. It drifts, then a bony hand slides into frame (1.6–2.0 s).
- **2.17 s:** cut to the character in a lamp-lit bedroom with feet on a glowing heater.
- **What moves:** the camera, not the character. In under half a second the hook goes from the whole body to the exact body part, then into it.

## 4. Shot by shot
Runs of similar shots are grouped. Every fast push and every effect transition has its own row. "Zoom" is the deep-watch radial flow in % scale a second (positive = in).

| Time (s) | Hold | Shot size | Camera (zoom %/s) | On screen | Into next |
|---|---|---|---|---|---|
| 0.00–0.93 | 0.93 | medium-full → full of shins | whip-tilt down and tighten (-12.9 flow, read as a down-move; shake 24) | character on white studio, then the legs | hard cut |
| 0.93–2.17 | 1.23 | macro | slow drift | shin bone with hairs through the glass; hand enters | hard cut |
| 2.17–3.30 | 1.13 | medium | push in (+15.1) | bedroom at night, feet on a glowing heater under a blanket | hard cut |
| 3.30–5.27 | 1.97 | close (shins) | push in (+10.5) | red glowing slash marks appear on the shins, warm heater light | hard cut |
| 5.27–7.74 | 2.47 | medium-full → full of legs | push to the pelvis glow, then fast tilt down (+2.8, tilt -7.5) | studio → living room; the shell goes see-through to show red and blue vessels down the legs | hard cut |
| 7.74–9.11 | 1.37 | macro | static | cut-away vessel with yellow plaque narrowing the flow | 2-frame mirror/kaleidoscope swipe (9.10–9.15) |
| 9.11–11.21 | 2.10 | medium → extreme close of face | radial-blur "time tunnel" behind; **crash push 10.1→10.5 s, about 2x in 0.4 s**; then held | character holding a wall clock; lands on the skull's eyes | blur-in cut |
| 11.21–12.05 | 0.83 | close ribcage → medium | **fast pull-back 11.2→11.4 s** (reveal) | kitchen, character holding two amber capsules | hard cut |
| 12.05–13.45 | 1.4 | close / medium | small moves | eating a capsule (12.05); sitting on a bed, head bowed (12.78) | hard cuts |
| 13.45–14.51 | 1.07 | macro | locked | shin hairs fall away from the bone | hard cut |
| 14.51–15.78 | 1.27 | close → extreme close face | **whip from the shin up to the face (14.5–14.7)**, then held | wide-eyed skull, bedroom behind | blur-in |
| 15.78–18.25 | 2.47 | macro fly-through | **fly forward down an artery (+45.5)** | lumen walled with yellow plaque, red cells tumbling | hard cut |
| 18.25–20.95 | 2.7 | macro cross-section | slow push (+5.7) | skin and hair-follicle cross-section; follicle fades | hard cut |
| 20.95–22.72 | 1.77 | medium → extreme close of a capsule | **push in (+31.5), about 2.3x in 1.2 s**, ends in a gold sparkle burst | kitchen, capsule held up between two fingers | hard cut |
| 22.72–26.93 | 4.2 | macro | push and pan (+1.5, pan -11.6) | amber fluid flows down an artery and melts plaque | hard cut |
| 26.93–30.33 | 3.4 | medium-full → full | push (+8.2) | studio → outdoor concrete stairs; character walks down, crouches; **dissolves into a leg-muscle anatomy view (29.3–29.7)** | hard cut |
| 30.33–36.67 | 0.8–3.4 | macro, then medium | moves inside the body (pull -12.1 at 31.1) | muscle with vessels; plaque close-up; kitchen with a jar of dark cloves (34.5) | hard cuts |
| 36.67–41.04 | 0.5–2.5 | close → medium | a mirror swipe at 37.6 hides a cut | jar close → bedroom, sitting in socks; blur-in at 39.6 | hard cut / blur |
| 41.04–46.61 | 5.57 | full legs → macro | **continuous push into the shin, then into a vessel, morphing into a plaque-packed lumen (42.6–43.8)** | the clearest "zoom in on what's said" move | blur-in |
| 46.61–54.19 | 1.8–3.4 | macro | fly-throughs (+52.3, +11.8) | lumen with red and white cells and green particles | hard cuts |
| 54.19–60.49 | 1.0–2.7 | close / insert | locked or small | a red wound on the thigh with a cut-away vessel inset that slides in (54.6); a blood-pressure meter with changing digits (58.1) | mirror swipe at 59.1 |
| 60.49–72.71 | 1.0–2.9 | macro | pushes and fly-throughs (+18.7, +14.8, +5.4, +12.4, +31.5) | plaque lumen; cracked plaque; heart inside a grey ribcage on dark (69.97), which at 70.97 cuts to a tighter heart-surface macro | hard cuts |
| 72.71–74.87 | 2.17 | macro insert | opens from a motion streak (blur-in 72.5–72.9), then pull (-31.1) | glowing digital meter with digits climbing | hard cut |
| 74.87–77.04 | 2.17 | macro fly-through | push (+30.7) | lumen; plaque petals close in | hard cut |
| 77.04–79.41 | 1.2 + 1.1 | medium | static | bathroom: character takes colourful pills from a cabinet | hard cut |
| 79.41–90.59 | 0.4–3.9 | macro | fast fly-ins (+20.6, +13.1, +32.3) | pills tumbling in a lumen with white cells; vessel cross-section; calcium and plaque | blur-ins at 81.5, 86.6 |
| 90.59–95.96 | 5.37 | macro | opens from a blur, glides through amber molecules (-55.3, a forward-backward glide), then dissolves to a cracked aged bulb on a dark table | warm amber and brown | blur-in |
| 95.96–99.13 | 1.3 + 1.9 | macro | **fly-in down a lumen behind a gold metallic flow (+42.0)** | gold liquid cleans plaque | hard cut |
| 99.13–107.91 | 5.07 + 3.7 | macro → lineup grid | push and pan | gold flow; a 3x4 grid of colour-swapped skeleton variants (caps, jackets) eating capsules; hard cut to an extreme close of two capsules on bony fingers (107.0) | blur |
| 107.91–111.75 | 3.84 | macro | **push into a bulb that dissolves into molecules turning gold (+46.2)** | dark → glowing amber | blur-in |
| 111.75–117.52 | 0.7–2.1 | medium / macro | small | a teal x-ray "lab" skeleton holding a bulb in a dark lab; heart with yellow particles on black; product shots | hard cuts |
| 117.52–118.75 | 1.23 | extreme close face | static | eyes close and open; capsule held to the nose | hard cut |
| 118.75–125.83 | 0.5–3.1 | medium / wide / close | pans, one push (+13.0) | a clear "doctor" skeleton and the character in a clinic (120.4); hard cut at 122.0 to the character running down a city street with a crowd of skeletons; pack on a shelf; jar with a counting display | hard cuts |
| 125.83–131.2 | 2.1 + 3.27 | close → medium | push (+13.2), then held | jar of cloves turning dark; character on white studio holding the pack and pointing down (blur-in 127.9) | end |

## 5. Zoom-in behaviour (the core of this style)
Numbers are from deep-watch shots.json and camera_timeline.json, then checked against the strips.

**How often:**
- 33 of 65 shots push in at more than 1.5 %/s (51% of shots, 54% of the runtime).
- 52% of all seconds (68 of 131) show zoom above 1.5 %/s.
- A new push-in starts about every 3.3 s (median), roughly 2.5 per 10 s.
- Pushes come in runs of 1–6 consecutive shots.
- 10 shots (15%) pull out. Most are fast reveals of under 0.3 s at the head of a shot (0.3 s, 11.2 s, 72.7 s, 90.6 s), not slow pull-backs.

**How fast:**

| Kind | Shots | Speed (%/s) | Median |
|---|---|---|---|
| Steady push (generated camera, from frame one) | 11 | 1.7–14.8 | 7.0 |
| Fast push or fly-through | 22 | up to 52 | 14.1 |

- Deep-watch flags many fast pushes as "handheld shake". The strips show smooth forward fly-throughs curving down a vessel, not handheld camera.
- Crash pushes on the character are the fastest:
  - face, shot 7: about 2x scale in 0.4 s
  - capsule, shot 15: about 2.3x in 1.2 s
  - the shin-to-face whip, shot 12: about 0.2 s
- Inside-body macros carry most of the zoom: median about +6.7 %/s. Character and world shots have a median of about 0.1 %/s and get their energy from short whips instead *(grouping inferred from strips and contact sheet)*.

**On what.** Always the body part, object or process the line names, and never a random drift. Four moves repeat:
1. **Drop to the part.** A fast whip from the whole body down to the named area, often with the shell turning see-through to show vessels or glow (0.3 s; 5.3–7.7 s; 26.9–29.7 s).
2. **Crash push to the face** on an emotional beat, then a held extreme close (10.1–10.5 s; 14.5–14.7 s).
3. **Push through into a macro.** One continuous move from the outside view into the vessel, which morphs into the inside-body render (41.0–43.8 s; the capsule at 21–22.6 s; the bulb into molecules at 107.9–111 s).
4. **Fly-through down the lumen** in the macro world (15.8, 46.6, 60.5, 74.9, 83.5 and 96.0 s).

**Camera or edit.** The zooms are moves generated inside the clip. They show parallax, perspective change and focus pulls, and the captions stay fixed through every one. I found no scale-up made in the edit.

**The contact sheet's "two skull shots"** at about 10.3 s and 10.7 s are not a re-cut of the same image tighter. The 10 fps strip shows one continuous crash push inside shot 7 (medium at 10.1 s, extreme close at 10.5 s, held to 11.2 s).

**Transitions.** About 20 of about 70 joins use a 70–330 ms blur-in (motion or zoom blur opening the new shot: 9.1, 15.8, 39.6, 46.6, 72.7, 81.5, 86.6, 90.6, 96.0, 111.7, 127.9 s) or a 2–3 frame mirrored kaleidoscope swipe (9.15, 37.6, 59.1 s). The rest are hard cuts. Blur-ins sit within 0.1 s of the cut.

**Timing to words and beats:**

| Cuts that land within 0.1 s of a… | This video | Random times |
|---|---|---|
| word start | 52% | 63% |
| beat | 41% | 38% |

- 17 of 64 cuts fall mid-word.
- So cuts and zooms are **not** locked to word starts or beats. They change on the caption phrase, about every 6 words (median words per shot 6, range 0–21).

## 6. Pacing
**Ranges:**
- Shots 0.4–5.6 s, median 1.8 s.
- About 5 cuts per 10 s overall.

**Where it changes:**

| Stretch | Pace |
|---|---|
| Hook, 0–15.8 s | Fastest: 12 shots, about 7.5 cuts per 10 s; holds 0.5–2.5 s |
| Middle explanation, 40–72 s | Slows to macro holds of 2–5.6 s; the push or fly-through carries the motion instead of the cut |
| 77–96 s | Speeds up again: 0.4–1.3 s inserts between fly-throughs |
| Close, 116–131 s | Short world shots (0.5–1.7 s), then a 3.3 s end hold on the character |

- Longest holds are macro fly-throughs or push-throughs (5.4–5.6 s at 41.0 and 90.6 s). Character shots rarely run past 2.5 s.

## 7. Sound
**Voice:**
- One male narrator: median pitch 139 Hz, variability 5.4 semitones (animated, storyteller rise and fall).
- 3.71 words/s, 23 pauses over 0.25 s, longest pause 0.46 s: nearly wall to wall.
- Voice sits steady at about -18 to -20 dB the whole way.
- Integrated loudness -14.2 LUFS; loudness range 5.6 LU.

**Music bed (it builds):**

| Time | Bed |
|---|---|
| 0–9 s | Bass-led beat about 14 dB under the voice |
| 9.1–11.2 s | A rising sweep fills the gap under the "rewind" clock shot: a riser or rewind sound effect, the one clear effect in the video |
| 12–70 s | Bed nearly gone, about 30 dB under the voice; soft sustained tones in the "other" stem |
| From 77.6 s | A fuller beat enters (kick, bass, melodic line) and rises to about voice level by 110–131 s (drums about -18 dB against voice about -20 dB) |

- Tempo 112 BPM.

**Effects:**
- No consistent whoosh on the blur-in transitions shows in the stems *(I can't hear; this is from the spectrograms)*.
- No impacts on cuts.

## 8. On-screen text (an editor layer)
- **Captions:**
  - Heavy rounded white sans with a thick black outline and soft shadow.
  - Mostly lower case as spoken.
  - One line of 1–4 words (usually 2–3) per page, centred at about 64% of frame height.
  - Pages swap on the phrase with no pop, no scale and no highlight colour.
  - They stay put through every zoom and transition.
- **Words inside the picture:** generated digits on meters, a counting display on a jar, and a calendar-like countdown. Under rule 32 these would not be burned into our clips. Note them for the editor if wanted.

## 9. Style pattern (look, light, colour, camera)
**Character:**
- An ivory anatomical skeleton with natural adult proportions inside a smooth clear glass or vinyl body shell (shoulders, chest, belly and limbs as a transparent outline).
- Large cartoon eyeballs with brown irises set in the sockets.
- Identity kit, kept in every shot: black backwards cap, black over-ear headphones around the neck, silver chain, olive cargo shorts.
- A soft red glow at the pelvis or gut marks the problem area.
- Variants appear for crowd beats: a grid of colour-swapped caps and jackets, a clear-headed "doctor" in a lab coat, and a cool teal x-ray lab skeleton.

**Places:**
- Clean, modern, neutral photoreal 3D: a white-grey seamless studio (open and close), a grey-white kitchen, a living room, concrete outdoor stairs, a bathroom, a clinic, a city street.
- Plus one warm lamp-lit bedroom at night.
- Soft daylight, low contrast, shallow depth of field.

**Macro world:**
- Glossy 3D medical illustration: artery lumens with red cells and lumpy yellow plaque, a skin and follicle cross-section, muscle with vessels, a heart in a grey ribcage on dark, amber glass ball-and-stick molecules.
- Saturated reds and yellows, depth of field.
- About 23 of 65 shots and about 42% of the runtime *(inferred from strips plus the contact sheet)*.

**Colour (deep-watch):**

| Measure | 10th–90th percentile | Median |
|---|---|---|
| Brightness | 34–59 | 46 |
| Contrast | 15–22 | — |
| Saturation | 12–53 | 29 |
| Warmth | 0 to +24.5 | +9 |

- Two worlds:
  - **Character and world shots:** neutral-cool white-grey. Saturation about 19, warmth about +6; for example the studio #A0A2A0 and the kitchen #89837B.
  - **Macros:** warm and saturated. Saturation about 49, warmth about +22; for example #9C552C and #8F5840.
- The bedroom #AB7E76 is the one warm character set.

**Camera:**
- The character is framed frontal and centred, medium to full, with frequent extreme closes on the face.
- Motion comes from whip drops, crash pushes and fly-throughs, never handheld.

## 10. Lane match
None of the current lanes fits cleanly. Closest: **Bare-Bones, dressed**, plus a clear body shell and x-ray-style inside views.

**Matches Bare-Bones:**
- An ivory anatomical skeleton with natural adult proportions and big cartoon eyes.
- One recurring character in every character shot, wearing one outfit (the guide's "Dressed" option).
- Real environments.

**Differs from Bare-Bones:**
- The clear glass or vinyl body shell, which neither the guide nor any lane describes.
- Neutral-cool, clean daylight sets, not "warm colour grade, soft volumetric light with drifting atmosphere".
- About 42% of the runtime is glossy medical macros with no skeleton in them. That breaks the guide's "The skeleton is in every shot".

**Against skeleton-xray:**
- The "show the inside" job fits.
- But there is no blue-tinted glowing skin and no organs lit red and orange inside the character. The inside is shown by cutting into separate macro renders.

**Skeleton-cute:** not a match (not chibi, no pastel set).

## 11. Why it works (for the viewer, look-wise)
- The first half second goes from the whole body straight to the exact part, so the eye always knows where to look.
- Every claim gets its picture within a beat.
- The clear shell makes "inside your body" readable while the character still feels like a person in a real room.
- Alternating between a likeable cartoon face and gross, glossy macros gives a constant pattern break about every 2 s.
- The fly-throughs give a sense of travelling deeper.
- The music bed builds late, lifting the energy into the close.

## 12. How the director recreates this from any script
- **Per line, choose one of four moves:**
  - (a) drop to the named body part, with the shell going see-through
  - (b) crash push to the face for a feeling
  - (c) push through from the outside into a macro of the process
  - (d) fly down a vessel or tunnel inside the macro
- **Recurring character:** keep one glass-shell skeleton with a fixed identity kit (hat, headphones, outfit, one prop) in every character shot. Use colour-swapped variants only for "many people" beats.
- **The two worlds:** cut between the clean neutral-daylight world and the warm saturated macro world. Put the steady pushes (about 2–15 %/s) in the macros and short whips and crash pushes (0.2–0.4 s) on the character.
- **Pacing:** shots of 0.4–5.6 s, median about 1.8 s. Fastest in the first 15 s.
- **Edit:** hard cuts, plus a 70–300 ms blur-in on about a third of the joins and an occasional 2-frame mirror swipe.
- **Captions (an editor layer):** 2–3-word pages of heavy white rounded sans with a black outline, at about 64% of frame height.
- **Sound:** one animated narrator nearly wall to wall. A quiet bed for most of the video that builds into a full beat for the last third; one riser for a time-jump moment.
- **Don't copy:**
  - the specific complaint, the capsules, jars and pack, the meters and countdown digits, the street run, the doctor endorsement
  - the cap, headphones and cargo shorts kit itself (choose a new kit per brand)
  - the wound shot (keep it gentle: glow, not gore)
