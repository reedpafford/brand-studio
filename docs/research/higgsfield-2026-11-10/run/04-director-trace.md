# Higgsfield run: what its director did, step by step (read from the chat's own step list, 10 Nov)
Chat model: Sonnet 5.5, medium effort. One conversation. Whole job after the go-ahead: 25 m 16 s for 3 place pictures, 6 clips (110 s), the join and the checks. No remakes.

## It is a working agent with a sandbox, not a chain of steps
- It keeps files (jobs.json, a script.json it chose not to write, prompt "pieces"), runs terminal commands (download, ffprobe, whisper, ffmpeg), looks at pictures ("Analyzed image"), and uploads files (voice samples, the film).
- Its skill has heavier machinery it may skip. On this run it skipped, saying so each time: the "mechanical script.json checks" ("writing a full script is a lot of JSON"), the "plate-frame step" for the store scene ("it would only add cost and an edit pass"), and the assembly script with its cut and seam analysis (plain ffmpeg instead). It had been told "go straight on, fix only real faults".
- Fixed prompt text is not rewritten each time: the place prompts were "assembled from the pieces" already on file, with fixes applied.

## Order of work
1. Place pictures: prompts assembled from files, 3 sent at once.
2. Looked at all 11 reference pictures for real faults only (a cropped panel is fine if the face panel is there; the van's cab windows noted, not redone).
3. Planned every clip in one pass of thinking, no document: per clip its length, which pictures it uses, the opening picture, each shot, when each line starts (it moved lines apart when a first pass ran tight, and left quiet seconds at each clip's end), and which clip first "creates" each person's voice.
   - Clips: k1 20-22 s (scene 1), k2 24 s (scene 2), k3 12 s (scene 3), k4 8 s (scene 4), k5 24 s and k6 20 s (scene 5; k6 is an extension of k5, not a new clip).
   - Extras with no sheet are given distinct looks in words so three men in the same clothes do not come out as one man three times.
4. Sent clip 1 alone first, "so I can read back its parameters before batching the rest", and checked the picture tags against its list.
5. Then the clips that depend on nothing (k2, k4) together.
6. Checked each finished clip with cheap tools: ffprobe (size, length, sound), whisper (the words and when they land), and one look at a sheet of its frames.
7. **Voices:** cut a 3-second voice sample for a person from the first clip they speak in (found by whisper's timings), uploaded it, and attached it to every later clip of that person: "@Audio 1 is the voice of @Image 2, Paige: every line she speaks is in this voice". A 1.7 s sample was repeated to reach 3.6 s.
8. Then the clips that needed a voice sample (k3, k5), then k6 as an extension of k5: "@Video 1 is the clip being continued: keep ... exactly as in its last frame", with its pictures and the voice sample.
9. Join: clips in film order with ffmpeg, re-encoded, sound levelled to -14 LUFS, a 0.4 s black beat after the cold open.
10. One listen to the whole film with whisper for every line, upload, and a plain report: cost against its estimate, what changed from the script, its own faults, three next steps as presses.

## Dialogue in a clip prompt (clip 3, 12 s, two people)
- Shots say only that someone speaks ("She speaks calmly."). The words are in one block after the shots:
  `Dialogue. Manager (a calm, dry, mid-low woman's voice, friendly and routine), at 3.6 s: "Find everything okay?" Paige (her voice from @Audio 1, quiet and a little strained), at 6.4 s: "Yeah. Thanks."`
- A person with no sample yet gets their voice described in the block; that clip then becomes the source of their sample.
- Clip 6 carried 7 pictures (place, 4 people, the alarm, the van), the clip it continues, and a voice sample.

## What this means for speed
- 6 units of work for 110 seconds, not 20-plus. One thinking pass plans them all. Nothing is drawn per shot.
- Work is ordered by what depends on what: one pilot, then everything independent at once, then the rest.
- Checks are tools first (probe, transcribe), one look per clip, and a human-readable report instead of automatic remakes.
