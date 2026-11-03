name: UGC
order: 11
on: no
image_model: auto
video_model: seedance-2.0
blurb: A real person talks straight into a phone in their own room, cut with fast literal B-roll of what they're saying.

<!-- New style, 3 Nov 2026, from Reed's Drive folder "UGC (B-roll)" (4 reference ads, 86–215 s), each watched with the deep-watch kit; the per-video notes are in examples/<video>/notes.md (named notes.md so they are evidence for people, not loaded into every prompt). Reed's note on the folder: "Probably make the person talking with heygen avatar 4 OR omni (cheapest option) maybe even MiniMax… B-roll with cheap video model to create captivating backgrounds." Reed, 3 Nov, on the talker's model: P-video is preferred, but for UGC "we can revisit this … since voice inflections are very important". The references use three treatments: a straight cutaway (talker full frame, then B-roll full frame: what the app makes today), the talker cut out and laid over full-frame B-roll (the keyed host layer), and a mix of the two. Reed's answers, 3 Nov (REED-DECISIONS-2 U1–U5, F7, captions): named "UGC"; runs in the Presenter format; straight cutaways now, talker over B-roll once the keyed host layer ships (server/app/host_layer.py); the talker made with P-video lip-synced to the video's own voice-over, tested first and revisited if the voice inflection isn't human enough; people in the B-roll as phone-real as the talker; no music by default; generated selfie testimonials allowed ("Yes, do not ever regulate me."); short B-roll pictures are separate generated clips spliced in the edit ("this will likely have to be done by generating several clips and splicing them together"); captions come in post production ("dont worry about captions"), so caption looks stay only in the notes. order 11 leaves 10 for Dr. Pickle. -->

## sheet_look
A real person photographed on a phone, not a model shoot: natural skin with visible pores, fine lines, small blemishes and uneven tone; real, slightly imperfect hair. The body and face follow the character's age: an adult has an adult's height, build and face. One fixed everyday outfit (or a work uniform when the role calls for it), plain and real-world, identical in every view, with one detail that reads at a glance (a bracelet, a watch, scrubs, a cardigan). Soft, even daylight from a window, no studio light, no retouching.

## place_look
A real, lived-in room photographed on a phone in daylight: specific clutter and everyday objects that say whose room it is (a workshop, a clinic, a home office, a kitchen), all in focus, no shallow cinematic blur. Soft natural window light, slightly warm, mid-contrast, no coloured studio light, no grading.

## still_look
The UGC look, unless the brand block says otherwise: "A vertical phone video frame, photorealistic and unpolished: real people with natural skin texture in a real, lived-in place, lit by soft window daylight or plain outdoor sun. Faces and builds come from the character sheets, and outfits too unless this video gives its own. When the main speaker is in the shot, they face the camera at eye level, chest-up and centred, looking straight into the lens, the room behind them in focus. Other shots look like everyday phone footage of a moment, a close-up of hands and objects, or, when the line explains what happens inside the body, a glossy translucent 3D medical render on a soft studio background. No cinematic lighting, no shallow-focus film look, no captions."

## clip_style
Realistic vertical phone footage: the speaker locked off at eye level talking straight into the lens in natural window light; cutaways with gentle handheld drift or a slow push-in

## fit_look
a realistic, everyday phone-camera look with natural skin texture

## The videos
One ordinary-looking person talks straight into a phone camera in a real room, as if they filmed it themselves; the edit cuts away to a fast run of literal B-roll that shows what they're saying (or, when the video lays the talker over the B-roll, keeps them on screen in a bottom corner). The talker carries the trust; the B-roll carries the attention.
- It runs in the Presenter format: the talker is the presenter, and their voice-over is the video's one voice.
- Straight cutaways now (talker full frame, then B-roll full frame); the talker laid over the B-roll once the keyed host layer ships.

