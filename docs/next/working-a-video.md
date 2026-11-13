# Working a video with Reed (the way RP5 was made)

Reed, 13 Nov 2026, after Movie Ad 1 (RP5): "what we just made, and the flow of how we made it was perfect." And: "the workflow we worked on to make RP5, can you save that ... The thinking and workflow should not be specific to the movie style ... So that hypothetically if i came to you with any type of video we could work through it like that - and you will never drift from that workflow."

This is that workflow, for any style or format. It is how an agent works a video with Reed from a script to a finished cut. It is not a style guide: what a style looks like stays in its guide. Where this file and a style guide differ on how the pictures look, the guide wins; on how the work is done, this file wins.

RP5's own record (every round, every fault, every price) is `.context/MOVIE-HANDOFF.md` in the skopje workspace; its tools are in `.context/rp5/`.

## The order of work

| # | Step | What Reed sees | Gate |
|---|---|---|---|
| 1 | Understand the ask | A few questions, bundled, each with a recommendation | He answers once |
| 2 | Learn the tools before using them | What the model's own guide says, and what changes from what we do now | |
| 3 | Prove it small | One short test (about 10 s), side by side when there is a choice | **He picks** |
| 4 | Prove the hard part | The one thing most likely to fail, alone (RP5: four people in one scene) | **He says go** |
| 5 | Plan the whole video and price it | Seconds, rate, total, a stop | **He OKs the price** |
| 6 | Make the references | Each person, place and product as one picture | He sees them; casting is his say |
| 7 | Film | Nothing, unless a provider runs dry | |
| 8 | Check every clip before he does | | |
| 9 | Cut and deliver | The video on his Desktop, and what is still wrong with it | |
| 10 | A round of notes | "These clips change, this is the price" | **He OKs the round** |
| 11 | Finish in the edit | The finished versions | |
| 12 | Put the lessons where they last | What changed on the site and in the notes | |

Steps 3 and 4 can be skipped only when the same style, model and kind of scene have already been proven. Say so when skipping.

## 1. Understand the ask

- Read everything he gave first: the script, the references, the earlier notes. Then ask only what cannot be worked out, all at once, each question with the answer you would pick.
- A decision he has already made is never asked again.
- His references are "loose creative guidance", not a template: "we can probably do better."
- The script's words are final. Creative liberty is in the pictures, never in the lines.

## 2. Learn the tools before using them

