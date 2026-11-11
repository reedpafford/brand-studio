# Why tonight's movie ad was weak, and the smallest fix

Video 366 (60 s, 6 clips, Gemini Omni 1.2 at 720p) against the Higgsfield film of the same script that Reed liked (scenes 1-5, Seedance 2.5 at 480p). I watched 366 frame by frame, read its plan and all six clip prompts, and compared them with Higgsfield's real prompt for the same store scene (`docs/research/higgsfield-2026-11-10/run/03-clip-prompt-scene2.md`).

## What is wrong on screen
- **0-13 s, the hook sags.** The stroller mom finishes her line at 4.8 s, then stands on the phone until the cut at about 9 s. No word is heard from 4.8 to 11.0 s. The van sits behind her and barely moves. No strobe.
- **11-13 s.** The cart kid stops, turns to the camera and grins on "I got the plate!", in an abduction scene.
- **16-22 s.** Paige and the stroller mom stand side by side facing us, like a line-up. The sky is pale daylight; five seconds earlier it was deep blue dusk. Same place, same minute.
- **22-25 s.** Paige's eyes are wet (the plan asked for no tears), then two cuts nobody planned (a wider shot, then her legs over the eggs).
- **28-31 s.** The man in gray stands dead centre facing the lens, like a mannequin.
- **31-34 s and 38-42 s.** Paige's thoughts ("Weird. But whatever.", "Construction guys, probably...") are meant to be in her head. She says them out loud.
- **34-37 s.** The "second man" is the first man again, now one step behind her. The script says they never come near her.
- **45-50 s.** The woman in the foreground is a stranger (dark hair, black top), not Paige.
- **53-56 s.** The three men are one face three times, standing together three steps from her.
- **Whole store scene.** The ceiling and aisles change from clip to clip (white tiles, then black open roof).
- **Pace.** About 19 of the 60 seconds have a voice. The same three store lines take 35 s in ours and 24 s in Higgsfield's.

The pictures themselves are sharp and real-looking. What fails is where people stand, where the camera is, how they act and whether the place stays the same. That matches Reed's words.

## Causes, most important first

**1. Our shots say what happens, never where anyone stands or where the camera is.**
- Ours (clip 2): `Medium two-shot, locked. Paige stands over the broken eggs ... while Stroller Mom pulls up beside her`.
- Ours (clip 6): `Wide, slightly high, locked. Down the main aisle, three men in gray sweatsuits stand at three different aisle ends`.
- Higgsfield, same scene: `Wide shot at eye height down the aisle toward the freezer wall ... Paige stands in the midground at the dairy case on the right side of the aisle ... At the far end of the aisle, in front of the freezer doors, Man in Gray stands still ... Two people in frame`.
- With no positions given, Omni puts everyone mid-frame facing the lens. Where we did say something exact it obeyed: "watching her reflection in the glass" came out as a reflection, and every cut landed on its second.
- The plan's instructions asked for this: the camera was "shot size and move" and the action "one or two short sentences".
- The old flow drew a start picture for each shot, and the Movie look rules for those pictures hold the staging ("eyes just off the lens", "wides keep the place readable"). One-pass draws no pictures (366 has none), and the one style line that reaches the video model never said any of it.

**2. One scene was cut into many small clips, and every clip draws the room, the light and the extras again.**
- The store scene is 4 clips (12, 8, 5 and 10 s). Higgsfield made it as one 24 s clip of 7 shots. The parking lot is 2 clips; theirs is 1.
- The Movie guide told the director to do this: "about one exchange of a scene, 2-4 shots" and "Group a scene's shots into clips of one exchange each". The plan's clips have 2, 3, 4, 2, 1 and 3 shots.
- That is where the sky change (13 s) and the changing store come from.
- Clip 5 exists only because the director tried to use one of the brand's real clips there (`footage:286`). The site made the shot instead, without Paige's picture, which gave the stranger. Not fixed here (see the end).

**3. Three men were given one picture.**
- The plan made one role, "The men in gray: Three grown men in identical gray hooded sweatsuits", so one sheet, and every man is that man.
- Our own instructions gave the example that caused it: `"two more men in the same grey sweatsuits, far end"`.
- Higgsfield gave one man a sheet and wrote the others apart: "one with a shaved head and light-brown skin, one with a short brown beard and fair skin, appear only where written".

**4. The prompt tells Omni to move lips on a thought, and acts out mood words.**
- Every clip carries the style line "characters talking to each other with lip-synced lines". The thought lines then say `(voice-over, lips closed, dry)` in a bracket. The style line won, three times out of three.
- Higgsfield writes it into the picture: "her lips closed and still ... Her thoughts are heard as a quiet voice-over while her lips stay closed".
- The cart kid's delivery note was "yelled, voice cracking, triumphant". He played triumphant. (One case, so this is likely, not proven.)
- The unplanned cuts at 23 s follow the words "handing off to the eggs on the shelf", a note to ourselves that was sent to the video model.

