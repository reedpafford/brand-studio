# FOMO-Producer handoff (2 Nov 2026)

From FOMO-Producer (session_01FRDAYJHqLy8hY5r4z4KkD5) to FOMO-House-Builder, copied to Next-Lead.
This adds to `docs/next/harvest/fomo-producer.md` and DECISIONS rule 35.

Script names below (`prod/...`, `ui/...`, `song5/...`) were the FOMO-Producer's working scripts. Copies were on the throwaway branch `media/fomo-house-watch` under `scratch-tools/`, which may be deleted. The kept fallback tools are in `tools/fomo/`.

## 1. Batches 3 and 4: Reed's verdicts and what changed

### Batch 3 (projects 51–55, then remakes 56 and 57)

The scripts were made from Reed's reels DfF6P64pvpD (Reptilian) and DfLFWmjyvBB (Fired), plus "Odds", "She Stayed", and the song "Left Me for a Yacht".

**Script round.**
- Reed on my Odds variation: "way too far off… something about odds - with an edgy crazy punch, then the sell is 'your odds are better being a millionaire on the fomo app'".
- Reed on the song: "Not edgy enough… girlfriend swiping on raya". I rewrote it and he said "the song is good… take 1".
- On the CTA: "your cta is bad, but i will edit it".
- His rule: "IF there is a friend or mentor in a remake, it is kimchi". On Odds: "the payoff only needs one cta".

**Delivered cuts.** Reed: "The shorts are just bad. There's weird gasping all the time, you don't actually tell the story visually. Fomo is messed up on some screens, montages are forced, the 'copy these' videos aren't copied at all. The song one has better visuals. The shorts are just not entertaining, and feel too sloppy."

