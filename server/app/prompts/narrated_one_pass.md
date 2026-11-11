# The shooting plan for a narrated video
<!-- Added to the one-pass plan (EXTENDS one_pass) for a narrated, presenter or Zack D video. Inputs added: <song> (the narration in use, measured: its length and each sentence with the seconds it is heard and its words' start times), and for a presenter video a <host> block (who presents and how they appear) or a <talker> block. Output: ShootingPlan, with each shot's `at` and each clip's `kind`. -->
<!-- Leaves out of the step above (they are for lines spoken on camera): **Voices** -->

This script is narrated. Its words are already recorded as one voice track, and <song> is that recording, measured. Everything above still holds unless this section says otherwise.

**The narration is the clock.** Never guess a length. Each shot starts where a sentence, or a phrase inside a long one, is heard: copy that start into the shot's `at`, the second in the track, from the times in <song>. The first shot's `at` is 0 and they only rise. Code works out every length from the next shot's `at`, so leave `seconds` at 1. One shot per sentence, or per phrase when a sentence runs past about two and a half seconds; a pause gets a picture too (a reaction, the product, the world moving on).

**Every clip is B-roll** (`kind`: "broll") unless a <host> or <talker> block says otherwise. Each shot shows what its sentence says, literally, so the story reads with the sound off. Nobody on screen speaks or moves their lips: `line` is none on every shot and `voices` is empty. A person may look into the lens at a turn or at the offer. Neighbouring shots differ in size and angle, so the eye always has something new.

**Clips follow the narration.** Neighbouring shots in one place share a clip, up to the model's longest clip. Never end a clip inside a sentence. A new place or time starts a new clip.

**The picture lands on its word.** What a sentence names (a number, the product, the reveal) is on screen as the word is heard, never before it: use the word's own start time for that shot's `at`. The payoff picture arrives within about a second of the last words and holds.

**Sound** is the scene's own, two or three real sounds, never a voice and never music: the narration is laid over the finished cut.
