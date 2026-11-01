# The site's director (plan only, nothing built)

**For Reed, in short.** You give a video a brief, a script or a reel, and the site's director (Claude) builds the whole video on its own, the way the agents do today: script, plan, cast, stills, clip prompts, takes, its own review of each take, redos of the clips that failed, and the final cut. It then delivers the video with what it cost and a short note on what it decided. You watch it and say what you'd change in the chat; it goes back, makes those changes and delivers again. It spends without asking while it stays inside the video's budget, and asks you only when a press would go past it (the same "Hold requests" approval you already have). You can still set things yourself: lock the cast, the look, the length, the song, a screen or the end line, before or during a run, and it builds around them. Editors can use it too, on published scripts only. It starts out knowing what the agents have learned so far (general craft, plus each brand's own notes). The step screens stay as they are, as the "look inside" view, so you or an editor can still change anything by hand.

Status: plan for the Producer to publish to Reed. Nothing here is built. Reed's answers (30 Oct): "Act on it's own, it has been really good on it's own"; "Editors too"; "I just want the flow to be how it has with the agents… If i notice anything, i say it, it goes back and makes those changes."; "I would still like to be able to set the cast, and other things like that."

## 1. How it works

1. **Start:**
   - **Owner:** a brief, a script, or a reel to adapt. From a brief, it writes the script and pitches it first (titles, payoff, the yes/no question), then builds on your go.
   - **Editor:** a published (approved) script only. There's no script check-in, and the script's words are locked. Asked for a line change, it says the words are set for this script and offers what it can change instead: delivery, visuals or pacing (never a dead end, never "ask Reed").
   - **Locks:** before or during a run, the owner or editor can lock any choice: brand, cast and looks, look/style, length, song, specific screens, the end line. Locked choices are fixed; the director builds around them and never changes them (it may say in the delivery note if a lock caused a problem). Unlocking hands the choice back.
2. **It builds the video itself**, step by step, pressing the site's own actions:
   - script (owner's videos only): writes or revises it as a new version (rule 19: a published script's words are never edited in place);
   - plan (scenes and shots), cast and looks, stills, clip prompts;
   - takes: makes them, reviews each with the take check (docs/next/take-review-checklist.md), and redoes only the clips that failed;
   - final cut.
3. **Delivers:** the cut, what it cost, and a short decision note.
   - **Craft choices** it was unsure of (framing, a take, wording of a prompt, timing) it decides itself and explains in the note; any of them can be undone by asking.
   - **Story choices** (the ending, cutting a character, a key line) and anything over budget it asks about first, mid-build. Over budget becomes a held request.
4. **Revisions in chat:** you or an editor say what to change. It makes the changes in order (script version, owner only → plan → the clips that went out of date → re-cut) and delivers again.
5. **Look inside:** every step screen still works. A change made by hand is something the director sees and builds on.
6. **Who:** the owner and editors. On a brand's video it's work, so it counts against the video's budget, not the editor's Quick-clip allowance (DECISIONS rule 5).

## 2. Money

- **Spends without asking** while it stays inside all three: the video's budget, a director budget for its own Claude time ($5 a video as a ceiling, owner-set in Limits; Reed: "Ideally less would be better", so we measure the first few videos and aim well under it), and the per-video cap (never bypassed).
- **Past any of them**, the press becomes a held request for the owner, exactly like an editor's over-budget press today. The director waits on that step and says so.
- **A running "up to" cost** shows on the video while it works, and the delivery shows the real total.
- **Cost habits copied from the agents:** check prompts and stills before making takes, redo only the failed clip, fix in the cut when it's free, keep videos 40–50 s, retry look-alike refusals (free).
- **Rough estimate, not measured:** a full build is about $2–6 of Claude time, plus about $0.05–0.20 a chat message afterwards. Stills and takes cost what they cost today, on top.

## 3. Starting with the agents' knowledge (the harvest)

Before the director is built, the agents write down what they've learned, so it starts where they are:

