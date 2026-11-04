# Notes: zackd-1793684261476 (ancient water alarm clock)

Look and feel only: no script text, no product, no offer. *(inferred)* marks anything worked out rather than seen or measured.

## Source
- File: `zackd-1793684261476.mp4` in Reed's Drive folder "Zack D" (video not in git). An original Zack D. Films video: "ZACK D FILMS" is moulded into the pots and carved into the bed's headboard.
- Studied 3 Nov 2026 by study-zack-d with the study kit (cuts, transcript) and the lead's deep-watch kit (output kept locally, not in git: per-second camera flow, 5 fps hook strip, 2.5 fps strips of the whole video, demucs stems, spectrograms, voice pitch and timing), plus 20 fps strips I made at five transitions (4.3–5.0, 6.3–7.0, 9.9–10.6, 14.3–15.0, 27.9–28.6 s).
- I can't play sound. I "hear" it through the separated stems, spectrograms, loudness per 100 ms, pitch and word timing.

## Length
30.43 s, 360x638, 30 fps. **One shot: no hard cut anywhere** (deep-watch: 1 shot; ffmpeg scdet at threshold 6 found nothing). 90 words.

## The hook (0–2 s)
- Seen: a white-bearded old man in a Greek tunic, chest-up, centred, holding a small green pot and pouring water into a larger cut-away green jar below him; dark brick wall behind, warm side light.
- Framing: medium close, slightly high angle, the jar's open rim in the lower half.
- What moves: the water pours out (0.4 s) and **the camera tilts down with it at about 30% of frame height a second** while pushing in (deep-watch s0: tilt −30.2%/s, zoom +5.4%/s; s1: zoom +14.8%/s). By 1.6 s the camera is inside the jar's cutaway following the stream; by 2.2 s a glowing red ring marks a tiny hole in the jar's base. The voice starts on frame 1 (first word at 0.00 s), mid-action: no title, no setup, no face to camera.

## Beat by beat (one continuous camera)
Times from the strips; "fast move" times from the 20 fps strips.

| Time (s) | Shot size | Camera | What happens | Into the next |
|---|---|---|---|---|
| 0.0–2.8 | medium close → macro | tilt down following the pour, push in | water pours into the cut-away jar; red ring marks the hole | camera keeps pushing through the hole (blur) |
| 2.8–4.45 | macro | slow push, slight drift | a cyan holographic X-ray of the valve inside the hole, drip falls | fast pull-back, 0.25 s (4.45–4.70) |
| 4.7–6.45 | medium (whole jar) | slow push / arc | the jar shown as a cutaway: U-pipe inside, slow drip filling | fast lateral move, 0.3 s (6.45–6.75), across the same room |
| 6.75–10.05 | medium | slow pan and tilt up to the window, back down | the old man gets into bed and sleeps; the moon crosses the window (time passing), night to day | fast lateral move back, 0.3 s (10.05–10.35) |
| 10.35–14.45 | medium → macro | steady push in | the jar now full; the inner pipe glows red, then the camera is inside the pipe as glowing blue arrows show the water rushing up | fast tilt down following the water down the pipe, 0.4 s (14.45–14.85) |
| 14.85–17.2 | medium close | tilt down following the water | as the camera arrives, a cutaway opens in the solid pot below (14.95 s) and water pours in; red ring marks its inlet | pull out |
| 17.2–18.6 | wide | pull out, then push back in | the whole four-pot tower on its stand: the one wide establishing frame | push into the bottom pot's cutaway |
| 18.8–24.0 | close → macro | push in, then a track along the spout | inside the sealed pot, white swirl lines and blue arrows show air being pushed out; the camera follows the air along the spout to a bowl | push on the spout |
| 24.0–25.6 | macro | slow push | red neon squiggle lines appear by the spout (a drawn "sound" sign) | pull back and pan |
| 25.6–28.0 | medium | pull back, pan to the bed | red sound rings reach the sleeping man; he jolts awake, sits up | the tower glows cyan |
| 28.0–28.6 | medium | hold | the pot tower glows cyan and turns into a modern black alarm clock, which tumbles onto a stone pedestal reading 6:00 | hold |
| 28.6–30.43 | medium | small pan | the man looks at the clock, then flops back to sleep (the closing gag); the voice ends at 29.66 s, 0.77 s of picture after it | end |

