# The song-ad workflow (the one that made the Iron Paws song ads)

Reed, 2026-10-29: "Those are amazing. I want whatever workflow made those."

This is the exact recipe behind "That's My Gut Breaking Down" and "Same Gut, Three Places": $39.47 for both, 2:45 and 2:28. It has two uses:
1. **Now:** an agent runs it by hand for any brand, with `tools/song_ad/song_ad.py` and the live app. Reed approves at the marked gates.
2. **Next:** the spec for building it into Brand Studio Next, so editors run it themselves (the last section).

The pilot log, with every problem hit along the way, is in `docs/next/song-pilot-notes.md`. The worked example (directions, shot plans, the exact Suno requests and app scripts) is in `docs/next/song-pilot/`.

> **Paid calls.** Every run that calls KIE (the song) or makes anything on the live site (looks, stills, clip prompts, takes) costs money. It needs Reed's OK on a cap first and a row in `ops/SPEND.md` after (PR to main). Keys and sign-in come only from the environment and are never printed, logged, committed or put in chat.

## The recipe

| # | Step | Who | Cost | Gate |
|---|---|---|---|---|
| 1 | **Brief:** brand, product, the reference ad(s), the editor's script if any, length | Reed | free | |
| 2 | **Study the reference:** fetch it, transcribe it, BPM, frame sheet (`song_ad.py ref`) | agent | free | |
| 3 | **Two song directions** per video: concept, lyrics, style line, visual concept; one recommended | agent | free | **Reed picks; the lyrics lock** |
| 4 | **The song:** Suno V6 through KIE, 2 takes per request (`song_ad.py song`) | agent | ~$0.06 a song | **Reed OKs a small song budget, then picks a take** |
| 5 | **Measure:** every locked line's start and end in the take, BPM (`song_ad.py measure`) | agent | free | |
| 6 | **Shot plan:** one clip per piece of the song (one place, one action), what's on screen, cost | agent | free | **Reed OKs the plan and the video budget** |
| 7 | **Into the app:** a dialogue-free script in the brand (one SCENE per clip, ★ product lines), cast read, publish, make the video, set the product variant | agent | ~$0.40 | |
| 8 | **Retime:** the breakdown's shots get the song's times (`song_ad.py retime`) | agent | free | |
| 9 | **Looks:** "make missing looks", one description shared by both videos when they share a cast | agent | ~$0.30 a look | **Reed approves the looks** |
| 10 | **Stills:** frame prompts, one still per clip, check by eye, "Change this…" on any off-model still | agent | ~$0.05 a still | |
| 11 | **Clip prompts:** write them, clear the flags (free fix, or a word swap) | agent | ~$2 a video | |
| 12 | **Takes:** make all, retry refusals or "busy" (free when refused) | agent | ~$0.10 a second | inside the budget |
| 13 | **Review:** 4 frames from every take (`song_ad.py review`); remake only real problems | agent | ~$0.50–1.80 a remake | inside the budget |
| 14 | **Final cut:** each take trimmed to its piece of the song, the song as the only sound, a 1.5 s fade (`song_ad.py cut`) | agent | free | **Reed gets the MP4** |
| 15 | **Log:** every paid call in `ops/SPEND.md` (PR to main), notes for the team | agent | | |

## What made them good (keep these)
- **Study the reference first.** Listening to the winning ad (it was a dog-POV *song*, not a voice-over) set the format, the hook and the shape. The visual grammar came from its frames:
  - exaggerated symptom close-ups in the first seconds
  - the daily routine
  - a cute trip inside the body that explains the cause
  - the find on her phone
  - the product into the bowl and the mid-air leap
  - "weeks later" with the reveal, then the apology and the hug
  - the proof lines
  - the pet pushing the product to camera on the last line
- **The editor's script becomes the lyrics, beat for beat.** Keep its story, its key lines ("That is my gut breaking down", "We were good", "You just didn't know… now you do… waiting on you") and its claims word for word. Add only the brand name to the last line.
- **The hook is the symptom list, sung in the first 5 seconds,** each symptom a chanted line ending in the same phrase.
- **A style line that describes the sound,** never an artist. For Reed's older audience: laid-back, breezy pop, warm female vocal, about 100 BPM, strummed acoustic guitar, light drums and handclaps. Suno's pacing add-on: "vocals start immediately, no instrumental intro, no instrumental breaks, continuous singing, tight ending".
- **The song is the clock.** Measure the real take; every clip covers one piece of it, and every shot inside covers one line. Pick the tighter take: it's cheaper.
- **B-roll only, nobody sings on screen.** No lip-sync to break, and every line is shown literally, so it reads with the sound off.
- **One place and one action per clip, 4–18 s.** Clips over 16 s with people are split in two, because long clips drift faces.
- **Exaggerate.** A crust-glued eye, a tongue blur, a fur blizzard, a vacuum "fur mountain", a shampoo-foam hat, a desert-cracked nose with a tumbleweed, the wise old dog walking in slow motion, bacteria buddies laying bricks, a chlorella wave, a chicory root planting itself.
- **The product exactly, at four moments:** the find (on her phone), the feeding, the proof, and the end (the pet nudges it to the lens). Set the project's product variant (peanut butter, not chicken).
- **Look at everything before paying for the next step:** the looks, a contact sheet of stills, a contact sheet of frames from every take.

## Costs to expect (480p)
About **$0.13 per second of finished video**: roughly $20 for a 2:30 song ad. The takes are about 88% of it. Songs are cents. Plan the budget at 1.5× the takes, to cover a few remakes.

## Running it now (agent)
- **Sign-in:** the QA owner from the environment (`BS_QA_EMAIL`, `BS_QA_PASSWORD`). The Suno key is `KIE_API_KEY`. A key saved after a session starts only reaches new sessions, so start a helper session for step 4 if needed.
- **Tools:** Python with `requests`, `playwright` (pre-installed Chromium), `faster-whisper`, `librosa`, and ffmpeg.
- The app steps without a `song_ad.py` command (7, 9–12) are plain API calls. The paths are listed in `docs/next/song-pilot-notes.md` and the pilot's PRs. Every call that starts a job returns a job id; poll `GET /jobs/{id}`.
- **Never** change or delete anyone else's projects. Ask for a budget per video before step 7.

## Building it into Next (the editor's version)
What the pilot had to do by hand, in the order it hurt:
1. **A song step in the video flow.** Song directions (with a third mode: "adapt my script into lyrics, keep its beats and claims"), then Suno takes through one provider interface (KIE first), a Preferred mark, and each take's length shown next to the video cost it implies.
2. **The song as the breakdown's clock.** Measure the Preferred take (Whisper word times aligned to the locked lyrics, as `measure` does) and feed the line times to the song breakdown, so shots and clips land on them (what `retime` does). Split long clips with people.
3. **"Song as the only sound" in Make video.** Trim each take to its piece of the song and lay the song under it (what `cut` does). Today Make video keeps the take sound.
4. **A reference study for song ads:** the reel import should return the transcript, the BPM and the sections with the frames.
5. **A shared cast for a pair of videos,** so the same dog and owner aren't drawn twice.
6. Smaller: false "Check the cast" alarms on insert shots; the word "answer" flagged as a spoken line; the free clip-prompt fix often has nothing to fix.
