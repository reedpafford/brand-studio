# Step: Narration music (the bed under a narrated video)
<!-- Inputs: <script> (the narrated script, as written), <seconds> (the narration's length), optional <note> (the editor's words about the music). Output: NarrationMusic. The server sends music_prompt(result) and the seconds to the music model (an instrumental, flows N1); check.narration_music(result) runs first, free. -->

Write the music for a narrated brand video: one instrumental bed, <seconds> long, that sits under one narrator's voice from the first word to the last. The narrator carries the words, so the music only carries the feeling.

Read the script for its feeling and where it turns. Most ads turn once: a problem, then the answer. The music follows that turn at the same point in the script, by thirds ("dark, tense documentary bed that lifts to hopeful in the last third"). A script that never turns keeps one mood. Fit the brand's own voice (brand block): a playful brand never gets a horror bed.

`prompt` is one paragraph of 30 to 60 words for the music model, in this order:
1. Genre and mood in a few words ("dark, tense documentary underscore").
2. Three to five instruments or textures, plain and concrete ("ticking pulse, low drones, sparse piano, soft hits").
3. The tempo, as BPM or words ("slow, about 70 BPM").
4. The turn, if the script has one, by thirds ("in the last third it lifts: warmer chords, brighter piano, a steady beat").
5. "Steady and low under the narration: no big drops, no solos, no sudden stops."

Never name an artist, band, song, film or composer, and never write "in the style of" anyone; the music model refuses names. Describe the sound itself. Write no vocals, choir, humming or lyrics: the narrator is the only voice. Don't write the length or "instrumental"; the server adds both.

`arc` says the same in a few plain words for the editor ("tense, then hopeful in the last third").

**The editor's note (<note>, when given):** follow it over your own reading, still with no names and no vocals.
