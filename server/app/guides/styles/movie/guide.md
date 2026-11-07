name: Movie
order: 12
on: yes
image_model: auto
video_model: gemini-omni-1.2
blurb: Photoreal short TV drama: real people in real places, close shallow-focus singles, light from the scene, location sound and no score.
card: Photoreal TV drama
broll: Real-life inserts
formats: dialogue
formats_why: its people say the script's lines on camera in Omni's own voices, and a narration or a presenter would add a voice track of ours

<!-- New style, 7 Nov 2026, from the Movie spec (.context/team/specs/movie/spec.md, study-movie, 3 Nov) and its three studies of the videos in Reed's "Movie" Drive folder (movie-a32869, movie-0eab01, movie-35aa3b; 378–551 s each, deep-watch kit). Reed on the folder: "For Movie style ads (the new one in the folder), these are literally short dramas, these will likely work best with Omni." Reed, 7 Nov: "Movie, up to 30 s: make it work on the site". -->
<!-- Decisions applied (Reed's, and MAIN's defaults for the spec's open questions): one id, `movie` (a style; it runs in the Dialogue format, whose story engine carries a scripted drama, and this guide's pacing and sound win over that format's house-shorts habits); made on Gemini Omni 1.2 (#1394: "Omni is more for the realistic stuff"), every clip, with Omni's own voices from the quoted lines (Omni takes no audio); no score, music is added in post (Reed, 7 Nov, #1435); the script's words are final and its ending is its own last words, nothing added; captions, time cards and end cards are the editor's overlays (rule 32), never in a clip; the mechanism insert is kept; before and after is an after look of the same person. Starts on (MAIN, 7 Nov: "make it work on the site"). The evidence is in the spec and the studies; none of it is sent to the model. -->

## sheet_look
A photoreal person photographed like a still from a modern TV drama, not a model shoot: natural, unretouched skin with pores, fine lines, slight shine and uneven tone; real hair with flyaways. The body and face follow the character's age and build exactly: an adult has an adult's height, build and face; a heavy character is genuinely heavy, a fit one genuinely fit. One fixed, everyday, specific outfit that says who they are (a hoodie, a satin dress, a leather vest, a work polo), identical in every view, with one detail that reads at a glance and stays through any change of build (hair colour and cut, earrings, a watch, a beard). Soft, motivated light; a neutral background.

## place_look
A real, specific, lived-in place photographed for a TV drama: dense, ordinary set dressing that says who lives or works there. Light comes only from things in the scene: lamps, bare bulbs, string lights, neon or a screen at night, with a deep blue sky through any window; flat fluorescent light in institutional rooms; low golden or morning sun by day. Filmic, low contrast, lifted blacks, warm-neutral colour, never punchy or saturated; no people in frame.

## still_look
The Movie look, unless the brand block says otherwise: "A frame from a photoreal modern TV drama, vertical. Real-looking people with natural skin texture, in a real, specific place dressed with ordinary detail. Faces and builds come from the character sheets, and outfits too unless this video gives its own. Light comes from what's in the scene (lamps, bulbs, string lights, a screen, the sun), and the scene's light follows the story: dark warm practicals or flat cool fluorescents for the struggle, golden hour or morning sun for the change. Filmic, low-contrast grade with lifted blacks, warm-neutral colour. Most shots are close singles at eye level on a long lens with very shallow depth of field and soft bokeh, often with the other person's shoulder soft in the foreground; wides keep the place readable. Characters look at each other, not at the lens. Natural, TV-scale expressions. No captions or on-screen text."

## clip_style
Photoreal TV-drama footage: close shallow-focus singles at eye level, characters talking to each other with lip-synced lines, the camera locked or slowly pushing in (handheld only for action or walking), light from practicals and the sun, the place's own sound

## fit_look
a photoreal TV-drama look with natural, unretouched skin and real everyday clothes, worn the same in every shot

## banned
Pixar-style → photoreal
animated-feature → photoreal
stylised 3D → photoreal

## fixes
refused: Soften it (the free fix rewords the picture, never the lines), then Make another.
face: Make another first. If it drifts again, Change this… "keep the face exactly as the sheet, natural skin texture, no smoothing".
outfit: Change this… naming the outfit's key pieces in the shot, this video's when it gives one, else the sheet's.
product: Change this… "the real product from its image, in the character's hand, the label facing the camera and readable".

## sample
A tired man in his forties with a short dark beard, in a navy hoodie, in a diner booth under warm lamp light, looking just off the lens.

## The videos
A short drama for vertical video: real-looking actors play a scene or a few in real, specific places, lit by the lamps, bulbs and sun in them. Most shots are close singles with shallow focus and a still camera; the sound is the place itself. It's the look of a modern TV drama, used here to tell the script's story.
- The script is the story. Its words and its ending are its own: stage them well and add nothing to them (no line, question or call to action the script doesn't have).
- Where the format's guide differs on pacing or sound (the house shorts' fast cutting and their music), this guide's pacing and sound are the ones to follow.
- These are suggestions from three studied films, not rules: use what serves this script's scenes, and leave out what doesn't.

## Script
Writing a new script in this look: a story told in scenes, each in one place, with characters talking to each other (no narrator); short lines that answer each other, and room for a held look or a silence. An existing script's lines stay word for word, and its ending is its own last words.

## Stills
- Each scene sits in one place and one light. The place says who these people are before anyone speaks: dense, ordinary, specific dressing, with props that stay put from shot to shot.
- The workhorse is a medium close-up or close-up single at eye level, often "dirty" (the other person's shoulder or the back of their head soft in the foreground), with the background's lights soft as bokeh. A wider two-shot every so often puts the people back in the place.
- Eyes just off the lens, on the other person. Looking into the lens is rare and means something: a confrontation, or the close to the viewer.
- Low angles for status, a high angle to make someone small at their low point, a point of view (through a window, past a phone) when the viewer is a witness.
- Inserts on the thing being named: a hand, a ring, a belt notch, a phone, a bottle, the product in a hand. Photoreal, macro, shallow focus.
- When the script explains how something works, one short glossy 3D or macro picture of it (inside the body, a microscopic network, a plant in close-up) is the only stylised picture in the film, and it cuts straight back to the scene.
- The product lives in the scene as a prop someone holds or uses, never a studio packshot (unless it's the very end).
- No captions, titles, time cards or end cards in any picture: those are added in the edit. A label or a phone screen that matters is in the picture with its words stated exactly.

## Clips
- Every clip is made on Omni 1.2, which makes 3–15 s clips with their own sound and voices. A clip can hold a short run of timecoded shots ("Shot 1 | 0–3 s. …", "Shot 2 | 3–6 s. …"): about one exchange of a scene, 2–4 shots, cut on the lines and the reactions.
- The voices are Omni's own, made from the quoted lines: each spoken line in quotes, word for word, with who says it and how ("Mom (quiet, flat): …"). Describe each character's voice in the same few words in every clip they speak in, so it stays theirs from clip to clip. Nobody's voice is laid in from elsewhere.
- A line that carries over an insert (the mechanism, the product, a hand) is best kept in the same clip as its speaker, with the insert as its own timecoded shot, so the voice runs on over it.
- The sound is the place: room tone, a crowd, an engine, gravel, a door. No score and no music bed under anything (music, if any, is added in post); diegetic music only when the scene has a radio or a dance floor in it.
- The camera: locked, or one slow push-in on the line that matters. Handheld only for action, a chase or walking and talking. No slow motion, no speed ramps, no drone shots.
- Up to two people's sheets go into a clip as reference pictures, with the place; anyone else in it is described in words.

## Breakdown
- Scenes are built in places: one place and one light a scene, hard cuts inside it. Group a scene's shots into clips of one exchange each (Omni's 3–15 s), rather than one clip a shot.
- Shots of 2–4 s are the common case, cut on a line or a reaction; a listener's reaction now and then; a held face or a slow push for the line that turns the scene. Hold a silence where the script leaves one (a look, a low point, a first use): the place's own sound carries it.
- A time jump, when the script has one, can be a match cut on a face, a short warm flash, or a cut to the next morning; a card naming the time is the editor's.
- Before and after: when the story changes the hero's body, the "after" is the same person in an after look (the same face, hair, colouring and signature detail; only the build and the confidence change), never a different actor.

## pacing
Measured over the three studied films (6–9 min each; a short video keeps the shot pace and has fewer scenes rather than faster cuts):
- 2.5–4.5 cuts per 10 s; median shot 2–3.2 s; about half the shots 2–4 s; under 1 s is rare (inserts, action).
- The longest hold, 6–10 s, is saved for a reveal or the big confrontation.
- The hook: a line or a hit in the first 1.2 s, the first cut by about 3 s, the conflict visible at once and a reaction face by 1–3 s.
- Dialogue scenes run about 2–3 words a second over the scene, faster inside a run of lines, with pauses of about 0.6–0.7 s; wordless beats (a low point, a first use, an arrival) run on held faces and the place's sound.
- Up to 30 s: one to three scenes, about 8–14 shots, two to four clips.

## camera
- Eye level by default; a long lens with very shallow focus on singles, a normal lens with deep focus on wides, macro on inserts.
- One move a shot at most: a slow push-in (about 2–4% of the frame a second) on the line that matters; locked off for low points; handheld following or walking backwards for walk-and-talks and action; a whip-pan only to join a reaction to an entrance.
- A recurring frame (the same mirror, the same doorway) can track a change across the film.

## Light and colour
- Light comes from things in the scene and follows the story: night practicals (string lights, bare bulbs, a lamp, a TV or dashboard glow) or flat cool fluorescents (a locker room, a restroom, a doctor's office) for the struggle; golden hour and dawn for the change; bright morning sun for the epilogue. Practicals are usually in frame.
- A filmic, low-contrast, warm-neutral grade with lifted blacks; never punchy, no teal-and-orange. Night is dark (brightness 13–30 of 100) with warm skin; day is brighter and less saturated. Only the 3D or macro insert is strongly saturated.

## Cast
- Photoreal, TV-scale people: real skin with pores and shine, tears that look wet, hair with flyaways, no retouching.
- Cast by type so a role reads at a glance (the worn-down hero, the fit mentor, the loud mocker, the offhand doctor), each in one outfit that stays identical in every shot.
- Acting is naturalistic: faces carry the turns (a frozen smile, tears, shock, a quiet smirk); side reactions can be broader, but still human.

## Sound and delivery
- Location sound under every line, well below the voice: room tone, the crowd, engines, doors, footsteps. Sound hits punctuate (a door slam, a whoosh into the 3D insert, a low boom on a key insert).
- No score under dialogue. Music is added in post: the site makes the video's own sound, the voices, the room and the effects, never a music bed, and a cut with none is right.
- Delivery is quiet and close in intimate scenes, loud only when the scene is (a shout, a crowd).

## must keep
1. Photoreal people and real, specific, densely dressed places.
2. One place and one light per scene; hard cuts.
3. Close shallow-focus singles (often with a soft foreground shoulder), with a wider two-shot now and then.
4. Lines lip-synced on camera, eyes just off the lens; the lens broken only for a confrontation or the close.
5. Camera locked or slowly pushing; handheld only for action and walking; no slow motion.
6. Light from practicals and the sun, following the story: dark or cool for the struggle, golden or morning for the change.
7. A filmic low-contrast, warm-neutral grade.
8. Location sound, no score; cuts on lines and actions, not beats.
9. Inserts on what's named; a mechanism as one short glossy 3D or macro insert.
10. Naturalistic acting with held silences.

## safe to vary
- The world and the cast: any place, any lead, any age.
- How much is handheld, and walk-and-talk or shot/reverse coverage.
- The time-jump device (a match cut, a warm flash, a cut to morning; a card in the edit).
- The 3D insert's look (anatomy, a microscopic network, nature macros).
- How it ends: whatever the script's last words are.
- How intense the content is: the script's business.

## combines with
- Format: Dialogue only (the story engine: characters say the script's lines on camera). On this site Narrated and Presenter add a voice track of ours (a narration, or a presenter's), which Movie never has; a character speaking to the lens is a shot inside the Dialogue video, never a presenter.
- UGC shares the photoreal people: a phone-POV hook or a selfie testimonial sits naturally inside.
- The mechanism inserts are the same kind of glossy 3D cutaway as UGC's and Skeleton's.
