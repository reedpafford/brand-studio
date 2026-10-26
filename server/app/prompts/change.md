# Step: Change it (a still's or a clip's prompt, from a plain-English note)
<!-- Inputs: <kind> (still | clip), <prompt> (the prompt as it stands), <note> (what the person wants changed). Output: ChangedPrompt. The server checks the note never touches dialogue before this runs, and compares the answer with the prompt: the same prompt means nothing is made. -->

Someone looked at the still or clip made from this prompt and wrote what should change. Rewrite the prompt so the next one shows that change, and nothing else.

- Change only what the note asks for. Every other word stays exactly as it is: the shape, the shot lines and times, the references and [ImageN] tags, the Keep and Audio lines.
- Spoken lines never change: every `Name (how it's said): "words"` keeps its words exactly. A note about a line changes only how it's said (the part in brackets).
- Say the change as what we see: faces, bodies, camera, light, where things are. Don't explain it, and don't mention the note.
- If the prompt already does what the note asks, give it back unchanged.
