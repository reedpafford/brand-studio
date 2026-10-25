# Reel import: the Director's part (plan, not built)

Owner: Director. Status: plan for the Producer and Reed (DECISIONS #270, #271). It matches Builder-Server's plan in `docs/design/reel-import-server.md` §3: prep (download, transcript, cut list, contact sheet) is theirs; three paid steps follow it. No paid calls until the Producer says go.

A new script can start from an Instagram reel link or an uploaded video. The app reads the reel into the same shape as `docs/references/*/BREAKDOWN.json` and pre-fills version A and the cast slots for Reed to adapt. Live action is always dropped.

| Step | Model | Prompt | Status |
|---|---|---|---|
| 1. Watch | Gemini 3.5 Flash (`watch-gemini`) | `prompts/reel_watch.md` (new, below) | plan |
| 2. Write | Claude, the existing `script_draft` step | `script_draft.md` with the script's own breakdown as `<reference>` and the `new_lines` switch | built: #271 PR (keep the reel's lines) |
| 3. Cast | Claude, the existing `cast_slots` step | `cast_slots.md`, with the reel as `<reference>` | built: #214, #241 |

---

## 1. Watch (`reel_watch.md`, Gemini)

**What Gemini is given** (Builder-Server's prep):
- the video (a Replicate file URL);
- a contact sheet, one frame per shot, each labelled with its shot number and times;
- the transcript with times, `[{start, end, text}]`, with no speakers;
- the cut list from shot detection, `[{n, start, end}]`.

**What it does:** it describes what it sees, shot by shot, and labels who speaks each transcript line. It never writes, fixes or moves the words: lines and timings come from the transcript, and the shot boundaries come from the cut list. The server merges each transcript line into the shot whose time range holds its start.

**Output schema `ReelWatch`** (the BREAKDOWN shape, minus what prep already knows):

```
ReelWatch {
  logline:     str                 # one sentence: who, the turn, the payoff
  style:       str                 # e.g. "3D animated (Pixar-style CG)"
  hook:        {seconds: float, mechanic: str}   # what grabs in the first seconds
  beats:       [{start, end, summary, emotion}]  # 5–10 story beats
  montage:     {start, end} | null               # the wordless run, if any
  shots: [                          # exactly one per cut, same n, start, end
    {
      n: int, start: float, end: float,
      framing:     str              # "close-up, low angle"
      camera:      str              # "static", "push in", "whip pan"
      on_screen:   str              # who and what is in frame (looks, place, props)
      action:      str              # what happens
      emotion:     str              # the faces, in words
      live_action: bool             # real footage (a real person, phone video), not animation
      text_on_screen: str           # captions seen, described only; never copied into a script
    }
  ]
  speakers: [{line: int, speaker: str}]   # transcript line index → a role name, the same name all reel long ("groom", "bride")
  why_it_works: [str]               # 3–6 short reasons
}
```

**Prompt rules (`reel_watch.md`):**
1. Use the cut list as given: one entry per cut, with the same numbers and times. Never merge, split or add shots.
2. Describe only what is on screen. Framing and camera in standard terms (close-up, push in, pan, track, orbit, low angle, overhead, handheld). Emotion as faces and bodies, not story.
3. **Speakers:** for each transcript line, name who says it. Use the reel's role names (groom, bride, rival, mom), each the same through the reel. A voice nobody on screen speaks is "narrator (V.O.)". Never invent a line, and never change the words.
4. **Live action:** `live_action` is true for any shot of real footage (a real person, a phone video, a real car), even inside an animated reel. Those shots are dropped later; flag them all.
5. `text_on_screen` describes captions so they can be ignored. It is never repeated as dialogue.
6. The hook is the first 1–3 seconds' mechanic (e.g. "'I do' → 'HELL NO!' rejection at the altar"). Beats carry an emotion each. The montage is the run of quick wordless shots, if any.

**Checks, `check.reel_watch(watch, cuts, transcript)`:**

| Check | Kind |
|---|---|
| a cut is missing, repeated, or its times differ | fix (regenerate) |
| a speaker is given for a transcript line that doesn't exist | fix |
| a transcript line has no speaker | advice |
| one role under two names (e.g. "bride" and "the bride") | advice |
| a live-action shot holds a transcript line (it will be dropped; the editor should know) | advice |

---

## 2. Write (the existing `script_draft` step)

This is built in the #271 PR:
- `<reference>` is `reference_block(...)` of the script's own imported breakdown, so live-action shots are already gone. It's the same shape as a catalogue reel.
- **Switch off (default):** the reel's spoken lines stay word for word, by the same character, in the same order. Only brand-swap lines are rewritten, at the same length, and they're listed in `ScriptDraft.changed_lines`.
- **Switch on, `<new_lines>true</new_lines>`:** new dialogue in the reel's style, beats and pacing.
- **Check, `check.reference_lines(script, reel_lines, new_lines)`:** advice per reel line changed or missing. Builder-Server's planned `check.reel_script` is this same check, so please reuse it rather than add a second.
- **Live action stays gone:** the reel's live-action lines never reach the prompt. Its slot becomes the brand's end line, which the existing breakdown check enforces.
- **No invented speakers, in version A:** every speaker in the script is one of the reel's speakers (mapped to the cast) or the brand's end-line speaker. An advice check is added at build time.

## 3. Cast (the existing `cast_slots` step)

`cast_slots_input({0: version A}, reference=reference_block(imported), cast=[locked], brief=title + description)`. The reel's on-screen looks (`on_screen`) feed each slot's description, and the reel's role names become slot names when version A keeps them.

---

## Evals

| Case | Reel | Gold | Checks |
|---|---|---|---|
| `reel-import-altar` | fomo-DehudnaAmce (altar) | `docs/references/fomo-DehudnaAmce/BREAKDOWN.json` | 50 shots, one per cut; shots 44–50 flagged live action; 11 transcript lines with speakers groom/bride; hook mentions the rejection. The write step keeps every reel line word for word (switch off). Cast slots: the groom, the bride, the rival; no admirers. |
| `reel-import-betty` | De4ohoJolPe (Betty) | the Producer's transcript plus a hand-checked shot list (to make) | one shot per cut; live action flagged; speakers stay consistent. The write step keeps the reel's lines except the reselling ones, which become trading lines and are listed in `changed_lines`. |

- **Inputs needed:** each reel's video, transcript and cut list. They're in the Producer's scratchpad and aren't in the repo; the eval reads them from a path given on the command line.
- **$0 dry run:** a worked example `examples/reel_watch.json` (the altar, from its BREAKDOWN.json) that passes `check.reel_watch`, unit tests for each check, and `run.py --print` for the watch prompt.

## Cost per reel

| Step | Calls | Estimate |
|---|---|---|
| Watch (Gemini 3.5 Flash, a 45 s video plus a contact sheet) | 1 | about $0.05 |
| Write (Claude, script_draft with a 50-shot reference) | 1 | about $0.25–0.35 |
| Cast (Claude, cast_slots) | 1 | about $0.07 (measured $0.065 a call) |
| **Total** | 3 | **about $0.40 actual. Builder-Server prices it at about 7 credits from today's per-call rates.** |

The paid eval (2 reels × 3 calls) comes to about $0.80, and waits for the Producer.

## Build order and ETA

1. `reel_watch.md`, the `ReelWatch` schema, `check.reel_watch` and the altar worked example: about 3 h after go.
2. `reel-import-altar` eval, plus `reel-import-betty` once the Producer shares its files.
3. The no-invented-speakers advice check: about 1 h, alongside step 1.