## Stills
- Two kinds of shot. **Talker shots:** the main speaker, from their sheet, chest-up (waist-up to selfie-close), centred, eye level, eyes straight into the lens, in their own room, which is in focus behind them. **B-roll shots:** one literal picture of what the line says at that moment, with no talker in it.
- The talker's room says who they are: a clinic for someone in scrubs, a workshop with shelves of jars, a home studio, a kitchen. Real clutter, window daylight, nothing staged.
- B-roll is one of four kinds, mixed freely: everyday people filmed like a phone video and as real as the talker, with natural skin, real rooms and phone light, never a polished or rendered look (the problem and the "after": tired on a sofa, a hand on a belly, smiling in the sun); a glossy, translucent 3D render of what happens inside the body, on a soft grey or dark studio background, when the line explains a mechanism; objects and ingredients in natural settings (a wooden table, a garden, stone), often a hand holding the product up; proof-style footage (a lab bench, a microscope view, another person's selfie testimonial, generated like the talker).
- Each B-roll picture keeps its own light and colour: phone footage natural, renders saturated and glossy. Don't grade them to match each other or the talker.
- No captions, titles or overlay text in any picture (rule 32). A product label or a phone screen that matters is in the picture and its words are stated exactly.

## Clips
- The talker is made with P-video, lip-synced to the video's own voice-over, so the voice keeps its real inflection.
- A talker shot is one continuous take: the camera locked off or nearly (no push-ins, no pans on the talker), the speaker talking into the lens with small natural head movement, blinks and hand gestures at the bottom of the frame.
- B-roll shots move gently: a slow push-in, a still frame with movement inside it, or a phone's handheld drift. A list of things gets one short shot per item. Short B-roll pictures (under the video model's shortest clip) are separate generated clips, spliced together in the edit.
- The talker's voice runs across the B-roll: it never stops for a cutaway.

## Breakdown
- Cut to B-roll on the phrase that names something showable; come back to the talker for opinions, turns and the close. The talker is in every talker shot and in none of the B-roll.
- One talker for the whole video, in one outfit and one room.

## pacing
- Quick cuts (Reed, 3 Nov: talking-head and UGC styles keep quick cuts). Measured over the four reference ads (86–215 s):
- Cuts per 10 s: 2.4–5.0 (3 of 4 at 4.0–5.0; the 215 s one at 2.4). Median shot: 1.9–3.0 s (4 of 4). Shortest shot: 0.2–0.8 s.
- Hook: the first cut comes at 1.4–4.3 s (4 of 4); the voice starts at 0.0 s (4 of 4).
- Talker shots: median 2.9–6.3 s, range 1.1–21 s (the 2 straight-cutaway ads). The longest hold in every ad is the talker (4.8–21 s, 4 of 4), on an opinion or the close.
- B-roll shots: median 1.8–2.9 s, range 0.2–6.9 s (4 of 4). Shortest in lists (0.6–1.1 s a picture); longest on 3D mechanism renders (4–7 s).
- Alternation in a straight cutaway: the talker comes back after a B-roll run of 3–6 s (median, 1–2 shots); an explainer run can go 20–26 s (8–10 shots) without the face (2 of 2). A talker block is one shot (2 of 2). The talker is on screen 40–45% of the time (2 of 2).
- Arc: a fast hook, the face on screen within 0–7 s (4 of 4), B-roll runs growing in the middle, often a long talker hold to close (2 of 4: 11 s and 21 s).

## must keep
- One main talker who looks straight into the lens in every talker shot: no profile, no off-camera eyeline (4 of 4).
- Phone-shot realism in the talker: vertical, a real room with real clutter, natural window light, the background in focus, everyday clothes or a role uniform (4 of 4).
- The talker's camera doesn't move: shake 0.1–1.2 on talker shots in 3 ads and 1.9 in the selfie-close one, against up to 41 on handheld B-roll; no push-ins on the talker (4 of 4). All the movement lives in the B-roll.
- A room that says who the talker is (3 of 3 that show the room; the fourth removes it).
- Literal B-roll, one picture per phrase, a new picture every 0.6–3 s in list sections (4 of 4).
- B-roll mixes looks on purpose, with no shared grade: B-roll saturation 7–74 and warmth −16 to +34 across the four (4 of 4).
- Voice from 0.0 s and almost no silence: voice on 88–96% of the time, no pause longer than 0.44–0.56 s (4 of 4).
- 3.3–3.5 words a second while talking (4 of 4), whatever the energy.

