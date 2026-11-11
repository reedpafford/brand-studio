# The shooting plan for a song video
<!-- Added to the one-pass plan (EXTENDS one_pass) for a song video. Inputs added: <song> (the song in use, measured: its sections with the best places to cut, its beats, and each sung line with the seconds it is heard and its words' start times). Output: ShootingPlan, with each shot's `at` and each clip's `kind`. -->
<!-- Leaves out of the step above (they are for lines spoken on camera): **Voices** -->

This script is a song. It is already made, and <song> is that recording, measured. Everything above still holds unless this section says otherwise.

**The song is the clock.** Never guess a length. Each shot starts on a sung line's start, a word's start, or one of the cuts listed for its section: copy that second into the shot's `at`. The first shot's `at` is 0 and they only rise; never cut mid-word or across a section's edge. Code works out every length from the next shot's `at`, so leave `seconds` at 1. Stretches with no singing get pictures too.

**The pictures show the lyric.** Every clip is B-roll (`kind`: "broll"): what the sung line says, shown literally and big, with the chorus the biggest pictures in the video. Nobody sings on camera and no lips move: `line` is none on every shot and `voices` is empty.

**Clips follow the song.** Neighbouring shots in one place share a clip, up to the model's longest clip; a clip with people in it that would run past about sixteen seconds splits on a beat. Each section's first picture is a fresh place or a clear change.

**Sound** is left empty: the song is the only sound in the finished cut.