- Each agent adds to `docs/next/agent-knowledge.md`, split into **general craft** and **per brand**: FOMO-Producer, Song-Producer, Writer, the Director's own notes, and QA-Live.
- The Director folds the general part into rules.md and the step prompts, and the brand part into each brand's notes.
- **One story's own logic** (why a fall happens, the stakes, the payoff) stays with that video and never becomes a rule. Reed was explicit about this.
- After launch, feedback is sorted the same way: craft → rules (via the Director), brand → brand notes, story → that video only.

## 4. The agents' loop it copies (FOMO-Producer, 30 Oct)

Items marked *(fomo)* are fomo's brand notes; the rest is general craft.

1. Write the script (titles, payoff, the yes/no question).
2. Cast read, then lock looks.
3. Breakdown: fix screens *(fomo: the real app screens)* and cast per shot, flashes on time jumps.
4. Stills: redraw a wrong one with "Change this".
5. Clip prompts: camera style, no red screens *(fomo: the brand only ever wins)*, no words that read as a spoken line.
6. Takes: review each (transcript plus a frame strip), redo only the failed clips.
7. Cut, rewatch the whole cut, deliver with the cost.

**Most frequent fixes, and the site action each maps to:**
- An unscripted or mispronounced word *(fomo: "FOH-moh")* → redo the clip with a note, or mute that span in the cut.
- A wrong or static screen → set the shot's screen (plan) and redo the clip.
- A look-alike refusal → change the scene or look in the clip prompt, retry (free).
- Glowing eyes or extra people → a Keep note, redo.
- A script change → new script version, then plan, then the stale clips' prompts, in that order.

**Gap:** the agents still do some fixes by hand, outside the site. Each becomes a site action, and the director uses it in its loop on its own as soon as it's built (order and sizes in §6).

## 5. Prompt side and safety (Director, 30 Oct)

- **Reuse the site's actions as tools**, each with its own prompt, schema and checks. The director never writes a clip, breakdown or still prompt itself.
- **About 6–9k tokens a call** (rules and brand ~3k, the video's state ~3–5k), mostly cached.
- **Safety is enforced by the server, not the prompt:** every paid tool goes through the same budget, hold, cap and rule 32 checks as a press; a hard limit on calls per job; no tool can change Limits or another person's work; every action is logged on the video.
- **Evals:** a free set with stand-in tools first. Paid evals only with the Producer.

## 6. Build order

| # | Piece | Size | Notes |
|---|---|---|---|
| 1 | Take check (post-reset) | (its own) | The director's self-review is built on it. |
| 2 | Harvest | S | Agents write agent-knowledge.md; the Director folds it in. Docs only. |
| 3 | Server tool layer: each existing action as a tool with its price check, budget and permissions | M | Calls the same functions the routes call; no new money paths. |
| 4 | Director job: builds a video end to end, then takes chat revisions | M | **First slice.** Same job and credits system as other Claude calls. |
| 5 | Chat panel and running cost | M | 390 first. |
| 6 | Locks on a video's choices (cast and looks, look, brand, length, song, screens, end line) | S | Stored on the video; the director's tools refuse to change a locked choice. |

**The agents' hand fixes, as site actions** (the director uses each automatically once it's built, in this order):

| # | Action | Size | Notes |
|---|---|---|---|
| a | Pick the best take per clip | S | From the take check's results; earlier takes stay pickable (rule 21). |
| b | Mute a span in the cut | S | The agents' most common free fix (an unscripted word). |
| c | Splice a correctly said word from another take | M | Same clip, another take's audio over the span. |
| d | Retime song takes to the song, end line over the instrumental | M | Song videos only. |
| e | The moving chart on the phone | M | Builds on #1059's screen figures. |

**Recommendation on the four-step flow:** fold it into this. Build the take check and the director's self-approval back end now, keep today's step screens as the "look inside" view, and regroup them into four steps later if it still helps.

## 7. Reed's answers (30 Oct)

1. **Director budget:** "Ideally less would be better." Measure the first few videos, aim well under $5, keep $5 as the ceiling (§2).
2. **Script:** "Editors should only be able to use approved scripts (published ones)." Editors build from published scripts with the words locked; for the owner starting from a brief, it pitches the script first and builds on go (§1).
3. **Unsure mid-build:** craft choices it decides and explains in the delivery note; story choices and anything over budget it asks first (§1). Reed: "All of that sounds good."
