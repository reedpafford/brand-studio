# skel-ac8fe0: glass-body cartoon skeleton, medical explainer (look-and-feel study)

## Source
- File: `.context/drive/skeleton/skel-ac8fe0.mp4` (720x1280, 30 fps, 160.7 s). From Reed's Drive "Skeleton" folder.
- Studied 2026-11-03 by study-skeleton (phase 1 draft). Read with the deep-watch kit (`watch/skeleton/skel-ac8fe0`: per-shot optical-flow camera numbers, per-second camera timeline, dense strips, demucs stems, spectrograms, word timings) plus an independent scale meter (5 fps grid search, (a local scratch script, not in git)) and an ffmpeg scene-change pass (threshold 0.12) to find edits the cut detector missed.
- Hearing limit: I can't play sound. Audio below comes from stems, spectrograms, loudness per 100 ms, pitch and word timing.
- Watched: hook strip; every strip in the first 30 s (shots 1-10); after that shots 12, 14, 15, 16, 19, 21, 22, 23, 24, 25, 27, 29, 30, 31, 34, 37, 40, 41, 43, 45, 47 (every fast push and every transition I could locate). Skipped strips: 11, 13, 17, 18, 20, 26, 28, 32, 33, 35, 36, 38, 39, 42, 44, 46 (short holds; numbers only). All 9 spectrograms read.

## Length
- 160.7 s. Deep-watch splits it into 47 shots (2.9 cuts per 10 s; shortest 0.87 s, median 2.4 s, longest 9.9 s).
- That undercounts: the old detector's 25 s "shot" and deep-watch's 8-10 s ones (shots 5, 6, 16, 29, 30, 40) hide dissolves, zoom-blur transitions and jump cuts between near-identical blue-backdrop frames. The scene pass finds about 72 change points (some are frames inside one dissolve); by eye I'd put the real edit count at **about 60-65, so about 3.8-4 edits per 10 s, median visual hold about 2 s** *(inferred from strips + scene pass)*.
- Speech: about 523 words, 3.41 words a second while speaking.

## Hook (0-2 s)
- 0.0-1.6 s: medium close-up of a torso, front on, chest to hips, centred. A clear glass-like body shell over ivory bones; a bloated, pink, fleshy belly mass bulges between the ribs and pelvis, and two bony hands squeeze it. Blurred gym behind (blue-grey). Camera: a slight push (1.7 %/s). What moves: the hands knead the belly.
- 1.6 s: hard cut to a low, ground-level close-up of shins and swollen pink feet inside the same glass shell; the feet shift. The clip loops once at about 2.4 s (the pose snaps back).
- 2.9 s: hard cut to a top-down view of one swollen hand (bones inside puffy pink tissue).
- So the hook is three body-part close-ups in 4.2 s, no face yet. The character's face first appears at 6.7 s.

## Shot by shot
Times from deep-watch; extra edits I found inside its long shots are listed in the same row.

