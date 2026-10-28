# Step: Change it (a still's or a clip's prompt, from a plain-English note)
<!-- Inputs: <kind> (still | clip), <prompt> (the prompt as it stands), <note> (what the person wants changed). Output: ChangedPrompt. The server checks the note never touches dialogue before this runs, and compares the answer with the prompt: the same prompt means nothing is made. -->

Someone looked at the still or clip made from this prompt and wrote what should change. Rewrite the prompt so the next one shows that change, and nothing else.

- **Change only what the note asks.** Every other word stays exactly as it is: the shape, the shot lines and their times, the References line and every [ImageN] tag, the Audio lines. Never add, drop or renumber a reference, and never bring in a person the prompt doesn't have.
- **Spoken lines never change.** Every `Name (in English, how it's said): "words"` keeps its words, its quotes and its language label ("in English") exactly: never translate a line or drop its quotes or its label. A note about a line changes only how it's said (the part in brackets) or what we see while it's said.
- **The Keep line follows the change.** If the note changes something the Keep line pins (an outfit, hair, a prop), change that part of the Keep line to match, so the two never disagree. Otherwise the Keep line stays word for word. Each person keeps their own look; a note about one person never moves their clothes or features onto another.
- **Screens stay exact.** A real brand screen keeps "with its logo, colours and layout exactly". A note about the money on it may name a figure ("the balance reads $18,900"), but only the logo must be right, so never change the screen's other content. An invented trading screen keeps "the fomo logo from [ImageN], the word fomo in lowercase, sharp and legible in the top corner", and a note may change its chart and number.
- **Say it as what we see:** faces, bodies, camera, light, where things are, in the prompt's own terms. Don't explain the change and don't mention the note.
- **A still** (kind still) is one image prompt. Keep its "Place the app screen from image N…" and "the person from image N" sentences as they are, and change only the scene the note is about.
- If the prompt already does what the note asks, give it back unchanged.
- Give back the whole prompt, every line, with only the note's change made: never just the changed part.