## Pacing
- Hard cuts: 0. Cuts per 10 s: 0.
- Camera beats (a new subject or place framed): 12 in 30 s, one every 2.5 s on average; beats run **1.6–5.2 s** (median 2.4 s; per-beat optical flow in the guide's pacing).
- Fast in-world moves that link beats: 4 (4.45, 6.45, 10.05, 14.4 s), each **0.25–0.4 s**, plus one object morph (28.0 s) and two push-throughs (2.8 s into the hole, 12.8 s into the pipe).
- The camera is moving in 24 of 30 seconds (80%, over 2% of frame a second); near still in only 5 seconds. Median move speed 6.6% of frame a second; push-ins 13 s, pull-outs 6 s, tilts over 3%/s in 10 s, pans over 3%/s in 9 s. Fastest one-second averages: push in 40%/s (s12, into the pipe), tilt 30%/s (s0, following the pour), pan 18%/s (s26).
- Something visibly changes every second or less (a graphic, a glow, the subject moving), even inside the long moves.

## Sound
- Voice: one narrator over everything, starting at 0.00 s and ending 0.77 s before the end. 3.06 words a second while speaking; 7 pauses over 0.25 s, median pause 0.40 s, longest 0.50 s. The phrases (8 between pauses) run 1.2–7.3 s, median 2.6 s. Median pitch 157 Hz; p10–p90 range −7.3 to +9.5 semitones; variability 6.4 semitones (a moving, storytelling melody rather than flat) *(how "animated" that sounds is inferred from the numbers)*.
- Music: a continuous low tonal bed in the "other" stem from 0.1 s to the last second, no drums, almost no bass stem (bass −60 dB, drums −59 dB median). Detected tempo 92 BPM. It sits about 17 dB under the voice (voice −14.6 dB, bed −32 dB while speaking) and does not rise in the pauses (−32 dB in gaps): no ducking.
- Effects: noise bursts in the drums stem at 9–9.5 s and 15.7 s (water rushes *(inferred)*); a single sustained high tone 24.2–26.5 s, exactly while the spout and red squiggles are on screen (the whistle).
- Loudness: −10.5 LUFS integrated, loudness range 1.5 LU (very loud and very even). No silence anywhere (none at −30 dB for 0.15 s).

## On-screen text
- Burned-in captions: white sans, semi-bold, sentence case, a thin dark drop shadow, centred at about 77% of frame height, 1–4 words at a time, changing with the voice (a new chunk every 0.2–1 s). Our rule 32: this is an editor's caption style, never generated into a clip.
- In-world text only as props: "ZACK D FILMS" moulded into the pots and headboard; the clock reads 6:00.

## The format pattern (how the information is presented; no words)
1. Opens mid-action on the first frame: someone already doing the thing.
2. A causal chain told in the order it physically happens: cause → so → after a while → then → since → which → result. Each clause gets the camera on the exact part that's doing it at that moment.
3. Time passing is shown, not cut: the moon crosses the window.
4. The payoff: the old device becomes its modern equivalent (a morph), then a small comic button (he goes back to sleep).
5. No sign-off, no title card, no end card.

## The style pattern (look and camera)
- Semi-realistic 3D CG (game-engine look): realistic proportions and skin, real materials (brick, linen, ceramic), physically lit water. Not cartoon, not Pixar.
- One set, one room, lit warm and low key (average colour #45402c; brightness median 71/255; saturation low, 13 on ffmpeg's scale). Moody: one warm key from above-left, deep shadows.
- Cutaways open as the camera arrives (the solid pot gains a cut-away window at 14.95 s). The explained object is cut away (the front half missing) so the camera can see inside; the cut edge is a bright lime green rim.
- Explanation graphics are in the world, glowing: red rings for "here", cyan hologram X-rays, blue glowing flow arrows, white motion swirls, a red-glowing part, red neon sound squiggles.
- The camera never stops; it follows the moving thing (the water, then the air) through the mechanism, and jumps between places in the same set with sub-half-second moves instead of cuts.

## Why it works
- Frame 1 is already in motion and the voice is already talking: nothing to skip.
- The camera literally follows the cause to its effect, so the viewer's eye never has to search; the voice says "this part" exactly when the camera arrives there.
- The cutaway plus glowing marks make an invisible mechanism readable at phone size.
- The morph to the alarm clock gives the "aha" a picture; the gag gives it a laugh.

## How the director recreates this from a new script
- Find the physical chain in the script and give each clause one camera beat on the part doing the work; link beats with following moves and short fast moves in one set, not cuts.
- Open on the action already under way; no setup frame.
- Use cutaways and glowing marks (red = here or the key part, cyan/blue = flow or mechanism working) for anything inside.
- End on a transformation or reveal, and a small human reaction.
- Don't copy: the Greek setting, the pots, the alarm-clock morph, the "ZACK D FILMS" lettering.