| Time (s) | Hold | Shot size | Camera (zoom %/s) | What is on screen | Cut / transition out |
|---|---|---|---|---|---|
| 0.0-1.6 | 1.6 | MCU torso | slight push (1.7) | glass torso, bloated belly squeezed by bony hands, gym | hard cut |
| 1.6-2.9 | 1.3 | low CU feet | static (clip loops) | swollen pink feet in glass shell | hard cut |
| 2.9-4.2 | 1.3 | top-down CU hand | slight drift | swollen hand, bones visible | hard cut |
| 4.2-6.7 | 2.5 | CU rib cage | static | blue backdrop; red/blue vessels draw in, yellow plaque fills them as they're named | hard cut |
| 6.7-15.7 | 9.0 | MS full figure | static (0.7) | **the character**: lab with blue holo screens; props pop in and float beside him as they're named (a vegetable, a salt shaker, pill bottles), then get swept away. Jump cut at about 14.5 to a tighter chest-up; vessels light up red/blue | **zoom-blur transition** |
| 15.7-23.7 | 8.0 | MS → CU chest | static, then slow drift | blue backdrop; a softgel appears in his palm, golden aura bursts round the body; hidden cut at about 20.1 to a CU rib cage with glowing gold nerve lines | hard cut |
| 23.7-26.0 | 2.3 | MS seated | static | grey sofa, red glow in chest, cuff and monitor | hard cut |
| 26.0-28.3 | 2.3 | MS → CU feet | **fast tilt-down + push in about 0.4 s**, then hold | from torso down to the feet, which then glow red | hard cut |
| 28.3-30.9 | 2.5 | MS torso | slow pull out (-2.4) | belly glows orange and swells as named | hard cut |
| 30.9-33.1 | 2.2 | MS seated | static | slumped on sofa, giant clock face behind, hands spinning | hard cut |
| 33.1-34.6 | 1.5 | MS | pan | slumped on sofa | hard cut |
| 34.6-38.9 | 4.3 | inside an artery | **fly-through push (59)** | forward down a pink vessel, red cells streaming; plaque grows and narrows the tunnel | hidden cut to a top-down wide: lying spent on a bed |
| 39.8-41.1 | 1.3 | MS | locked off | (not viewed) | hard cut |
| 41.1-42.4 | 1.3 | CU face | slight push (2.5) | eyes droop, bags darken: ageing on the word | hard cut |
| 42.4-46.7 | 4.2 | MS seated on bed | static; hidden tighter cuts at about 43.6 and 44.8 | knees, then shins glow red as each is named; each cut frames the legs tighter | hard cut |
| 46.7-56.6 | 9.9 | MS → macro → CU | static; slow drift | knees glow → **dissolve** (47.9) into a calcified artery macro → second macro (49.9) → **dissolve** (51.0) to a CU face with the heart glowing in the chest → cut (53.8) to MS chest, black smoke ribbons wrap the heart | hard cut |
| 56.6-59.8 | 3.2 | MS / CU | slow push (2.1) | (17-18 not viewed) | hard cut |
| 59.8-62.7 | 2.9 | floating artery cutaway | push + pan left (3.2) | a cut-open vessel model hangs in a lab; softgels flush the plaque out, the wall clears | hard cut |
| 63.6-68.1 | 4.5 | MS → macro chain | **zoom chain (48)** | push onto the chest where the hero ingredient glows inside the ribs → cut (64.3) to the ingredient in a glass jar → it splits open (65.2) → cut (65.9) to macro inside it → cut (66.3) into a glowing molecular lattice → **fast push onto one molecule** (67.9) | hard cut |
| 68.1-71.5 | 3.5 | molecule CU → MS | pull out (-13) | molecules drift; cut (70.1) to him beside a holo screen showing the molecule | hard cut |
| 71.5-78.2 | 6.7 | inside artery | drift + fly (shake reads high: it's a curving fly-through) | gold particles break the plaque, camera travels down the vessel, flies into the lumen; **dissolve** (76.7) to MS: body glows cool white-blue, sparkles | hard cut |
| 78.2-80.6 | 2.4 | inside vessel | fly-through (7.1) | red cells, blue and gold electric arcs | **light-flash transition** (80.6) |
| 80.6-84.8 | 4.2 | MS full figure | static | gym blue; golden energy lines travel out along the limbs | hard cut |
| 84.8-93.9 | 9.1 | CU face / MS group | slow push (2.7, 2.9) | swallows a softgel, orange glow runs down the throat into the chest; then three of him (red, green, blue headbands) in the lab | **zoom-blur transition** |
| 93.9-102.5 | 8.6 | MS → chest-up | static; punch-in jump at about 97.5 | holo heart-rate panel beside him; two softgels appear | **zoom-blur transition** |
| 102.5-110.6 | 8.1 | MCU chest-up | static | two softgels float at his shoulders, one glows (comparison) | hard cut |
| 110.6-115.7 | 5.1 | CU face → CU throat → MS | push + tilt down (5.5) | swallows; hidden cut (112.6) to the throat, camera follows the capsule down; cut (113.8) to MS, green smoke and bulbs burst from his mouth (sight gag) | hard cut |
| 115.7-122.8 | 7.1 | MS / CU gut | static, pull (-6.7) | the ingredient glows in his gut, a red cartoon jagged "pain" burst; cut back to MS | hard cut |
| 123.8-126.5 | 2.7 | CU hand | push (3.1) | **zoom-blur in**; a bony hand holds a softgel trailing golden ribbons; shallow-focus lab | hard cut |
| 126.5-133.0 | 6.5 | MS | static, pull (-3.8) | (not viewed) | **zoom-blur transition** |
| 133.0-142.9 | 9.8 | MS → chest-up | static; punch-in jump cuts at about 135.3, 139.4, 141.8 | holds the product pack; softgels juggle in the air, gold spiral sparkles, cyan holo scan lines and check marks | hard cut |
| 142.9-150.1 | 7.2 | MS seated | slow push (2.6) | **warm sunlit kitchen**: pack on the counter, phone in hand showing a shop page | hard cut |
| 150.1-151.6 | 1.6 | | locked off | (not viewed) | hard cut |
| 151.6-155.6 | 4.0 | MS → ECU | push (3.4) | racks of the ingredient ageing, gold glow, a holo progress line; **dissolve** (154.0) to an ECU of his eyes behind the ingredient | hard cut |
| 156.6-160.7 | 4.1 | MS | static | **zoom-blur in**; white operating room, heart glowing inside the ribs, softgels orbit; glowing family silhouettes fade in behind | end |

## Zoom-in behaviour (Reed's key ask)
- **How often (measured, deep-watch shots):** 14 of 47 shots push in (30% of shots, 29% of runtime); 31% of seconds show zoom above 1.5 %/s (50 of 160); 23 seconds pull out. 0.9 push shots per 10 s, one starting about every 8.8 s. **This is the least zoom-heavy of the set:** the camera mostly holds.
- **How fast:**
  - Slow drift: 6 shots at 2.1-3.4 %/s (median 2.8), constant across the shot, on the character or a prop.
  - Fast: 3 real fly-ins: the artery fly-through (59 %/s), the ingredient-to-molecule chain (48 %/s, accelerating, ending about 2x tighter on one molecule) and the blood fly-through (7 %/s with curving motion). Two follow-moves track something into the body: torso to feet (tilt + push in about 0.4 s) and the capsule down the throat (5.5 %/s). My scale meter agrees on direction and rough size.
- **On what:** always the thing being named: the body part (feet, chest, throat), the inside of the vessel, the ingredient, one molecule. Never the face for emphasis (the one face push, 2.5 %/s, is on the ageing line).
- **How "showing what is said" is mostly done here (not by zoom):**
  1. **The named body part lights up in the shot**: feet and legs glow red, the belly swells orange, the heart glows, vessels draw themselves in, nerves light gold. It appears on or just after the word.
  2. **Props pop in and float beside the character** when they're named, then get swept off.
  3. **Cutting tighter**: hidden jump cuts that reframe the same setup onto the named part (legs at 43.6 and 44.8 s; chest-up at 97.5 and 135-142 s). This reads as a zoom made in the edit.
  4. **Cut or dissolve into a macro cutaway** (artery, molecule): 8 macro passages, about 20% of the runtime *(estimated from the table)*.
- **Edit-made zoom: the zoom-blur transition.** Six times (15.7, 93.9, 102.5, 123.8, 133.0, 156.6 s) the next shot enters through a radial zoom/motion blur lasting about 0.2-0.4 s (one frame fully smeared at 10 fps). This is a CapCut-style zoom transition *(inferred)*, not a camera move. The pushes inside shots look generated (parallax in the artery and molecule shots; the captions stay fixed).
- **Timing:** 57% of cuts land within 0.1 s of a word starting, against 58% for random times, so **cuts are not word-locked**; 17 of 46 fall mid-word. Beat alignment is 43% against 43% random, and there's no music (below), so beats don't matter here. The **in-shot glows** are what's timed to the words *(seen in strips, not measured)*.

## Pacing
- Visual holds about 0.9-9.9 s by detector; real holds about 0.4-6 s once hidden edits count. Median about 2-2.4 s.
- Fastest: the hook (3 cuts in 4.2 s) and the 63-68 s zoom chain (5 edits in 4.5 s). Slowest: the long talk-to-camera stretches on the blue backdrop (6.7-15.7 s, 93.9-110.6 s, 133-143 s), kept alive by props popping in, glows and jump cuts rather than cuts to new places.
- Rhythm: a problem block (0-60 s: body-part close-ups, glows, artery fly-through), a mechanism block (60-80 s: zoom chain, macro), a proof/benefit block (80-125 s: energy glows, swallow and glow), then a warm CTA block (143-160 s).

## Sound
- **Voice only.** One male narrator, wall to wall: median pitch 110 Hz, pitch variability 5.0 semitones (animated, confident storytelling), 3.41 words a second while speaking, 32 pauses over 0.25 s, median pause 0.30 s, longest 0.56 s (no dramatic silences).
- **No music bed:** the drums and bass stems sit near -75 dB (median per 100 ms) and "other" at -59 dB, against the voice at -18 dB. The spectrograms show only voice bleed in the non-vocal stems, with no tonal lines. Deep-watch's 136 BPM "tempo" comes from the syllable rhythm, not music.
- **No whooshes or impacts:** not even on the zoom-blur transitions or the light flash (no hits in the drums or "other" stems at those times).
- Loudness: -14.1 LUFS integrated.

## On-screen text (an editor layer, never in the footage)
- Burned-in word captions, **ALL CAPS**, heavy geometric sans (Montserrat ExtraBold-like *(inferred)*), white with a thin black outline and a soft shadow. **The word being spoken turns yellow (about #F0F000).**
- Pages of 1-3 words (usually 2-3), centred horizontally at about 67% of frame height (over the chest or belly in most framings). No pop or scale animation: pages swap instantly, and the highlight steps word by word. Pages run across cuts.
- Other on-screen text is generated in the picture, not caption-layer: product pack labels, a phone shop page, holo UI panels, a clock face. These are scene props, not editor text.

## Style pattern
- **Character: one recurring cartoon skeleton in a clear glass body shell.** Ivory, slightly stylised adult skeleton (lanky, adult proportions); big glossy cartoon eyes with lids and blue-grey irises; cartoon brown quiffed hair on the skull; **a red sweatband as the identifier** (variants in green and blue for "other people"). A fully transparent, glossy human-silhouette shell (clear, not blue-tinted) shows the bones. Spinal discs glow faint green. Organs are **not shown by default**: they appear only when named (vessels, heart, belly mass, nerves, the softgel's path). He is the same character in every shot he's in.
- **Places:** mostly a **flat saturated-blue studio backdrop** (soft gradient, floor visible); a **sci-fi medical lab** with cyan holo screens; a gym, grey-sofa living room and blue bedroom for the "everyday" moments; **a warm, sunlit kitchen** for the CTA; a white operating theatre for the close. Inside-the-body macros: glossy pink-red vessel tunnels with red cells, yellow plaque, gold particles and cyan electric arcs.
- **Light:** soft, even studio light with gentle rim; glows and auras are the light accents (gold for good, red for bad, orange for bloat, cyan for "science"). The kitchen has a strong warm window sun with god rays.
- **Colour (sampled):** a cool overall look. Brightness median 48 (32-61), contrast 17, saturation median 31 (9-47), warmth median -3 (-18 to +16). Blue backdrop about #4A657E to #325382; MS frames average about #64768A. Macros run warm (#845C4B, warmth +8 to +16); the kitchen CTA is warm (#9E8D79, +10 to +14). The palette is cool blue ground, ivory bones, red and gold accents.
- **Render:** clean, glossy, high-end 3D medical-explainer animation (shallow depth of field in the CUs, sharp everywhere else); the bodies read as toy-like and friendly, never gory.
- **Camera:** mostly locked or a slow drift; motion comes from in-shot effects (glows, props, particles) and from the fly-throughs. Every transition is a hard cut except 6 zoom-blurs, 4 dissolves and 1 light flash.

## Lane match
- **Nearest: skeleton-xray**, partly. It matches the world: "clean sci-fi medical 3D", "a clean blue gradient backdrop" or "a real setting", soft rim light, health subject, the inside shown in plain visual terms (glows, a knot loosening).
- **It doesn't match the x-ray body:** the lane's character is "a translucent glowing anatomical human body … visible internal organs … glowing red and orange through a blue-tinted translucent skin outline". Here the shell is **clear glass, not blue-tinted**, organs show **only when named**, and the face is the **Bare-Bones skeleton's** (adult ivory bones, big expressive cartoon eyes), plus cartoon hair and an accessory. So it's a hybrid: Bare-Bones character + clear glass shell + the X-Ray lane's world. It isn't the Mascot (adult proportions, not chibi).
- Guide fit: matches R1 (one locked character) and "the visual is the proof of the line". It differs from the default's warm photoreal places (here cool blue studio and lab) and from "one move and one camera move per shot with a motion transition on every change": most changes are hard cuts.

## Why it works (for the viewer, look-wise)
- The first second is a body part in trouble, not a face: instant "that's me" recognition.
- The glass shell makes every claim visible: whatever the voice names lights up inside the body at that moment, so it reads with the sound off.
- The fly-throughs and the zoom chain are the "wow" beats. They arrive when the explanation goes inside (problem mechanism, then fix mechanism), and they pay off the curiosity of what's going on in there.
- One friendly, identifiable character (the red sweatband) carries a 2.7-minute ad; the blue backdrop keeps attention on the body.
- The shift from cool blue to the warm sunlit kitchen marks the close.

## How the director recreates this look from any script
- Lock one character sheet: an ivory cartoon skeleton with big expressive eyes inside a **clear glass body shell**, plus one identifying accessory and hair. No organs in the base sheet.
- For each line, show what it names **on the body**: a glow on that part (red = problem, orange = bloat, gold = fix), or the organ or vessel drawing itself in. Or cut to a tighter framing of that part.
- When the script explains a mechanism, go **inside**: a macro fly-through (a tunnel forward, 7-60 %/s), or a zoom chain (body → the thing → inside it → one particle, 4-5 steps over about 4-5 s).
- Mostly static or slow-drift camera (2-3.5 %/s). Hard cuts; save the zoom-blur transition for re-entries to the talk-to-camera setup (about one every 25 s here).
- Home base: a flat blue backdrop or a sci-fi lab; everyday places only when the line is about daily life; switch to a warm, sunlit real room for the CTA.
- Editor: ALL CAPS 2-3-word captions with the spoken word in yellow, at about 67% height; voice only, no music, no SFX (optional, not seen here).
- **Don't copy:** the product, pack, phone shop page, the ingredient-in-a-jar and molecule shots *as specific images* (the device carries over, the object doesn't); the red-sweatband exact look (pick a new identifier per brand); the 9-10 s static talk holds (they work here only because props and glows keep moving).
