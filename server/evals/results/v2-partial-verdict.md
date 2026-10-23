# Eval v2 (partial): Director's verdict on Enhance (2026-10-23)

v2 ran 5 of its calls ($0.36): the four Enhance cases and one script draft. Its breakdowns never
reached the API, because the runner asked for more output than the SDK allows without streaming
(fixed in #41). So this verdict covers Enhance only. Breakdowns, clip prompts and the reference
case wait for the rerun.

## Winner for Enhance: v2
All 4 cases pass the machine checks (v1 passed 3 of 4).

| Case | v1 | v2 |
|---|---|---|
| fomo-tight (a script that already works) | 5 marks, 3 on the punchline | **2 marks**: one action, one held reaction on "Six cents." |
| fomo-thanksgiving (messy draft) | 14 marks | **10 marks**, with every screen, cut, scene break and the Wallet fix kept; the two decorative camera marks dropped |
| ironpaws-slow-start | 9 marks | 7 marks, same fixes; the bag comes in at the payoff |
| ironpaws-pitbull-1 (Reed's real voiceover script, new) | not run | 17 marks for about 160 s; no spoken word touched; flavor flagged |

## Good example: ironpaws-pitbull-1
- It opens on "an extreme close-up of Bruno's crusty eyes as they blink open", so the first second
  shows the problem.
- It gives each symptom its own picture (raw paw, a cloud of fur in a sunbeam), and on the long
  science paragraph it pushes into "a stylized 3D gut: glowing good bacteria…" so the picture
  keeps moving.
- It puts the real bag at the find, the feeding, the claims and the end card.
- On "Peanut butter flavor" it leaves the words alone and says: "The bag label says Chicken
  flavor, but this spoken line says peanut butter; the editor should decide."

## Weaker spot: fomo-thanksgiving
- v2 dropped v1's push-in on Rick's opening jab. The hook still works (the small talk is cut),
  but that mark was one of v1's best.
- I'm not adding a rule for it. If the rerun shows weak hooks in breakdowns, the fix belongs in
  the breakdown prompt, not Enhance.
