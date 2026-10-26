# QA-Live end-to-end test: live site, 26 Oct 2026

One full run on https://srv2091584.hstgr.cloud, clicking the screens as QA Owner (owner) and QA Editor (editor), brand fomo.

- **Spend:** 82 credits shown on the screens (limit 140). About 70.4 credits actually charged (≈ $7.24). Details are in `costs.csv`.
- **Finished video:** `qa-live-final.mp4`. It is the 4 downloaded clips joined in order with ffmpeg, no re-generation: 42.3 s, 480×854, 9:16.
- **Screenshots:** `shots/` (numbered; `-390` files are phone width). I left out screenshots that show team members' real email addresses. No screenshot shows an invite link, password or cookie.

## What worked

- Owner invite → account → role owner (`shots/001`).
- **Instagram link works from the live server.** Pasting the reel link made a draft at once. After about 126 s it showed "Got the reel · 40 s · 45 shots · 18 lines of dialogue" and offered "Read this reel · 7 credits". I didn't press it (`shots/002–004`).
- Delete a draft → Undo brings it back → delete again. Both drafts (the throwaway and the Instagram one) are now under "Deleted and archived" (`shots/005–009`, `075–076`).
- Upload → read → script → directions → 1 variation → cast (Omar locked to "Carl", the girlfriend and the rival left unlocked) → breakdown → publish 2 versions (`shots/010–030`).
- Team invite for an editor; the editor accepted in a second browser (`shots/031`).
- Editor: version A → looks made for both unlocked roles → storyboard → clip prompts → 4 takes → one Redo with a note on clip 1 → all clips approved → zip downloaded (21.7 MB) (`shots/032–070`). The editor saw no dollar amounts and no "Ask Reed" anywhere on this run.
- Owner started version B and released it (`shots/071–074`).
- Owner removed QA Editor. Their sign-in stopped working at once, and Undo was offered.
- Cast check, done after the stills (your messages reached me late): every one of the 40 breakdown shots tags the right character, and the breakdown was never redone after Assets (`shots/065`).

## Findings, most serious first

