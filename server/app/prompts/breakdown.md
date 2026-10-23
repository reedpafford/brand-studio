# Step: Breakdown
<!-- Inputs: <brief>, <cast>, <places>, <video_model> (name, min/max seconds per clip, reference limits), <script> numbered. Output: Breakdown. -->

Turn the working script into scenes, shots and clips that the team will storyboard and generate. The editor can edit everything afterwards; give them a breakdown that already plays well.

**Shots.** Cover every script line, in order, with no gaps. The words in `line` are the script's, unchanged. Break dialogue so each speaker's line and each turn in an argument gets its own shot (shot and counter-shot), and give the big moments their own reaction shot. Winning reels from this genre cut every 0.3–1.8 s in arguments and montages and hold longer only for a line that needs it. Inserts (the phone screen, the number, hands on the keyboard, the clock) move the story without dialogue. Write camera so it carries emotion: push in on the doubter's accusation, a high or isolated wide for the low point, a low angle and a tracking move for the payoff.

**Scenes.** One per place or time. The `look` tells the story state in light and colour: cold blue and dark for struggle, the warm glow of a laptop or phone lighting the face for the grind, warm gold or neon for the win, background people who react when it's public.

**Brand.** Tag each shot's `moment` from the brand block. Any shot whose moment has a screen gets that screen in `screen_ids`, usually as its own insert, and the reaction to it in the next shot. If a trading or brand moment has no ★ line in the script, still show the screen: it's required.

**Clips.** Group consecutive shots into clips the video model generates in one go, each within its min and max seconds. End a clip only on a hard cut that changes place or time, or when the next shot would pass the max. A clip that starts after a time jump opens on an insert (phone, screen, hands) before the hero's face. Fewer, longer clips keep characters consistent; don't split a conversation across clips unless you must.

Use only ids from the user message and the brand block.