- Prompt each model the way its own maker says to, using a guide that is known to work. For RP5 that was Higgsfield's course and the model's own documentation, read in full before a prompt was written.
- Start from an example that succeeded and change one thing at a time.
- "Make sure we aren't just mindlessly stacking prompts and lines and direction, we are carefully inserting and removing, iterating." A new instruction replaces the one it corrects. A prompt is as long as it needs to be and no longer.
- When a model refuses or fails, find the rule behind the failure with the smallest test that can show it, before trying anything bigger. (RP5: the video model refused every real-looking face until the sheet was drawn by its own maker's image model on the same account. Four cheap tests found that; nothing else would have.) A refusal usually costs nothing; use that.

## 3 and 4. Prove it small, then prove the hard part

- The first paid thing is short: about 10 seconds, one beat of the script.
- When there is a choice (two models, two ways of prompting), make the same beat both ways and put them side by side. His test: "can we tell the difference in 5 seconds?"
- Then test alone whatever is most likely to break in the full video: several people in one shot, the product's mechanism, a voice that must stay the same, a long continuous take.
- Only after he likes a sample is the whole script planned. His words that opened RP5: "I think this was a great sample clip. Lets do the whole script."

## 5. Plan the whole video and price it

- For every beat, before any camera word, answer two questions: **what must the viewer understand here, and what does each person want?** Write the answer as something a body does. This is the lesson Reed corrected on RP5: "it was more on you not capturing emotions or events well enough off the script."
  - A feeling is what a real person does at that moment, as big as the moment is; never its name. "Real and expressive", not small and not staged.
  - A threat looks at its target. A result has its cause in the shot. A life-saving action is one fast, committed move, shown once.
  - The product is shown as it really works, from its real picture.
  - The world around the people is alive: bystanders who go about their day, heads that turn.
- One clip is one scene in one place. Inside it: shots back to back, each with its size, where the camera is, who is in frame, one action, and the line with how it is said.
- "Hook first" means the opening of the whole video, never every clip.
- The price is built from seconds: seconds times the model's rate, extras named one by one. No padding. His expectation: about $3 to $5 of filming for 30 seconds. If the first figure is high, find out why before defending it.
- Say the total and the figure at which you will stop. Nothing is spent before he says yes, and nothing past the stop without asking again.

## 6. References

- Consistency comes from references, not from describing people again in every prompt. Each person, place and product is one picture, made once and approved.
- A person's picture is them on an ordinary day: their face large enough to read, their clothes for the story, nothing of any one scene on them.
- Every prompt says what to take from each picture (the face and outfit from this one; the place and its light from that one, not its framing).
- A voice that must stay the same is carried the same way: a few seconds of it from an earlier clip go with the later ones.
- Casting is the one place Reed wants a say. Saved people are used only when he picks them.

## 7. Filming

- Everything is resumable: what has been made is never asked for, or paid for, twice.
- A few clips at a time, not all at once, so a fault shows before the whole budget is spent on it.
- Never restart or deploy the site while clips are being made.
- A check never stops a run: note the fault and keep going. The run stops only when it needs him (a provider account is empty, the stop figure is reached).
- Every paid step is written into `ops/SPEND.md` with his words of approval.

## 8. Check every clip before he does

- Look at every clip (a frame a second) and listen to it (the words heard against the words planned) before anything is shown.
- Remake only real faults: a wrong word, a wrong person, the product working wrongly, the action not happening. Never a remake for taste. "Finish, don't polish."
- A small fault that is left is written down and told to him with the delivery. It is not remade without him.

## 9. Deliver

- The cut goes to his Desktop, named so he can find it, with the earlier cut kept.
- With it: what it cost against the stop, what is known to be wrong, and what could not be checked. (An agent can measure sound but not hear it; say so.)

## 10. A round of notes

- Quote his notes in his words and number them. Each note is answered.
- For each note find the cause in your own direction first: the reading of the script, then the references, then the prompt, then the model, then the edit. Do not blame a guide line for a beat that was directed badly.
- Change only the clips the notes touch. Say which clips, why each, and the price; wait for his yes.
- A round replaces what it corrects. Keep the round before as a backup, never as a second set of instructions still in force.
- RP5 took three rounds. Round one fixed what the scenes meant (the men must watch her; dread by cutting back to them). Round two fixed how big the acting was. Round three fixed the hooks and one action. Expect the same order: meaning, then size, then detail.

## 11. Finish in the edit

- Sound follows the picture: a sound is loud when its cause is on screen, drops under speech, and stops when its cause stops.
- A jump in time is shown, with a card in a quiet, well-set type.
- Captions are small, the script's exact words, with the word being spoken picked out.
- Look at the frames where each thing lands before delivering. Build the finish so it can be made again from the same clips for free.

## 12. Put the lessons where they last

- Bugs met on the way are fixed and noted, not worked around in silence.
- What was learned goes into the site as a replacement of the line that was wrong, not as a new line beside it; one change, one reason, in a pull request he can read. Guides and rules change only with his approval.
- The handoff file's "NOW" block is replaced on every update; a durable lesson goes to memory, once.
- Say plainly what is proven on a real video and what is proven only on stand-ins.

## What never changes

1. The script's words are final.
2. Nothing paid without his yes; every spend logged; the estimate honest.
3. Small before big; one change at a time; replace, never stack.
4. Direct the beat, not the adjective.
5. References carry consistency.
6. Check it yourself before he sees it; fix real faults only; tell him what is left.
7. His words are recorded as he said them; a settled decision is not reopened.
8. Plain language in everything he reads.