### 1. Starting a version spends credits with no price shown, and Release doesn't stop it (high: money)
- Screen: Scripts → "Version B, ready to make" → "Make this version" → video 8. `shots/071–073`.
- Did: pressed "Make this version" (the panel's button showed no price for B), then "Release this version" straight away.
- Expected: nothing charged, or the price shown on the button first.
- Happened: a breakdown job (job 76) started by itself. The release dialog said "The 3 credits already used stay used", but the job kept running after the release and charged **3.923** credits, on a version that had already been handed back.
- Guess: `web/src/scripts/VersionPanel.tsx` (the `price` hides when `has_breakdown`, but B had no breakdown of its own), and the `/scripts/{id}/drafts/{slot}/produce` handler, which plans automatically. Release should cancel jobs that are still running.

### 2. After the paid reel read, the Script step shows a "Write with Claude · 6 credits" button instead of the new script (high: user could pay twice)
- Screen: script → step 2 Script. `shots/014` (during the read), `shots/015` (after it finished), `shots/016` (after a reload).
- Did: pressed "Read this reel · 7 credits" on the Script step and waited.
- Expected: a progress line, then the written script.
- Happened: no progress line while reading. When the read finished, the page offered "Write with Claude · 6 credits" and never showed the script until a reload.
- Guess: `web/src/scripts/WriteOptions.tsx`. When the reel read finishes, nothing reloads the script (only `ReelBlock` on the Description step does that). `ReadReelButton` also shows nothing while the read is running.

### 3. A failed paid job looks like it is still running (high)
- Screen: video → Clips. `shots/057`, `058`.
- Did: pressed "Write clip prompts · 3 credits".
- Happened: the job failed after about 1 minute ("Lost contact while starting paid work. Check the provider before retrying."). The screen kept saying "Writing your clip prompts…" for 7+ minutes and never showed the failure. A reload just showed the button again, with no message. I pressed it once more and it worked. The failed job was not charged.
- Guess: `web/src/projects/ClipsPane.tsx` (`writingNow` doesn't notice a failed job).

### 4. Claude wrote a clip prompt that blocks "Make clip", and the editor is told why in jargon (high: dead end for editors)
- Screen: Clips, clip c2. `shots/062`, `063`.
- Happened: the c2 prompt ended with an empty, zero-length shot ("Shot 11 | 12-12 s."). "Make clip · 12 credits" was greyed out with no reason on the button. The only explanation was small red text: "shot times aren't whole seconds back to back from 0" and "shot 11 has no line but doesn't say no one speaks". "Make the takes" silently left c2 out (30 instead of 42 credits).
- I fixed it by hand with "Edit prompt" (deleted the empty line, free). An editor is unlikely to manage that.
- Guess: the clip-prompt writer on the server (an empty last shot), plus the clip card should say in plain words why the button is grey.

### 5. Prices shown and credits charged don't match, and Usage hides most charges (medium: money reporting)
- Charged more than shown: "Write clip prompts · 3" charged **4.499**, and "Make the breakdown · 3" charged **3.35**.
- Charged less than shown: "Read this reel · 7" charged 3.026, "Write 1 variation · 6" charged 1.582, "Suggest directions · 3" charged 0.695.
- **Usage → charges (`/api/usage/charges`) lists only the Claude text jobs.** The reel watch (Gemini), the look sheets, the storyboard frames and all 5 video takes (48 credits) are missing, so Usage shows 13 credits for a run that cost about 70.
- Guess: `server/app/routes/usage.py` `charges()` joins `Usage` rows, and image/video/Gemini jobs don't seem to write one (or not yet). The estimates live in the job-price code.

### 6. The locked look's name replaces the role's name (medium: wrong words in the video)
- Locking "Omar, the boyfriend" to the look "Carl" made the breakdown, prompts and stills call him **Carl**, while the lines still say "Omar, it's not what it looks like" (`shots/028`, `034`). The prompts even say "Carl (the girlfriend calls him Omar)".
- The locked look also overrides the role's outfit: the role says navy hoodie, and "Carl" is a grey quarter-zip.

### 7. The finished clips don't keep characters consistent (medium: video quality, for the Director)
- In clip 2, Carl wears the rival's black leather jacket. In clip 4 he turns into a different-looking man (black hair, sunglasses, suit). See frames at about 7 s, 10 s and 32 s of `qa-live-final.mp4`.
- The fomo screen shows $548,920 where the script says $512,400.
- The clips are only 480×854 with 32 kHz audio.

### 8. "Locked by Reed" is written into the code (medium: wrong name, and editors see it)
- Assets shows "Locked by Reed" on a lock QA Owner made (`shots/035`). It comes from `web/src/projects/AssetsPane.tsx:164`.
- In the same spirit, `ClipsPane.tsx` (lines ~240, 320, 384) labels buttons "Ask Reed to approve" when over budget. This run never hit it, but an editor would see it. The QA checklist says editors never see "Ask Reed".

### 9. "Can't reach the server" full-page error (medium)
- Twice, a plain page load showed only "Can't reach the server. Try again in a moment." with no button (`shots/023`, `041`). It worked again on the next load.
- Note: `/health` returns the web page (HTML) rather than a real health check, so a monitor would always see 200.

### 10. Two copies of a character, made from a script role (low)
- Cast & places has two identical characters, #4 and #5 "Nate, the boyfriend who proposes": no sheet, no history, used by nothing. The lock panel and the Assets picker list them twice (`shots/025`). This looks like "Make a look" being pressed twice, or not checking for one it already made. See the character list below.

### 11. Smaller things (low)
- "Make a look" on Assets shows no price (it's free: it adds the role to Cast & places, and the paid sheet, 1.5 credits, is made there). Without a price it's unclear whether it spends.
- The editor's invite page says "Join owner-reed", an internal name, not the studio's name.
- An imported reel is titled "Untitled reel", and the Description step has no Title box until you press "Edit description".
- Both reel imports reported "45 shots" for a 40 s reel. That looks over-cut, but the breakdown didn't use it (40 shots, 4 scenes, 4 clips).
- The video's budget meter didn't count the 2 look sheets (they are character costs), so it read 0 / 84 after 3 credits had been spent for this video.
- A second owner (QA Owner) gets a "…" menu on Reed's own row on Team. I didn't open it; worth checking that one owner can't remove or demote another by mistake.

## Characters created from a script or video (read-only, GET as QA Owner)

The API doesn't record where a character came from. I worked it out from the names (a role name rather than a person's name), the notes (the role description copied in), the version history and the jobs. Nothing was changed or deleted.

| id | name | brand | made by / when | came from | used by anything now? |
|---|---|---|---|---|---|
| 6 | The girlfriend | fomo | QA Editor, 26 Oct 04:00 UTC (sheet job 62, approved) | Assets "Make a look" on video 7 (QA live reel, script 19) | **No.** Video 7 now uses Goth GF for that role |
| 7 | The rival | fomo | QA Editor, 26 Oct 04:02 UTC (sheet job 63, approved) | Assets "Make a look" on video 7 (QA live reel, script 19) | **No.** Video 7 now uses Mogging BF for that role |
| 4 | Nate, the boyfriend who proposes | fomo | unknown (no history saved; no sheet ever made) | a script role: "Turned down in Paris…" (script 15, videos 3 and 4) | **No.** Videos 3 and 4 now use Carl for that role |
| 5 | Nate, the boyfriend who proposes | fomo | unknown (same as #4; an exact duplicate) | same as #4 | **No** |

Made in Cast & places by Reed, for reference (not from a script): #1 Goth GF, #2 Mogging BF, #3 Carl. All three are in use.