## safe to vary
- How talker and B-roll combine: straight cutaway (2 of 4), the talker cut out over full-frame B-roll for the whole video (1 of 4), or a mix (1 of 4).
- The talker's age, sex and look (a man in his fifties–sixties, a woman in her twenties in scrubs, a man in his thirties, a man in his fifties).
- Framing: waist-up to selfie-close with the head touching the top edge.
- Energy: calm and confiding (pitch variability 3.6 semitones) to lively and urgent (4.9–5.8, with rising peaks).
- Music: none by default (2 of 4 have none); a quiet bed 21–24 dB under the voice (2 of 4) when the script or editor asks for one.
- Editor transitions: none (2 of 4), or a flash or whip on about every third cut (1 of 4).
- Hook device: a metaphor picture behind the talker, split screens of the problem, a second person over the talker, product footage behind the talker (one each).
- Extras: generated selfie-testimonial clips of other people near the end (2 of 4), picture-in-picture photos over the talker (1 of 4), designed offer cards in the last third (1 of 4).

## combines with
- 3D medical renders as B-roll: glossy, translucent inside-the-body footage in 4 of 4 (the longest B-roll holds). The talker frames it as real.
- Skeleton: one B-roll shot in one ad is a glossy 3D skeleton in a clear body, used as UGC B-roll.
- Testimonial selfies: other people talking to their own phones, each in their own room and light (2 of 4).
- Format: Presenter. Any script with one main speaker talking to the viewer (a testimonial, an expert explaining, problem to mechanism to fix, an offer) suits it.

## camera
- The talker's camera holds: locked off or nearly, no push-ins, no pans (4 of 4). All the camera movement is in the B-roll.
- Talker: centred, eye level, eyes in the upper third; a wide phone lens, with a little stretch on the face at selfie distance.
- Talker over B-roll (when the video uses it): the talker cut out chest-up in a bottom corner, 40–55% of the frame's width, head top at about 55–62% of the height; their light doesn't match the background, and that's accepted.
- B-roll: slow push-ins (1.5–19% of the frame a second, median about 4%), still frames with movement inside, or handheld phone drift.

## Light and colour
- Talker: soft window daylight from the front or front-side, even on the face, no hard shadows; the room behind a little brighter. Measured talker frames: brightness 40–51 of 100, saturation 27–30, warmth +7 to +12, contrast 22–27; averages #745853, #73675e, #806c6d; faces #b38371 to #c79a87.
- B-roll keeps its source colour; renders are saturated (salmon and amber organs, cyan or green glows, saturation 40–66).

## Edit devices
- Optional, all added in the edit: picture-in-picture photos over the talker's chest for a named object; designed offer cards (the product, arrows or a seal) in the last third; split screens of the problem in the hook; a white or coloured flash, a whip or zoom blur, or a light-leak flash as a transition.

## Sound and delivery
- One close, clean voice from the first frame to the last.
- Pitch variability 3.6–5.8 semitones: warm and calm to lively; urgency shows as rising peaks.
- No music by default. When asked for: a quiet bed 21–24 dB under the voice that can change as the video turns to the offer. Effects only on editor transitions (a whoosh on a flash, one low impact).

## banned
Pixar-style → realistic
animated-feature → realistic
stylised 3D → realistic

## fixes
refused: Soften it (the free fix rewords the picture, never the lines), then Make another.
face: Make another first. If it drifts again, Change this… "keep the face exactly as the sheet, natural skin texture, no smoothing".
outfit: Change this… naming the outfit's key pieces in the shot, this video's when it gives one, else the sheet's.
product: Change this… "the real product from its image, held up to the camera, the label facing the lens and readable".

## sample
A friendly man in his forties with short greying hair and stubble, in a plain navy long-sleeve top, at his kitchen table in window light, looking into the camera.
