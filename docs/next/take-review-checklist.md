# Take-review checklist (spec input for the advisory take check)

Saved verbatim from FOMO-Producer's message to Next-Lead, 30 Oct 2026, at the Producer's request. It is the spec input for the post-reset AI check on takes (part of the four-step flow, DECISIONS rule 21). Nothing here is built yet.

---

A) Camera style. Applied to every clip prompt:
  "locked-off cinematic framing" → "dynamic, always-moving cinematic camera"
  "mostly locked off" → "always moving"
Resulting Style line: "Style: Pixar-style 3D animation, warm amber key against cool blue shadows, shallow depth of field, dynamic, always-moving cinematic camera, big readable expressions."
It also flags any shot line with red/dips/dive/loss/losing next to fomo (a red FOMO screen) for a manual check. Reed's framing: general advice, not strict rules. Visual interest ("something happening") beats more cuts.

B) Review checklist, run on every take:
1. Transcript (faster-whisper small, word timestamps) against the script's lines for that clip:
   - extra or unscripted lines → mute that span in the cut, or redo;
   - missing lines;
   - a line spoken by the wrong person or off camera: the anchor's line must play on a shot where he's talking;
   - lip-sync gaps when a line spans a cut.
2. Pronunciation: FOMO must be FOH-moh. Fail on "Fobo", "Fogo", "Foho", "FOMA". Whisper mishearings like "traitor" for "trader" or "treat" for "trade" usually mean the audio is fine, so listen before redoing.
3. Eyes: no glowing or red eyes. It comes from strong emotion words; fix with a Keep note ("normal human eyes the whole time, never glowing or red").
4. Screens (6-frame strip plus a close look at each phone shot):
   - real FOMO UI, logo legible, phone in the scene, never full screen;
   - FOMO only winning: losses only on a plain app or an unseen screen, except a story dip that recovers;
   - the figures match the beat and grow;
   - the payoff is a big balance on the Home (rich) screen.
5. Continuity and cast:
   - the right people in each shot, no extra characters;
   - outfits and faces stable;
   - a white flash on every time jump.
6. Story logic for that story: every fall or hit has a cause on screen, and the stakes match the payoff. Per story only, never a rule (Reed was explicit).
7. Pacing:
   - something happening in every beat, a moving camera;
   - montages read as one smooth climb: no split screens, no unrelated payoffs crammed in, no 2-second dead holds.
8. Ending:
   - the yes/no question (not in songs), then the end line, word for word with FOMO said right;
   - the phone held up to the lens with a legible Home screen.
9. Wording that gets voiced or blocked: inner-speech feelings ("can't believe it worked") get spoken; "reply" and "answer" in actions get flagged as dialogue.
10. After a fix, re-transcribe the final cut and check it start to finish.
