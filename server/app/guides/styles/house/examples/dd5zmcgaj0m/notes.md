# Study: Dd5zmcgAj0M (House style reference reel)

Look and feel only: no script, no words, no product, no offer.

## 1. Source
- File: `.context/drive/house/Dd5zmcgAj0M.mp4` (720x1280, 30 fps as delivered; the original on next's `docs/references/nateassets/Dd5zmcgAj0M/` was 1080x1920 60 fps). Instagram reel by the creator behind the house references.
- Studied 2026-11-03 by study-house with the deep-watch kit (`watch/house/Dd5zmcgAj0M/`): hook strip, every shot strip (53 shots, 56 strip images), all 3 spectrograms, `audio.json`, word timings, plus ffmpeg colour samples (shadow/highlight split at 9 times) and `ebur128`/`silencedetect`. The older BREAKDOWN.md on next was used only to cross-check.
- I can't play sound. Everything under Sound comes from the separated stems, the spectrograms, loudness per 100 ms, the voice pitch track and word timing.

## 2. Length and measured numbers
| Measure | Value |
|---|---|
| Duration | 56.03 s (3D animation 0-54.50 s, live-action tag 54.50-56.03 s) |
| Shots (kit's cut detector) | 53 (the older hand-checked breakdown counts 64, because it splits the montage's 0.1 s jump cuts finer) |
| Cuts per 10 s | 9.5 |
| Shortest / median / mean / longest | 0.13 s / 0.43 s / 1.06 s / 9.93 s |
| Shots under 1 s | 41 of 53 |
| Words spoken | 143; 2.86 words/s while speaking; the opening 13.9 s carries 67 words (4.8 words/s of runtime) |
| Music tempo (detected) | 143.6 bpm (could be a 72 bpm groove read double; *inferred*) |
| Loudness | -14.1 LUFS integrated, loudness range 3.6 LU; no silence anywhere (silencedetect -35 dB / 0.4 s) |

## 3. The hook (first 2 s)
- 0.00-0.13: a plain closed bedroom door, centred, eye level, filling the frame. The hook title is already on screen.
- 0.13-1.23: the door bursts open in a smeared morph (no clean door swing; the generator's blur carries it) and the angry parent strides straight at the lens, wallet raised, into a medium close-up. Static camera; all movement is the actor coming at us. Her face is a cartoon-big scowl: slammed brows, bared teeth, wide eyes.
- 1.23-1.93: hard cut to a wide over her shoulder (her hair and arm frame the right edge) with a fast 30 %/s push-in toward the son at his desk, deep in a room walled with stacked stock. He spins round in shock.
- So in 2 s: a door, a charge at the camera, a reverse wide that shows the whole situation (who, where, how much stuff), and three spoken words per second over it.

## 4. Shot by shot (grouped by segment)
| Segment | Time | Shots | Shot lengths | What the camera and picture do |
|---|---|---|---|---|
| Confrontation (day, bedroom-stockroom) | 0.00-13.90 | 1-13 | 0.13-3.67 s, median 0.70 s | Eye-level singles and two-shots. Static frames where the actors do the moving (lunges, wallet slam, a chair spin with legs flying), cut every line or half-line. Two whip-pans (shots 6-7, pan 5-14 %/s with full motion-blur frames) sweep across the stock as an insert. One snap pull-back from an extreme close-up of the parent's face (shot 11, zoom -11 %/s). One slow push on a profile two-shot (shot 13, 7 %/s) that ends in a radial zoom-blur into the next segment. |
| Night grind montage | 13.90-19.80 | 14-27 | 0.20-1.10 s, median 0.38 s | One locked-off frontal composition repeated: the son centred at a desk, stock behind, a hoodie or mailer on the desk, a big clock in the top tenth of the frame. Plus two over-the-keyboard laptop inserts. Time jumps are jump cuts and generator morph frames (ghosted double images, garment colour swapping mid-shot). The light flips between warm interior and moonlit blue with phone glow on his face. Wordless. |
| Doubt beat | 19.80-27.33 | 28-29 | 6.57 s, then 0.97 s | The longest still moment: locked-off frontal on him behind a laptop, lit only by the screen's cold blue; the parent appears in the warm-lit doorway behind and watches, then leaves. Then a crash zoom into his eye (zoom 3.5 %/s rising to a full-frame iris) and a cut to black (about 0.2 s). |
| Turn and reveal | 27.33-42.37 | 30-32 | 9.93 s, 2.60 s, 2.50 s | One 9.9 s generated shot that moves through four set-ups by morphing: a low close-up of him over his phone with order notifications floating in the air between phone and face, a follow as he runs to the door, a two-shot with him holding the phone out to her, then the room seen empty and filling with stock (a time-lapse inside the shot), then packing at the counter. Shots 31-32 are two-shots at the packing counter with fast character action; shot 32 cuts in to a frontal close-up of his face for one reaction. |
| Packing montage | 42.37-47.93 | 33-46 | 0.20-0.83 s, median 0.35 s | Same idea as the night montage: one frontal two-shot at the counter, locked off, held while the background swaps (day with palm trees and blue sky, brick wall, night with a starry sky, back to the stockroom). Morph and motion-blur frames between them. |
| Resolution | 47.93-54.50 | 47-48 | 5.50 s, 1.07 s | A static frontal two-shot behind a wall of shipping boxes, held for the payoff exchange and a shared smile. Then a push from behind their shoulders to a doorway stacked floor to ceiling with parcels and a courier's face peeking over the top: a visual topper with no words. |
| Live-action tag | 54.50-56.03 | 49-53 | 0.20-0.57 s | Real handheld phone footage of the creator: a warehouse aisle, a night high-rise room with stock, a car door in a garage, a purple-lit car interior, a room full of stock. Cut on a bass hit at 54.5 s. |

## 5. Pacing
- 9.5 cuts per 10 s overall, but it moves in waves: talk scenes cut on lines (median 0.7 s), montages cut much faster (median 0.35-0.38 s), and three long holds give the breath: 6.6 s (doubt), 9.9 s (the turn, one continuous generated move) and 5.5 s (the payoff).
- Cuts don't land on the beat: 17 of 52 cuts sit within 80 ms of a detected beat, which is what chance gives at this tempo (about 38 %). Dialogue cuts follow the words; montage cuts follow the action and the clock.
- Speech covers the confrontation densely, then stops for 6.1 s (13.6-19.7 s) and 5.5 s (40.7-46.2 s) where the music carries the montages.

## 6. Sound (from stems and spectrograms)
- Music bed under the whole video; no silence. The bass stem shows a constant low drone from the first frame to the last.
- Under the confrontation the bed is held far down: vocals median -17.9 dB against drums -47.6 dB and other -42 dB, so the voices sit about 25 dB above the music.
- At the montage (about 13.9 s) the drums come in hard (median -21 dB) and the bass thickens: the montage is music-led. The packing montage is the loudest music stretch (drums -26, bass -26).
- 24-37 s: the "other" stem shows rows of short, bright, evenly spaced tones stacked on a grid, which read as a burst of repeated notification chimes as the orders arrive *(inferred: notification sounds)*.
- Hits line up with physical action: the door burst (1.1-1.5 s), the wallet slam (2.3 s), whooshes at the whip-pans (4.3-4.9 s), the chair spin, and a bass thump at the cut to the live tag (54.5 s).
- Voice: median pitch 239 Hz, range about 20 semitones (p10 -11.9 to p90 +8.4), variability 6.9 semitones: shouted, very animated. Median pause 0.48 s; 19 pauses over 250 ms.
- Mastered loud and flat: -14.1 LUFS, loudness range 3.6 LU.

## 7. On-screen text (added in editing, for the editor)
- Hook title, 0-1.2 s: one line in white heavy rounded sans, all caps, with a skull emoji, centred at about half height, thin dark shadow. It names the doubter and the payback in a few words.
- Word captions: one word at a time, white bold rounded sans, lower case (numbers as figures with a currency sign), soft dark drop shadow rather than a heavy outline, small (roughly 5 % of frame height), sitting at about 60-65 % of the frame height. Each word changes with a quick blur-smear, so the caption never sits still.
- Night-montage clock: big cream bold condensed numerals with an orange outer glow at the top of the frame, ticking through late-night times. The digits morph and sometimes a second clock appears mid-frame, which suggests the clock was part of the generated clips rather than an editor overlay *(inferred)*.
- In the turn shot, counting numbers appear as plain word captions as the room fills.

## 8. The style pattern (look)
- Render: stylised 3D feature-animation CG with big, glossy, highly elastic faces (huge eyes, heavy brows, wide mouths), realistic cloth and props. Adult and teen bodies are proportioned like adults and teens; faces are pushed cartoon-big at the emotional peaks (shot 11's face fills the frame, shot 29's iris fills the frame).
- Cast and outfits identical across all 48 animated shots: the son in a backwards navy cap, white tee with a small navy chest logo, thin silver chain, black trousers, white sneakers; the parent in a beige blouse with rolled sleeves, navy trousers and a chin-length brown bob. No outfit changes at all, even across the time-lapse.
- Places: a real-world suburban home (bedroom turned stockroom with wire shelves, cardboard boxes, a cork board, a desk, a hallway door), shot as it would look in life. Props are close to photoreal; the stock inserts in shots 6-7 look almost like phone footage.
- Light: day scenes are soft, warm, low-contrast interior light (contrast 16-20 of 100; sampled shadows are warm-neutral, e.g. #1c1310, highlights warm, e.g. #bd9882). The warm/cool contrast comes scene by scene, not inside one frame: night scenes go fully blue (avg #161d28, highlights #68809b) with a phone or laptop glow on the face, and the warm doorway behind (shot 28) is the one warm patch.
- Colour by segment (kit averages): confrontation #5f4c43-#765a4f, brightness 33-41, saturation 25-33, warmth +7 to +14; night shots #1f242c-#2c2b30, saturation 42-66, warmth -2 to -5; packing montage alternates #63514c (warm) with #171b30-#252235 (warmth -8 to -12); live tag purple #441a41-#42315a.
- Depth of field: moderate. Backgrounds stay readable in wides and two-shots (you can count the stacks); only the close-ups (shots 13, 32) go properly soft.
- Camera: mostly static at eye level, with the actors doing the moving; camera moves are punctuation (one crash push, one snap pull-back, two whip-pans, one crash zoom to the eye, a push to the final gag). The "handheld shake" the kit reports on shots 2, 7, 11, 30-32 is motion blur and morph frames from fast action and AI scene changes, not a handheld camera: the strips show steady frames between the smears.
- Screens: a phone held in a hand fills most of the frame once (shot 9, readable big number); two over-the-keyboard laptop inserts (shots 16-17) show listings full width with the fingers at the bottom; notifications float as 3D cards in the air in front of his face (shot 30). The phone is otherwise always in hand and often lights the face.
- Transitions: hard cuts in talk scenes; whip-pan blur, radial zoom-blur, morph dissolves inside one generated shot, a crash zoom to black at the midpoint, and AI morph jump-cuts in the montages. No white flash.

## 9. Why it works (for a viewer)
- 0-2 s: a door and a charge straight at the lens, then the reverse wide that shows the whole stockroom: the situation is clear before the first sentence ends.
- The talk scene keeps the eye busy with physical comedy (lunges, a wallet slam, a chair spin with flailing legs) and one face blown up to fill the frame.
- The montage switches to music and one repeated frame, so the time passing reads at a glance (the clock, the light going blue).
- The one long, quiet, blue hold lets the low point land before the crash zoom and the black frame turn the story.
- The same frontal two-shot across changing backgrounds makes the "working together for weeks" idea readable with no words.
- The final parcel-wall gag tops the payoff visually, and the real-life tag ties the cartoon to a real person.

## 10. How the director recreates this look from a new script
- Keep: one consistent 3D cast in one fixed outfit each; real-world rooms dressed with dense, real props; eye-level static frames where the actors carry the motion; cut on lines in talk scenes; faces pushed cartoon-big at peaks; montages as one repeated locked-off frame with the time or place changing behind; a long quiet hold before the turn; music low under talk and up in montages.
- Use camera moves sparingly as punctuation: one crash push or snap zoom per scene at most, whip-pans as inserts or transitions.
- Don't copy: the doubter-parent premise, the stockroom and its merchandise, the live-action creator tag (that belongs to this creator's channel), the burned-in captions (rule 32: captions are the editor's job), the AI morph artefacts (they are the generator's, not a choice; a clean cut does the same job).

## Format notes (dialogue skit), from this video
- Shape: cold open mid-conflict (0-14 s, dense lines) → wordless music montage (6 s) → quiet low point (7 s) → turn (10 s continuous) → wordless montage (5.5 s) → short payoff exchange with a visual topper (6.5 s) → 1.5 s creator tag.
- About half the runtime is wordless and carried by music; the lines cluster in the open and the turn.
