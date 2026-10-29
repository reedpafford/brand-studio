# Song ads
<!-- Inputs added to the breakdown's: <song> (song_block: the preferred take's length, BPM, beats, sections and sung lines with times). The script is the lyrics. Output: SongBreakdown. From Starpop's song-ads skill (docs/research/starpop-2026-10-28, rule 20). -->

This script is a song: its lines are lyrics, sung by the music model, and the <song> is the real take, measured. The song leads and the pictures follow it; everything above still holds unless this section says otherwise.

**The song is the clock.** Never guess a length: every shot sits on the song's real time, and the measured line times in <song> are that clock. A shot that holds a sung line starts where that line is sung and ends where it ends (or where the next line starts), from those times, never from the words' count. `song_start` and `song_end` are seconds in the song, on beats from <song>; the shots run back to back from 0 to the song's end with no gaps, instrumental stretches included (they get pictures too: the hero reacting, the product, the world moving on the beat). A shot holds one lyric line or less, and never runs across a section's edge; `seconds` is `song_end` minus `song_start`. A sung line's shot covers it from its first word to its last: never cut mid-word.

**B-roll by default.** Every shot is B-roll: silent picture under the song that shows what the line at that moment says, literally, so the story reads with the sound off. `line` and `speaker` are null for B-roll (nobody on screen speaks or sings; the song plays over it). `sung` is true only on lines or sections the script marks [Lip-sync]: the lead sings them on camera, `speaker` is the lead and `line` holds the sung words exactly. Vary the B-roll framing (wide, close on the product, the hero's face, an insert), cut on the beat, and give the chorus the biggest pictures.

**Clips follow the song.** A clip's shots are consecutive and its slice of the song runs from its first shot's `song_start` to its last shot's `song_end`; `seconds` is that span rounded up, within the video model's limits. End clips on a section's edge or a strong beat, never mid-line, and still one scene a clip.

**The brand.** The required screens and products still show at their moments, on the line that names or needs them. The last sung line's shot shows the real brand element (the phone with the app, the bag), large and clear.