What I changed:
- Remakes now go through the site's reel import (POST /scripts/import/upload, then /import/read, 7 credits). That gives a true shot-by-shot copy; only the brand and cast change.
- I added a gasp check, but Reed later said "Don't worry about the gasping", and the ban was removed (#1093).

**Reptilian v2 and v3 (project 56).**
- Reed: "The lizard one is still not great… critically watch the reels and see if they make sense and are continuous".
- Then: "You need to watch at more FPS". 1 fps was rejected, so I now use 6 fps sheets with word timestamps.
- Then: "I just don't think emotions are captured, and it doesn't look good. You are meant to catch these and make these changes."
- Then: "The biggest gap is the acting and the shots… I also don't like the hook you put in. I don't feel like the video makes any sense. The shifting face/wardrobe is less important than the story". He raised the cap to $200.

**Reptilian v4 (project 56, rebuilt).** Reed: "v4 was much better". What changed:
- A new script where every scene sets up the next.
- A hand-written breakdown (`prod/director56.py` is the example) with one feeling and one action per shot.
- Clips of 6–11 s with reveals held, then a reaction.
- No added hook.
- Absent characters' sheets removed from clips.
- A made-up "FOMO" line muted.

**Fired v3.** This was a free re-edit: the cash-burning shot and the note were cut, and a time-jump flash was added.

### Batch 4 (projects 58–62, 2 Nov)

- **59 "Come Back When You're Successful"**, based on reel DfF5SCpT9kL. Reed: "video 2 is good". No change.
- **62 "We Ain't Broke No More"**, the song video. Reed: "the song is good". Before delivery I cut the empty bus shot and remade the ending (Mom child-sized, "Fogo").
- **58 "Ghostmode"** and **61 "Kiss Cam"**. Reed: "Video 1 and 3 has good moments, but sometimes scenes dont make sense (peanut falls on tray for some reason) I KNOW what its supposed to be saying, but we are missing little actions that connect clips. Things where characters refer to the screen or something like 'thats my face' i assume was supposed to show the coin on fomo and doesn't."
  - Ghostmode v2: I cut the peanut beat. A held, readable insert of @GHOSTMODE on Chase's phone was made by hand with `tools/fomo/insert_hold.py`. c5 was retaken with extreme close-up inserts, but they still came out about 0.5 s, so I used the hand-made insert.
  - Kiss Cam v2: c3 retaken with a big insert of the KISS CAM coin (Carl's face) before "That's my face".
  - Before delivery I'd already retaken Kiss Cam c1, where the jumbotron made it look as if Carl and Brittany kissed.
- **60 "Milk Girl"**, a shot-by-shot copy of reel De3dl-KR4VH. The c1 opening was refused as a look-alike 14 times; it got through with no reference images. One take came out in Chinese and was retaken with a "Language:" line. c3 said "Fogo" and was retaken. **No verdict from Reed yet.**

**Pending verdicts:** Milk Girl, Ghostmode v2 and Kiss Cam v2.

## 2. How I make a video end to end

**Site and account.** The LIVE site is https://srv2091584.hstgr.cloud with the API at /api, logged in as "QA Owner". Its session cookie stays out of code, logs and chat, and is never sent to other hosts.

**The test site.** https://thisisatestingenv.online is on stand-ins (FAKE) until Reed switches it back. Its fomo brand has only Goth GF. Its login comes from Reed and is never written down.

**How I drive it.** Everything goes through the API with small Python scripts (`prod/bs.py` is the client), never the browser UI. The flow:

1. **Script.**
   - POST /scripts {brand_id:1, title, description, notes, text}
   - PUT /scripts/{id}/drafts/0 {text, target_seconds}
   - POST /scripts/{id}/drafts/0/approve
   - POST /scripts/{id}/cast/read, then poll until it's done
   - Cast: POST /scripts/{id}/cast/{slot}/lock {library_item_id}, then PATCH the slot's description (the look's base text plus the per-video outfit). DELETE duplicate slots.
   - POST /scripts/{id}/publish, then POST /scripts/{id}/drafts/0/produce, which returns the project_id and the breakdown job.
2. **Breakdown.**
   - GET /projects/{pid}/breakdown, edit it, PUT it back. `prod/restructure.py` splits clips, sets per-shot screen_ids and swaps words.
   - A PUT returns "problems". Fix every non-"Advice" one, e.g. the cast check: a shot whose script lines name a character must include that character's ref ("char:NNN" once the looks exist).
3. **Looks.**
   - GET /projects/{pid}/assets/missing-looks, then POST make-missing (`prod/mklooks.py`).
   - Watch the sheets. A bad look can be merged into another slot for free: POST /projects/{pid}/assets/slots/{a}/merge {into_slot_id:b}. Then POST approve-all.
4. **Stills.**
   - POST /projects/{pid}/storyboard {per_shot:false}, then render the frames (`prod/stills.py`).
   - Redraw a wrong still with `prod/change.py pid frame_id "note"` (4 credits).
5. **Clip prompts.** `prod/prompts.py`, then `liven.py`, then `fixcase.py`. Then read every prompt and fix it by hand (PUT /projects/{pid}/clips/{id} {prompt, references}):
   - "invented trading screen" means a fake red screen. Rewrite it as red light on the face with the phone turned away.
   - "Two quick cuts:" risks a split screen.
   - Keep-line outfits.
   - The FOMO pronunciation hint.
   - Absent characters' sheets must not be attached.
6. **Takes.** `TRIES=3 prod/takes.py pid [clip…]` generates and downloads to tk{pid}/. Refused takes are free.
7. **Cut and review locally.**
   - `prod/localcut.py out.mp4 tk{pid} c1 c2 … [mute=c8:2.2-3.08] [duck=…]` makes the 480p cut.
   - Songs: `prod/cutsong.py pid song.wav '[[a,b],…]' out.mp4`, with env `CUT=c2:1.9-3.6` to trim a dead span.
   - Watch with `tools/fomo/watch6.py`: 6 fps sheets plus the transcript. Check every line against the script and mute anything made up.

**Cost.** A typical 50–60 s video is about 70–95 credits, $7–10 (1 credit = $0.1028):
- Looks: about 2–4 credits each.
- Stills: about 1–2 each.
- Breakdown and prompts: about 3–5.
- Clips: about 1 credit per second.
- One or two retakes.

**Time.** About 1.5–2 hours of wall clock for a batch of five run in parallel: about 10 min for breakdowns, 5 for looks, 5 for stills, 15–20 for takes, plus review.

**Done by hand outside the app:**
- Muting made-up lines.
- Trimming dead spans.
- Song timing (KIE Suno V6 via `song5/make.py`; the key comes from the env KIE_API_KEY and is never printed). Trim the song so the vocal starts at 0.
- Phone-screen inserts and moving charts (tools/fomo).
- No captions; Reed hasn't asked for them.
- Spend is logged in ops/SPEND.md via docs-only PRs (the latest is #1199, $226.53 of the $250 cap).

## 3. Phone-insert tools

PR #1226 (`tools/fomo/` on next) has a README.
- `insert_hold.py clip at screen.png fx fy out.mp4`: a readable held insert.
- `onphone.py in out ref.png start:anim_dir`: moving charts or a still screen fitted onto the phone.
- `chart_anim.py climb|crash|rocket secs out.mp4`: animated chart pages.
- `watch6.py`: review sheets.

## 4. Tone notes, cast, screens

**Tone notes.** These are the live brand 1 tone_notes, which I copied verbatim from the site:
- FOMO only shown winning.
- The real UI, with made-up figures.
- Loading screen: dark with the eyes and logo.
- FOMO is the saviour, sold in conversation, mostly copy-trading.
- Say FOMO as "FOH-moh", written in capitals in lines.
- Payoffs vary.
- A white flash on time jumps.
- More action, keep it edgy.
- End with a yes/no question, then the end line.
- 480p.
- Charts move with the story; a dip is fine if it recovers.

The end line is "Want to trade like me? Download fomo through the link in my bio."

Also from Reed:
- He sometimes wants one CTA only, with no question.
- Songs have no question.
- In a remake, the friend or mentor is always Kimchi.
- Story logic is per story, never brand-wide.

**Cast** (live library, brand 1):

| Id | Character | Base look | Notes |
|---|---|---|---|
| 12 | Wyatt | Early-20s, curly dark-brown hair | The hero |
| 14 | Kimchi | Short straight black hair | Friend or mentor; always him in remakes |
| 1 | Goth GF | Black bob with blunt bangs | Look-alike refusals; fix by restyling her hair (bun or ponytail, no bangs) |
| 24 | Goth GF 2 | Long layered hair with a purple streak | Original variant |
| 2 | Mogging BF | Platinum hair | Rich rival; was Chase in Ghostmode |
| 3 | Carl | Sandy hair | Snore Guy, Kiss Cam |
| 13 | Clavicular | | Used only in the song "One Go" |

- Library outfits override the per-video wardrobe in stills and takes. Put the scene's outfit in the Keep line and the slot description.
- Batch-4 one-off looks belong to their projects: Marcus, Maya and the Kid (58); the Salesman (59); Brittany, the buff guy and Carl's date (61); Andre and Mom (62).

**Real screens** (live brand screens):

| Id | Screen |
|---|---|
| 3 | Home |
| 2 | Home (rich), $348,920.15 |
| 5 | Token chart up |
| 4 | Token chart down (loss; avoid showing it) |
| 1 | Desktop |
| 9 | Desktop (real UI) |
| 14 | Coin chart up |
| 15–17 | Parents: $1,260, $9,800, $46,500 |
| 18–27 | Batch 3 per-beat charts |
| 10, 8 | SNORE coin pages |
| 11–13 | Home rich: $612k, $1M, $740k |

Batch 4 screens:

| Id | Screen |
|---|---|
| 28, 29 | Ghostmode: +$212.40, $63,417.29 |
| 30 | Spotlight with @GHOSTMODE (Chase's phone) |
| 31 | Home, $5,004,190.88 (Marcus) |
| 32–34 | Comeback: +$1,180, $27,640, Home $412,906.31 |
| 35, 36 | Coming Up: +$1,940, Home $186,730.44 |
| 37 | Home, Milk Girl, $86,412.07 |
| 38, 39 | MILK GIRL coin (her face), and the same coin climbing |
| 40, 41 | KISS CAM coin (Carl's face), and the same coin climbing |
| 42 | Home, Kiss Cam, $97,604.12 |

- Tags: chart-up, coin, mobile for charts; home, mobile, portfolio for balances.
- How they're made: `ui/make_val.py` (coin chart with a figure), `make_home.py` (balance), `make_coin.py` (a character's face as the coin icon), `make_spot.py` (the Spotlight row with a chosen trader). Upload with `prod/addscreen.py path "name" tags`.
- Never reuse $348,920.15 or another video's figure. Take each figure from its beat.

## 5. Open with Reed

- **Pending verdicts:** Milk Girl, Ghostmode v2, Kiss Cam v2.
- **Paid work is paused** until Reed switches the test site back from stand-ins (the Producer's instruction).
- **Budget:** cap $250, spent $226.53, $23.47 left. Ask Reed before going over.
- **The House-style before/after test script** I proposed: "It's Friday" with Goth GF.
- **Ideas he liked that aren't made:** none outstanding.

## 6. Reed's habits

- He watches the actual cut, usually on his phone, and gives notes in one burst. Story and clarity come first ("I don't feel like the video makes any sense"), then acting and shots, and continuity last ("shifting face/wardrobe is less important than the story").
- He expects you to catch problems yourself, fix them, and only then deliver ("You are meant to catch these and make these changes"). Never send a cut you haven't watched at 6 fps with the words.
- He dislikes:
  - Hooks or extras he didn't ask for.
  - Hard rules where he wanted suggestions ("we said no hard rules, just suggestions").
  - Story logic pushed brand-wide.
  - Forced or default numbers.
  - Full-screen app screens.
  - Gasping (now dropped).
  - Montages that feel forced or choppy.
- In reports: plain language, short, and say plainly what's still weak. He asks "you understand why, right?" and "are these pushed to the director?" Always route lessons to the Director via the Producer and confirm with the PR number.
- He references Nate's reels (docs/references/nateassets) as the bar: fast but legible cuts, edgy and funny.
- He approves spend in chat ("Raise the spend to 200", "Raise to $250"). Log it with his words.

## 7. Scratchpad kept

The working scripts are on branch `media/fomo-house-watch`, in `scratch-tools/`:
- The API client and pipeline: bs, takes, prompts, liven, fixcase, fixlib, mklooks, stills, change, restructure.
- Cuts: localcut, cutsong.
- Screen makers: make_val, make_home, make_coin, make_spot.
- The song maker (KIE, key from the env).
- director56.py, the hand breakdown that made Reptilian v4 work.
- The batch-4 scripts.

The cookie and login files are NOT included.