**5. Shots are longer than their lines.**
- The hook's first shot was given 9 s for a 20-word line: three words a second plus a pause after each sentence, as the Movie guide says. Shouted, it took 4.8 s. Nothing else was planned for that shot, so she stands.

## What the successful example does differently
- One clip per scene (8 to 24 s), so the room, the light and the people cannot change inside a scene.
- Every shot says where the camera is, where each person stands, which way they face, and how many people are in the frame.
- The scene opens on a wide that shows the place and where everyone is; the close shots come after.
- One fixed paragraph in every clip: faces turned three-quarter, eyes to one side of the lens, "the actors play small and real".
- People who dress alike are told apart in words.
- Thoughts are written as closed lips in the shot itself.

## The theory
When we dropped the storyboard we dropped the staging with it. The start pictures used to fix where people stood, where they looked and what the room was. One-pass sends only words and character sheets, and our words describe the story beat ("Paige stops and looks at her basket") but not the frame. So the video model fills every gap the same way: one person, centred, facing us, in a freshly invented room. Higgsfield has no storyboard either. It gets the staging from words: each shot placed in the room, one clip per scene, and an opening wide. Omni followed nearly everything we stated exactly, so the fix is to state those things, in a few words per shot.

## Which video model for Movie
**Recommendation: stay on Omni 1.2 for now, and decide on Seedance with one side-by-side test after this fix.**

Evidence:
- Every fault above traces to a line in our plan or prompt. None is shown to be Omni's alone.
- Omni followed what we stated: cut times, the reflection, the man crossing the far end of the cereal aisle (42-45 s).
- Omni costs about $0.07 a second at 720p. Seedance 2.5 costs about $0.10 at 480p (softer picture) and $0.23 at 720p.
- Seedance has three real advantages for drama: 30 s clips where Omni stops at 15, about eight people with pictures in a clip where Omni takes two, and a voice sample to keep a voice the same across clips.
- The only film Reed liked was made on Seedance.
- On our road to Seedance (Replicate) a real-looking teenager's picture was refused on Seedance 2.0 (the th-20s test). Since then the site sends no pictures of people to Seedance in real-looking styles and describes them in words instead, so faces would not be held.

Guess, not evidence:
- That Omni will hold a whole 15 s scene of five or six placed shots as well as Seedance holds 24 s.
- That Replicate's Seedance 2.5 would accept adult character sheets the way Higgsfield's does. Nobody has tried.

## The change (branch `night/movie`)
No new lines; 13 lines reworded; about 150 words added. No new checks.
- **The plan's instructions** (`server/app/prompts/one_pass.md`, read by every style):
  - the camera says where it is;
  - the action says where each person is and which way they face;
  - a thought is written as closed lips;
  - a delivery note is about the voice only;
  - a group who dress alike is one role plus extras told apart (the example that caused the clones is replaced);
  - a hand-off is shown, never named.
- **The Movie guide** (`server/app/guides/styles/movie/guide.md`):
  - a clip is a whole scene, two if it runs past 15 s (replaces "one exchange of a scene, 2-4 shots");
  - an early wide in each scene shows where everyone stands;
  - a shouted line is sized shorter and a shot is not padded past its line;
  - the style line on every clip now says "faces turned three-quarter with eyes just off the lens, the acting small and real" in place of "close shallow-focus singles ... lip-synced lines".

## Seen but not fixed
- A Movie plan is offered the brand's real clips, which only UGC can use. The director split out clip 5 for one, and the site made the shot instead.
- Our place pictures show one direction of the room. Higgsfield's show both, which helps a room stay put. That is a bigger change.
- The listen check says the three thought clips "aren't planned to speak", though the plan asks Omni to voice them.

## How to test it
One video, about $4 to $5, stop at $6. It needs this branch on the test site first.
- **Script:** `.context/pgtest/excerpts/1-movie-RP5.txt`, the same excerpt as video 366, pasted as a finished script.
- **Settings:** the same as 366, so only the instructions differ: Palace Guard, Movie, Dialogue, 9:16, Gemini Omni 1.2 at 720p, the same product, a new video (so the plan is written fresh).
- **Expected cost:** about 45 to 50 s of clips at $0.07 is $3.15 to $3.50, plus about $1 for the plan and pictures.

Read the plan before the clips are made (free to check):
1. The store is 2 clips at most (was 4) and the lot is 1 (was 2).
2. The whole video is about 45 to 50 s (was 60).
3. Shots say where people stand ("at the far end", "near us").
4. The men are one role plus two extras who look different.

Then watch the cut:
1. Nobody stares into the lens, and two people are never side by side facing us.
2. The three men have three different faces and stay at the far end of the aisles.
3. Paige's lips stay closed on her three thoughts.
4. No silent wait of more than about 2 s after a line in the first 13 s, and the cart kid is not smiling.
5. The store looks like the same store from start to end.

If items 1 to 4 pass and the store still changes between its two clips, that is the case for the Seedance test: the same script with the model set to Seedance 2.5 at 480p, about $5.
