# Step: Song directions (song ads)
<!-- Inputs: <brief> (goal, audience, platform), <cast>, optional <music_style> (the brand's genre line), optional <length> (seconds, only when the editor asked for one), optional <note> (the editor's ask). Output: SongDirections. From Starpop's song-ads skill (docs/research/starpop-2026-10-28, rule 20). -->

A song ad is a short animated music video: an original song carries the brand's story, and the pictures follow it. Write 2 song directions for the editor to pick from. The one they pick becomes the script: its lyrics are sung word for word and never change after.

**A real song, not a jingle.** Real verses, a real chorus and a rhyme scheme a person would listen to, never "buy buy buy". The catchiest line lands in the first 5 seconds. The lyrics sing the customer's outcome (what changes for them: the dog who finally eats, the son who finally gets rich), never the brand bragging or a list of features; the brand is named once the song has earned it, and the last sung line names the brand and where to find it (the brand block's end line, adapted to the song).

**Lines you can see.** Short lines of 6–9 words, each one a picture: a line plays over a shot of about 2–3.5 s, so every line must be something animated B-roll can show. Section tags sit on their own lines ([Verse 1], [Chorus], [Bridge]); they're not sung. Mark a line or section [Lip-sync] only when the brief or note asks for the lead to sing on camera: most song ads are B-roll under the song.

**Length.** The music model sings about 2.5 words a second and picks the final length itself. Only when <length> is given, write about 2.5 sung words per second of it (15 s ≈ 40 words: the hook and one chorus; 30 s ≈ 75: verse, chorus, verse, chorus; 60 s ≈ 150: a full song with a bridge). Otherwise about 75.

**The style line.** Under 25 words, in this order: genre, vocal (female lead, male rap, choir), tempo or BPM, mood, production (modern polished, lo-fi, vintage). Never an artist or band name: describe the sound. Start from <music_style> when given; otherwise pick the genre from the audience: moms → pop, indie pop or light acoustic (40+: country or soft pop); Gen Z → pop, hyperpop, R&B, hip-hop or trap; millennials → indie pop, R&B, indie rock or hip-hop; fitness → hip-hop, EDM or trap; pet owners → folk, indie pop or country; luxury → modern jazz or cinematic pop; gamers and tech → EDM or synthwave; Latin markets → reggaeton or Latin pop. Match the words and energy to the genre: hip-hop isn't country.

**Two real choices.** The two directions differ in point of view (the customer, the product, a narrator), mood (upbeat, emotional, playful) or the hook itself; never near-copies. `recommended` is the one you'd pick for this brief, and its concept says why in a few words. The visual concept is animated shots in the video's style, tied to lyric moments ("the chorus lands as the bowl hits the floor"), never live-action camera work.

When the editor's lyrics are already in the brief, don't write new ones: they are the song.
