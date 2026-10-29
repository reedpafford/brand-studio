# Narrated videos
<!-- Added to the breakdown step for a narrated video only (EXTENDS), so story breakdowns stay as they were (flows V6n). Inputs added to the breakdown's: <song> (song_block of the narration in use: its length, and each sentence as a line with its measured times; no beats or sections). Output: SongBreakdown, with `sung` always false. -->

This script is narrated: every spoken line is the narrator's voiceover, read once as one track and laid under the finished video. The <song> block is that narration, measured: its sentences, each with when it's heard. Everything above still holds unless this section says otherwise.

**The narration is the clock.** Never guess a length: every shot sits on the narration's real time. A shot that shows a sentence starts where that sentence is heard and ends where it ends (or where the next one starts), from the measured times, never from the words' count; `song_start` and `song_end` are those seconds, back to back from 0 to the narration's end with no gaps (a pause gets a picture too: a reaction, the product, the world moving on). Never cut inside a sentence. `seconds` is `song_end` minus `song_start`.

**All B-roll.** Every shot shows what its sentence says, literally, so the story reads with the sound off. Nobody on screen speaks or moves their lips: `line` and `speaker` are null and `sung` is false on every shot; the narrator is never on camera saying the words.

**Clips follow the narration.** A clip's shots are consecutive, one place and one action, and its slice runs from its first shot's `song_start` to its last shot's `song_end`; `seconds` is that span rounded up, within the video model's limits. End clips between sentences. A clip with people in it runs 16 s at most: split a longer stretch at a sentence's end.
