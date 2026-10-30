# Director chat (plan only, nothing built)

**For Reed, in short.** Each video gets a chat panel. You (or an editor) talk to a Claude "director" that can see everything about that video: the script, the plan, the cast, every still and take, the AI check's notes and the brand's notes. It answers like the agents do: it looks across all the steps, says why, asks when it isn't sure, and remembers the conversation for that video. When you agree, it does the work by pressing the site's own buttons for you: rewrite a line, change a plan beat, recast, "Change this…" on a still or clip, make another take, re-cut. Every paid press shows its "up to" price first and goes through the same budgets, approvals and caps as a press you make yourself. It never edits a published script's words. It works the same way for every brand: the general craft rules are shared, and each brand's own notes, screens and cast are added on top. A chat message costs about $0.05–0.20 of Claude time; a video's chat has its own small budget. It comes after the four-step flow and the take check, because it uses both.

Status: plan for the Producer to publish to Reed. Nothing here is built. Reed's words: "i really want the outputs and thinking to work how the agents do per video".

## 1. What it is

- **Where:** a side panel on every video (a sheet at 390), open on any step. One conversation per video, kept with the video.
- **Who:** the owner, and the editor who made the video (the same people who can change it today, flows "Who changes a video"). Others can read it.
- **What it sees:** the video's whole state, read fresh each message: script version and lines, the plan (scenes and shots), cast and looks, stills and takes (with the take check's results, Advice and "Change this" notes), Video settings, brand notes (tone, Do/Don't, CTA lines, screens), spend so far and what's left.
- **What it can do:** only the site's existing actions, called as tools, the same server routes the buttons use:
  - script: suggest a new version of lines (a draft for the owner to approve; never edits a published script, rule 19 and 31);
  - plan: change a beat or a shot's action, split or join a clip;
  - cast: recast a role, make or pick a look;
  - stills and clips: "Change this…" with a note, make another take, pick a take, approve;
  - final cut: re-cut with the approved takes.
- **Money:** every paid action shows its "up to" price in the chat and waits for a yes before it runs (one tap). It goes through the same checks as a press: the video's budget, Reed's "Hold requests" approvals, the per-video cap (never bypassed), rule 32 (never below the charge).
- **Review, like the agents:** when a take finishes it reads the take check (docs/next/take-review-checklist.md) and proposes the fix ("Take 2 says 'Fobo' at 0:04. Make another take with the pronunciation note? Up to 6 credits."), never acting on its own.

## Every brand: three layers

The chat knows three things, kept separate so it works for any brand, not just fomo:

1. **General craft (the same for every brand):** the rules files (rules.md), each step's own prompt, the looks. Movement, readable expressions, no split screens, a flash on a time jump, one payoff per montage clip, quotes never changed.
2. **The video's brand:** its notes and tone, Do/Don't and never_say, its real screens (and figure spots), its cast, its CTA lines and end line.
3. **This story's own logic (this script only, never a rule):** why a fall happens, what the stakes and payoff are, the yes/no question. Reed was explicit that these never become general rules.

When Reed's feedback is about craft, it belongs to layer 1 (a rules change, via the Director). When it's about a brand, it goes to layer 2 (the brand's notes). When it's about one story, it stays in layer 3, the chat's memory for that video.

## How the agents work today (FOMO-Producer, 30 Oct)

The chat copies this loop, one video at a time. Items marked *(fomo)* are fomo's brand layer; the rest is general craft:

1. Write the script and pitch it to Reed (titles, payoff, the yes/no question); he approves.
2. Cast read, then lock looks.
3. Breakdown: fix screens *(fomo: the real app screens)* and cast per shot, flashes on time jumps.
4. Stills: redraw a wrong one with "Change this".
5. Clip prompts: camera style, no red screens *(fomo: the brand only ever wins)*, no words that read as a spoken line.
6. Takes: review each (transcript plus a frame strip), redo only the failed clips.
7. Cut, rewatch the whole cut, send to Reed with the cost.

**Decides alone:** bad takes, mutes, prompt wording, retries (look-alike refusals are free). **Asks Reed:** story or ending changes, new rules, anything over $15 a video or past the cap. The chat keeps the same line: it fixes craft, and asks about story and money.

**Most frequent fixes, and the site action each maps to:**
- An unscripted or mispronounced word *(fomo: "FOH-moh")* → redo the clip with a note (Change this, Make another take), or **mute that span in the cut**.
- A wrong or static screen → set the shot's screen (plan) and redo the clip.
- A look-alike refusal → change the scene or look in the clip prompt, retry (free).
- Glowing eyes or extra people → a Keep note, redo.
- A script change → new script version, then plan, then the stale clips' prompts, in that order (otherwise "made for an older breakdown").

**Gap:** two of the agents' fixes are done outside the site today: muting a span in the cut, and compositing a screen onto the phone. The chat needs both as site actions (a "mute 0:04–0:05" on the final cut; #1059's screen figures cover part of the second).

**Memory it keeps:** Reed's tone rules (brand notes), his feedback on this video, earlier takes per clip (pick the best), and his standing preferences: action and camera movement, varied payoffs and story logic per story (general), and fomo only ever winning on its real UI *(fomo)*.

**Spend:** mostly takes (1 credit a second), with redos adding 30–50%. It keeps that down by checking prompts and stills before making takes, redoing only the failed clip, fixing in the cut when it's free, and keeping videos 40–50 s.

## 2. What makes it feel like the agents

- **Reasons across steps:** "the payoff reads small because the plan's beat 4 has no balance figure; I'd add one, then redo clip 4."
- **Explains why** before each proposal, in plain words, and names what goes out of date.
- **Asks when unsure** (two good options, or anything touching the script's words), instead of guessing.
- **Remembers** the conversation and the decisions made on this video ("you said no red screens"), so later fixes follow them.
- **Batches** a fix plan ("three changes, up to 18 credits total") instead of one press at a time, and you can say yes to all or pick.

## 3. Cost

- **Claude per message.** It uses the same Claude model the site already uses. Each message sends about 6–9k tokens (rules and brand ~3k, the video's state ~3–5k for a 60 s video), mostly cached after the first message. One message is usually 1–3 Claude calls (read, maybe a tool call, answer). Rough estimate, not yet measured: **about $0.05–0.20 a message**; a busy video's chat of ~30 messages is about $2–6. The paid actions it presses (stills, takes) cost what they cost today, on top.
- **A per-video chat budget**, e.g. $5 (about 49 credits) by default, owner-set in Limits, shown as "up to" like everything else. Past it, the chat says so and stops; the buttons still work.
- **Editors:** chat on a brand's video is work, so it counts against the video's budget, not the Quick-clip allowance (DECISIONS rule 5).
- **Keeping it small:** cache the rules and brand notes; send only the state that changed; the chat proposes and the existing prompt families do the writing (it calls "Change this…", it doesn't write clip prompts itself).

## Prompt side (Director, 30 Oct)

- **System prompt:** rules.md (~1.2k tokens), the brand block, the video's look and its one-line description, and a short chat.md: you're this video's director; act only through tools; say what a paid action costs first; plain words. The steps' full prompts (7–9k tokens each) stay out, because the tools carry them.
- **The video's state** goes in the conversation, not the system prompt, so it caches: the numbered script, plan scenes, the shot list (one line each), clips with status, and what's selected.
- **Reuse, never re-decide:** it only calls the site's actions ("Change this" on a scene, shot or clip, "Redo storyboard", "Make clips", "Improve", the look switch, "Check this"). Each keeps its own prompt, schema and checks. The chat never writes a clip, breakdown or still prompt itself.
- **Rule 19:** the script's words are read-only to the chat. It can suggest a line change in words; only the owner applies it, as a new version.
- **Safety in code, not in the prompt:** tools are read-only by default; a paid tool runs only on a Yes click with its price shown, never on the chat's own say-so; a per-chat credit cap is enforced by the server. The biggest risk is paid calls stacking up ("helpfully" redoing five clips). The second is drift from the rules (softening a gag, suggesting a split screen); its advice passes the same checks as the steps' Advice.
- **Evals:** a small free set with stand-in tools (e.g. "make the payoff bigger" → calls Change this on the right shot, no paid call without a Yes). Paid evals only with the Producer.

## 4. Build pieces and order

| # | Piece | Size | Notes |
|---|---|---|---|
| 0 | Take check (post-reset) and the four-step flow | (their own) | The chat reads the take check's results; build those first. |
| 1 | Server tool layer: each existing action wrapped as a tool with its price check, budget and permissions | M | Thin: calls the same functions the routes call; no new money paths. |
| 2 | Chat job: a worker job per message (state snapshot, cached rules, tool loop, a hard per-message call limit) | M | Same job/credits system as other Claude calls; refusals and "service busy" handled like any job. |
| 3 | Chat UI: panel/sheet, proposals with "up to" prices and Yes/No, progress while it works | M | 390 first. |
| 4 | Memory: the conversation and a short "decisions" list kept per video | S | Stored with the video; nothing shared across videos. |
| 5 | Safety: rule 19 guard, owner/maker only, no tool can change Limits or another person's work, every action logged | S | Tests per tool. |
| 6 | Cut fixes as site actions: mute a span in the final cut (today done by hand outside the site) | S | The agents' most common free fix. |

Rough total: about the size of the four-step flow (pieces 1–3 the bulk). First slice: read-only chat (explains, proposes) with "Change this…" and "Make another take" as the only tools.

## 5. Open questions for Reed

1. Per-video chat budget: $5 default? Visible to editors as credits.
2. Should it ever act without a yes for free actions (pick a take, approve a clean still), or always ask?
3. Editors too, or owner only at first?
4. Can it suggest script line changes as a new draft for you to approve, or should it never touch the words?
5. One chat per video, or also one per script (for writing)?
