# Step: Video variations
<!-- Inputs: <brief>, <cast>, <script> (numbered, its words final), <treatment> (the finished video's), <clips> (its plan: each clip's shots, the lines they cover and what they show), <part> (hook or ending), <count> (2 or 3), optional <note> (what the person asked for). Output: VideoVariations. -->

This video is finished and delivered. The person wants <count> variations of it that differ only in their <part>: the same video, with the same cast, look, voices and every other clip kept as it is, but a different hook (its opening) or a different ending. Only the clips you name are made again; every other clip and take is reused as it is.

**The script never varies (see "The editor owns the script", above).** A different hook or ending comes from the script itself: a different picture or staging of the same opening (or closing) line, a different shot or moment of the script brought forward as a silent picture in the first seconds, a different reaction or payoff picture on the last line. The spoken words and their order stay. Never write brand copy, a slogan, a claim or a call to action the script doesn't have.

**The person's own words.** Only when <note> gives new words in quotes for the opening (or closing) line, that variation may use them: set `line` to that line's number and `words` to those words exactly, and name a clip that says that line. Nothing else ever changes a word.

**Each variation:**
- `title`: a few words naming the idea, as the team would.
- `direction`: the new hook (the first 2 seconds: what we see and hear, on the conflict or the most striking picture, never on setup) or the new ending (the payoff and why it lands), written as the treatment's own `hook` or `ending` would be.
- `clips`: the clips it makes again, as few as the idea needs: for a hook, the first clip and only the clips right after it that the new opening touches; for an ending, the last clip and only those right before it. Never every clip.
- `note`: the change note for those clips, ready to send to the clip's prompt: what we see and how the moment plays now (the picture, the staging, the camera, the reaction). It never quotes or changes the words.

The <count> variations are different ideas from each other and from the video's own <part> in <treatment>, each one a reason to stop scrolling (or a payoff that lands harder) for this story and this look. <note>, when given, steers them.

Plain words throughout: the person reads each variation's title and direction before choosing to make it.
