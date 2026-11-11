# Robustness night, 11 Nov 2026 (the LONG helper)

Everything here was done on the free stand-ins. No paid call, no merge, no deploy, nothing on the live site.

## In short
- A long narration no longer stops the run. It is read in parts in the same voice and joined. **PR #1553**.
- Stops now say the real reason, and a failed voice job is no longer counted as money spent. **PR #1554**.
- Several videos can be planned at once, switched off until you turn it on. **PR #1549** (written by a helper I briefed; I reviewed it).
- Three things still need one real paid run to confirm. They are listed at the end.

## 1. Long scripts
I pushed scripts of 300, 1,000 and 2,000 spoken words through Dialogue (House, and Movie on Omni), Narrated, Zack D, Presenter (a corner host in a cloned voice, and a UGC talker on Omni) and Song.

| Format | 300 words | 1,000 words | 2,000 words (about 13 minutes) |
|---|---|---|---|
| Dialogue, Movie | delivered | delivered | delivered: 42 to 63 clips, 835 s |
| UGC talker (Omni) | delivered | delivered | delivered: 57 clips |
| Narrated, Zack D | delivered | delivered | **stopped before; delivered now**: 48 to 56 clips, 770 s |
| Presenter, corner host | delivered | delivered | **stops**: HeyGen takes 10 minutes of audio at most (see below) |
| Song | not testable on the stand-ins (their song is always 24 s) | stops: lyrics over 4,960 characters, a real limit of one song | same |

What broke, and what I did:

1. **The narration was longer than its voice can read.** ElevenLabs v3 (the default, "Sarah") takes 5,000 characters a request; MiniMax takes 10,000. Your 12-minute script was 9,901. The run tried once more in the same voice and stopped. **Fixed (#1553):** words past the voice's limit are cut between sentences, each part is read in the same voice, and the parts are joined before the timing is read. I chose this over moving to another voice because the voice is a creative choice, and because a 2,000-word script (about 11,000 characters) is past MiniMax's limit too. It is priced once, by its characters, as before.
2. **Carry on ignored the video's voice.** After the stop you set a voice, and Carry on read in Sarah again. **Fixed (#1553):** it reads in the voice the video has now.
3. **One shot under a second failed the whole plan.** On a narrated or song video the plan was thrown away if any one shot started less than a second after the one before it. The prompt asks for one shot a sentence, so short sentences invite exactly that, and a 12-minute script has about 240 shots. Each miss cost a whole second answer, and two misses stopped the run. **Fixed (#1553):** that shot is left out in code and the picture before it holds. Nothing is asked again.
4. **A Presenter video over 10 minutes stops late.** The host's one HeyGen take can't be longer than 10 minutes. The run finds out only after the narration and the plan are paid for, then stops with a clear message. **Left:** splitting the host's take in two touches HeyGen and the cut, and I can't prove it without a paid run.
5. **Nothing grows faster than the script.** Time went to the real work (ffmpeg, the cut), in step with length: 2,000 words ran end to end in about two minutes on the stand-ins. The pause trim is the one part that slows more than in step: 600 pauses in a 12-minute narration took 17 s here against a 180 s limit. Fine at 2,000 words; worth watching beyond.

Can the plan be written at all for a 12-minute script?
- Tonight's real plans came to about 170 tokens a shot. A 12-minute narration is about 240 shots, so about 42,000 tokens of answer. The limit is 128,000, thinking included. **It fits, with room.**
- It would run out near 30 minutes of video (about 5,000 words). The site accepts scripts up to 50,000 characters (about 8,000 words), so a script that long would be paid for and fail. Not fixed: no one has sent one.
- Cost: about $1 to $2 of Claude for one plan answer at that length. A plan that fails its check is asked once more in the same job, and the run then tries one more job, so the worst case is four answers.
- The held PR #1528 (write shots scene by scene) was built for the older pipeline and isn't needed at 2,000 words. It becomes worth redoing only for scripts past about 5,000 words.
- The $86.82 first price is the honest "up to": about 720 s of clips, each counted once and once more.

Limits I found and left, because they sit above 2,000 words:
- A narration over 15 minutes (about 2,500 words) can't be timed: the timing step refuses files over 900 s. That is found after the voice is paid for.
- The timing read (Whisper) is allowed 30 minutes at most. The code's own notes record it running several times slower than real time on the test site under load. A 12-minute narration should fit, but only a real run will tell.

## 2. Every way a one-pass run can stop or wait
"Person needed?" means a person, not a retry, is what unblocks it.

| # | Stop or wait | What triggers it | Person needed? | My call |
|---|---|---|---|---|
| 1 | Start card (Make it) | The plan and looks are ready | Yes, it is the money OK. "Make without asking" presses it for the owner | Keep |
| 2 | Cast and places OK | Every look is drawn | Yes, by your rule of 4 to 5 Nov. It still waits under "Make without asking" | Keep. **Your call:** should "Make without asking" approve the cast too? |
| 3 | Song style card | A song with no style line | Yes, once | Keep. Option: use the brand's last style when nobody answers |
| 4 | Presenter's voice card | A presenter with no voice yet | Yes, once | Keep |
| 5 | Waiting for the owner's OK | An editor past the planning allowance, or a step past the approved price | Yes, money. Never the owner on the live sites | Keep |
| 6 | "The plan couldn't be made" | Two plan jobs failed, each already asked once more | Yes: each new try costs a plan | Keep. **Message fixed** (see below) |
| 7 | "Planning this change is waiting on the owner's OK" | The owner said no on a planning card | Yes | Keep |
| 8 | "… couldn't be drawn. Upload or pick a look in Cast" | A look is missing and nothing is drawing it | Yes | Keep |
| 9 | "X failed 3 times" (a look, a take, a timing) | The same item failed three times | Mostly no: it is the service being down | Keep the stop, since trying forever spends. With a cut already made it delivers without the item. Message left: it doesn't say why, and the progress card reads this sentence |
| 10 | "It stopped for your answer: … refused 3 times" | The safety filter refused one clip three times | Yes: the prompt must change | Keep |
| 11 | "This same prompt for clip N was blocked before" | A refused take, asked again (a one-pass run has nobody to reword it) | Yes | Keep. **Message fixed:** it now names the clip |
| 12 | "The narration (or song) didn't come out" | The service failed twice | Sometimes | Keep. Two of its causes are fixed (length, Carry on's voice) |
| 13 | "The narration runs past HeyGen's 10 minutes" | A Presenter video over 10 minutes | Yes | Keep. Found late (item 4 above) |
| 14 | "The lyrics are too long for one song" | Lyrics over 4,960 characters | Yes | Keep: it says what to do |
| 15 | "The presenter's take didn't come out twice running" | HeyGen failed twice | Usually | Keep |
| 16 | "The cut couldn't be made" | The cut was refused or its render failed | Yes | Keep. **Message fixed:** it gives the refusal's own words |
| 17 | Any step refused twice running | The same step refused two turns in a row | Depends | Keep: it shows the step's own reason |
| 18 | "It stopped after N turns" or "at $5 of its own time" | The run's own caps (40 turns, or 2 a clip up to 200; $5 for anyone but the owner) | Yes | Keep. A normal run uses about 10 turns at any length |
| 19 | A shot under a second in a timed plan | See finding 3 | No | **Now carries on** (#1553) |
| 20 | The watch of the cut fails | The watch job fails | No | Already fine: it delivers without the watch |
| 21 | A take misses a scripted line | The free listen | No | Already fine: made once more, then delivered with a note |

Messages I fixed (#1554), each from tonight's evidence:
- **The plan.** Video 370's plan failed on "The presenter: in a shot, but neither in the cast nor in roles". The stop said "left out or repeated a script line", which was not what happened: the code picked one of two fixed sentences. It now gives the check's own first words. It also said "Nothing was charged", which is not true in dollars: Claude bills each answer. That sentence is gone.
- **The cut.** A refused cut stopped the run after one try saying "a clip changed since", whatever the real reason. It now gives the refusal's words.
- **A refused take.** "This same prompt for this clip" did not say which clip. It does now.

Not changed: one refused clip also holds back any other clips still waiting to be made again in the same step. After the person fixes that clip and presses Carry on, they are made.

## 3. Spend words
There were two different faults behind "$0.99 spent" beside "Nothing was charged".
- **The failed narration.** Nothing was charged: Replicate does not bill a run that fails (the code already quotes its billing page). But the spend figure counted any failed job with no bill attached at its list price: 9,901 characters is $0.99. **Fixed on the counting side (#1554):** a run that failed at Replicate counts $0. Failures elsewhere that may have been billed still count.
- **The failed plan calls.** These were charged: Claude bills an answer even when our check then refuses it. The figure was right and the words were wrong. **Fixed on the words side (#1554).**
- Left: a failed Claude job's own line in the job list still ends "Nothing was charged; try again". That is true of the video's credits, not of your Claude bill. It is one shared sentence used by every provider, so I did not touch it tonight.

## 4. Several videos at once (PR #1549)
How the site runs: one API process, and three workers (media, Claude, local). The Claude worker makes one call at a time for the whole site, and a long plan can take many minutes, so six videos queue behind each other.

**The change (off by default):** a setting, `BS_CLAUDE_WORKERS`, gives the Claude worker that many lanes. A video's number picks its lane, so two lanes can never take the same job and one video's steps stay in order. A test runs two lanes as real threads and proves both. To switch it on, add `BS_CLAUDE_WORKERS: "6"` to the Claude worker in `deploy/next/compose.yml`.

**The 10-minute hang: not proven.** Ranked guesses:
1. Most likely, the API ran out of database connections. It has 15, and 40 request threads share them. Every picture and video on a page held one until its last byte was sent. With six videos open, the rest wait 30 seconds and fail. #1549 gives the connection back before the file is read. To confirm, look in the API log for "QueuePool limit of size 5 overflow 10".
2. A lock chain: making a cut locks the video's row while ffmpeg cuts the presenter's take. No minutes-long lock was found.
3. A deploy during a long Claude call takes the API down until that call ends. Compare the hang's time with the deploy times.

Ruled out from the code: the live streams hold no connection, and the worker holds no lock across a Claude call.

Risks left in #1549: two videos whose numbers fall in the same lane still wait for each other; several calls at once may meet Claude's rate limit (they are queued again, never lost); the zip download still holds its connection.

## What needs a real paid run to confirm
1. **A narration read in parts.** That two parts in the same voice join without an audible change of tone at the seam. About $1 for a 10,000-character script. This is the one I would run first.
2. **The plan call for a 12-minute script.** That Opus writes about 240 shots in one answer without a slip, and how long it takes (my guess is 10 minutes or more).
3. **The timing read of a 12-minute narration on the server**, inside its 30 minutes.

## What I changed
| PR | What | App code |
|---|---|---|
| #1553 | Long narrations read in parts and joined; Carry on's voice; a shot under a second left out | +86 −30, and the stand-in voice +29 −5 |
| #1554 | Real reasons in three stop messages; a failed Replicate run counts $0 | +27 −17 |
| #1549 | Claude lanes (off); file downloads free their connection | +23 −8 |

Each fix has a test that fails without it. The whole server suite passes on each branch.

## What I left, and why
- A Presenter video over 10 minutes (needs HeyGen in two takes; unproven without a paid run).
- Scripts past about 5,000 words (the plan would need writing in parts; nobody has sent one).
- A narration over 15 minutes paying for a voice it can't time (above 2,000 words).
- If a part of a long narration can't be started (the service says busy), the parts already started still run and are billed, about $0.50 at most. Rare, and stopping them isn't sure to save the money.
- Softer plan checks (too many people in a clip, a shot a little short for its line) still cost a second answer when they trip. I have no evidence they tripped tonight. The failed plan jobs' notes on the live database would show which checks do; that is a free read.
- Providers (pictures through Google): not mine tonight.

Scratch tests I used are in `.context/night/work/scratch/` (not in any PR).
