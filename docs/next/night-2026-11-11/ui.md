# Night UI pass, 11 Nov 2026 (helper: UI)
Branch `night/ui`, worktree `.context/night/wt-ui`. **PR #1556** into `reedagents/clean-look` (so it sits on top of #1545 → #1544 → #1543). Look and feel only: no server change, no paid call, nothing merged or deployed.

## The three open PRs: what they do, and are they safe to merge
All three: GitHub checks green on the first try, each builds, and I looked at each on the stand-in preview at 1440 and 1960.
- **#1543 Home looks like a studio** (`reedagents/home-look` → `next`). Four big style posters with real frames, the poster fan over a larger headline, the floating words box, loading placeholders, the run card's clock and moving bar. **Safe.** It adds about 1.1 MB of sample pictures and clips to the server, so it deploys with a restart.
- **#1544 The director's thinking shows as it plans** (→ home-look). The plan call asks for its thinking summary; the worker keeps it in a small file; the card reads it every 2 s. I read the server change: the file is closed in a `finally`, a failed write is logged and skipped, a 400 falls back to the old request, and only a running Claude job's file is ever read. **Safe to merge, but unproven**: it has never run against the real API (the PR says so). The first real plan is the test; if the summary never arrives the card still shows the clock, the bar and the plan so far.
- **#1545 The whole app in one clean frame** (→ live-thinking). Rail on a grey canvas, the page a rounded panel that scrolls on its own, rounder corners, soft pills. **Safe only together with #1556**, or expect fault 1 below.
- **Order:** #1543, then #1544 (`gh pr edit 1544 --base next`, rebase), then #1545, then #1556, each retargeted to `next` after the one below merges. A trial merge of `next` (2c326124) + all four had no conflicts (`server/app/worker.py` merged by itself); web typecheck, lint and 924 tests pass on it, and so do the thinking, Claude-client and worker server tests. I did not run the whole server suite on the merge.

## Faults I found in the stack (all fixed in #1556)
1. **The window itself could scroll (#1545).** The page scrolls inside the panel, but words hidden for screen readers were still placed against the window. A Scripts list longer than the window made the whole frame scroll too. Fix: the panel is `relative` (one word, `web/src/shell/Shell.tsx`). This was also why the Usage browser test ("no sideways scroll") failed about one run in three on this Mac: 9 of 25 on #1545's code, 7 of 25 on mine before the fix, 0 of 40 after. GitHub's slower machines did not hit it.
2. **A frame's outline was cut** at the left edge of the run card's strip.
3. **The "being made" light only reached the chat card**, not the Clips tab (a still grey block there).
4. Smaller: chat cards had two corner sizes after #1545 (10 and 12 px); page headers sat 4 to 8 px off their content; Usage capped some sections at 1100 px beside a table that wasn't.
Not a fault: black marks at the panel's corners in screenshots taken with Playwright's old headless browser after a dialog opens. Real Chrome does not draw them (checked).

## What #1556 changes, screen by screen
- **Every screen:** buttons dip when pressed; dialogs rise in, side panels slide in, phone sheets come up, the dim fades in; toasts are a white card that rises in; loading placeholders catch a moving light (no blink); error banners are a soft tint with no red outline; rail rows ease their colour.
- **A video's page:** "Planning", "Making the clips" and "Thinking" are crossed by a slow light while the director works; the thinking window glides to the newest words; the clip being made shimmers in the strip and in the Clips tab; the chat's "working" dots pulse. A stopped or failed run is a plain card with one small red icon (was a red band and a red edge), and a run that stopped at the plan holds no empty gap. Chat cards share one corner size.
- **All videos:** centred 1280 px column at 1960; cards have the card corner and lift under the pointer; the header lines up with the grid; the filter's picked segment uses the shared shadow.
- **Library (Characters, Places, Products, Footage, Presenters, Brand kit):** same centred column; header, tabs and content start on one line.
- **Settings, Team:** same centred column; content lines up with the title.
- **Usage:** every section the same width.
- **Home:** nothing new of its own (it inherits the press, the placeholders and the dialog motion).
- **Sign-in, set-up, invite:** a white panel on the grey canvas, like the app.

## How it is built (lean)
- 36 files, +112 −93, **net +19 lines**. No new dependency or component.
- The motion is 19 lines in `web/src/styles/index.css`: `shimmer`, `text-shimmer`, `animate-dots`, `animate-sheet`, `animate-side`, `lift`, and one rule so every `<button>` dips (in the base layer, so any class still wins; not for a full-screen scrim).
- Removed in exchange: 3 hand-written gradients, 4 blinking placeholders, 10 `rounded-[10px]`, 6 `border-[#c9ccf6]`, 5 `max-w-[1100px]`, a hand-written shadow, the hard-coded greys and pinks in the run card.
- One token changed: `--danger-soft` is paler (text contrast on it goes from 4.5 to 4.8).
- Reduced motion: loops stop, panels appear at once, the new press rule is off.

## Checks
Typecheck and lint clean; 924 unit tests; browser suite 85 of 85 on the final code (run locally; no test file changed). GitHub's checks on #1556 are all green (browser tests, server tests, lint, guides guard).

## What I would still improve (not done)
- About ten small tinted notes in `clips/ClipOpen.tsx` (and a few elsewhere) repeat the same class string with all-red or all-amber words. One shared note component would calm them and delete code.
- A run that stopped at the plan says "0 of 0 clips made". Those are the server's words (I changed no server code).
- The clock on a long wait reads minutes only ("185:45 so far"); past an hour it should say hours.
- Needs you shows its title twice (page bar and heading).
- On the centred pages the header's bottom line stops at the column's edge (Usage already did this). Fine, but a full-width line would look more finished.
- The rail marks the current main row with a white pill and the current folder and video with grey. Deliberate-looking, but two idioms.
- Three kinds of empty state exist (the dashed frames, the bordered card with an icon, plain words).
- About 180 hand-made `<button>`s keep their own hover styles. They all dip now, but their hovers differ.
- Text boxes use the keyboard outline when typed in; only Home's box and the chat box have the indigo edge and halo.
- Not looked at: the Cut editor, the older script flow, every dialog in every state, the editor (non-owner) view.

## How to view it
- Pictures: `.context/night/ui-shots/before/` and `after/` (same names; `-1440` and `-1960`; `x-*` are things in use: dialog, side panel, toast, hover, reduced motion, phone). `ui-shots/run/` is a stand-in run watched as it went.
- Live, free stand-ins: `.context/night/uirun/start.sh` (API on :8081; `WORKER=0` leaves a step hanging so the wait can be seen) and `cd .context/night/wt-ui/web && npx vite --config vite.local.config.ts` (:5181). Sign in as the e2e owner (`web/e2e/helpers.ts`). Both were left running when I finished and stop on their own within two hours.
- Saved states to swap in as `uirun/data/dev.db` (stop the API first): `frozen.db` (video 12 planning, 7 waiting on a question, 5 and 6 stopped, the rest delivered), `waitok.db` (12 waiting for the OK), `making.db` (12 with a clip being made).
- Retake the pictures: from `wt-ui/web`, `node ../../uirun/shots.mjs after` and `PW_CHANNEL=chrome node ../../uirun/interact.mjs after`.

## One mistake of mine, put right
At about 01:45 I stopped my own stand-in worker with a command that matched every stand-in worker on this Mac, so the `adsrun` and `oprun` preview workers stopped too (both idle; they finished cleanly). I restarted both at once with the settings from their own `start.sh` (their `worker.pid` files are current). Nothing paid and nothing live was touched. If a stand-in run on :8077 or :8078 hung around 01:45 to 01:47, that was me.
