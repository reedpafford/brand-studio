# Breakdown

Purpose: Claude turns the working script into scenes → shots → clips. The editor checks it, fixes problems, and moves on to the storyboard. The script stays in the left pane the whole time (`project.md`).
API (#66): `POST /projects/{id}/breakdown` (paid, queues a job), `GET` (newest, with `problems` and `stale`), `PUT` (save an edited breakdown; problems are re-checked).

## Desktop (1440): the stage pane
```
│ Breakdown · made by Claude for script v5          [Redo · 6 credits] │
│ ┌ Problems (2) ──────────────────────────────────────── danger-soft ┐ │
│ │ • Shot 2.1 is a loss moment but shows no fomo screen.   [Go to]   │ │
│ │ • Clip c3 is 17 s; the model allows 4–15 s.             [Go to]   │ │
│ └───────────────────────────────────────────────────────────────────┘ │
│ Hook: "Mia's coffee freezes mid-air as the chart drops."              │
│ 3 scenes · 9 shots · 4 clips · 28 s (planned 30 s)                    │
│                                                                       │
│ SCENE 1 — INT. KITCHEN — MORNING                                      │
│ Cold blue light, empty counter, nobody behind her.        (look, muted)│
│ ┌─ Clip c1 · 8 s ───────────────────────────────────────────────────┐ │
│ │ 1.1  3 s  Wide, slow push-in                         lines 2–3 ◂  │ │
│ │      Mia scrolls her phone, coffee in hand.                       │ │
│ │      [● Mia] [⌂ Kitchen]                                          │ │
│ │ 1.2  2 s  Close-up, static                             line 4 ◂   │ │
│ │      MIA: "Wait… it dipped?"            (Courier, read-only)      │ │
│ │      Reaction: eyes snap wide                                     │ │
│ │      ★ loss · fomo screen: Chart down                             │ │
│ │                                        [Edit] [Split clip after]  │ │
│ └ ends: hard cut to the street ─────────────────────────────────────┘ │
│                                                                       │
│                                        [ Next: Storyboard → ]         │
```
- **Header line:** source ("made by Claude" / "edited by Sam") and the script version it was made for. **Redo** shows its cost and asks "Replace this breakdown? Your edits are kept in History." if there are edits.
- **Stale:** when `stale` is true, a warning banner sits above everything: "Made for script v3. The script is now v5." with **[Make a new breakdown · 6 credits]**. Next stays disabled until there's a breakdown for the working script.
- **Problems:** a danger-soft card listing `problems` as given (they're already plain sentences). Each one has **Go to**, which scrolls to and outlines the shot or clip it names. With no problems the card is hidden. **Next is disabled while there are problems**, with the reason "Fix the 2 problems first." Required brand screens are the reason this gate exists.
- **Clips** are bands around their shots: the label "Clip c1 · 8 s" at the top and the `seam` reason at the bottom ("ends: hard cut to the street", or "end" for the last one). Clip seconds turn danger-coloured, with the reason, when they're outside the model's range.
- **Shot card:**
  - Top line: shot id, seconds, camera.
  - `action` as the main line.
  - If someone speaks: `speaker: "line"` in Courier Prime, read-only, because the words belong to the script.
  - `reaction` if any, and chips for cast (●), place (⌂) and moment + ★ screens.
  - **lines 2–3 ◂** highlights those lines in the script pane (`--accent-soft`) and scrolls them into view. Selecting a script line does the reverse.
- **Edit** opens the shot in place. Editable: action, reaction, camera, seconds, cast, place, moment and screens. **Not editable**: the spoken line and speaker, which come from the script. Hint: "To change the words, edit the script." **Save** sends the whole breakdown (`PUT`), shows "Saved. 1 problem left." or "Saved. No problems.", and the source becomes "edited by <name>".
- **Split clip after** / **Join with next clip** sit between shots. They recompute clip ids and seconds on the page, then the next Save re-checks them.

## States
- No breakdown: empty card "No breakdown yet." / "Claude splits your script into scenes, shots and clips. Nothing is generated yet." / **[Make breakdown · 6 credits]**. Disabled reasons: "Add a script first", "A breakdown is already being made", "Waiting for Reed to approve".
- Running: skeleton shot cards + "Breaking down your script…".
- Failed: "The breakdown didn't finish. Nothing was charged for the failed part. [Try again]".

## Phone (390)
- The tabs read **Script | Breakdown**. "lines 2–3 ◂" switches to Script and highlights the lines.
- The problems card is collapsed to one line ("2 problems ▸") that opens a bottom sheet with Go to links.
- Shot cards are full width. **Edit** opens the shot in a bottom sheet with Save / Cancel.
- Split / Join live in each shot's ⋯ menu.
- **Next: Storyboard →** sits in the fixed bottom bar above the tab bar, with the disabled reason under it.
