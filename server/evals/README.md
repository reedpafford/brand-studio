# Director evals (offline)

Six cases in `cases.json` (3 fomo, 3 Iron Paws) that test the prompts in `app/prompts/` against
the two creative rules: **engaging**, and **the brand's required screens featured**.

Each case has:
- `steps`: the Claude steps it runs, in order (Enhance's suggestions are all accepted before the next step).
- `good`: what a reviewer checks by eye (hook, cuts, reactions, restraint, screens in the right places).
- `expect`: what `score.py` checks mechanically, on top of `app/prompts/check.py` (quotes found,
  no dialogue rewritten, screens at their moments, clip lengths and reference limits).

What each case is for:
| Case | Tests |
|---|---|
| fomo-thanksgiving | Full chain on a messy draft: cut small talk but keep the callback's setup, add the missing screens, replace a made-up screen, scene break, seams |
| fomo-tight | Restraint: a script that already works gets 3 marks or fewer |
| fomo-draft-salesman | Drafting from a brief: different hooks, right length, screens on ★ lines |
| ironpaws-rescue | Breakdown + clips with a product (the bag) instead of app screens: shown exactly, no face, good seams |
| ironpaws-slow-start | Enhance on a slow opening and an explaining line, and a script that never shows the bag |
| ironpaws-pitbull-1 | Reed's real script: long dog voiceover, no names or headings; keep every word, find the pictures, show the bag, flag the flavor mismatch |

Iron Paws: a human-grade greens powder for dogs; the real bag is its required element, stored as a brand screen.

## Running (paid; needs the Producer's go-ahead)
```bash
python -m evals.run <out> --cap-usd 2   # 11 Claude calls, key from STUDIO_ANTHROPIC_KEY
python -m evals.score <out> "v1"
```
`run.py` accepts every Enhance suggestion before the next step, saves each answer to
`<out>/<case>.<step>.json` (plus `<case>.script.txt` and `cost.json`), and stops at the cap.

One full run is 12 Claude calls. Estimate at the prices in `app/claude.py` (about 3k system +
1k user tokens in, 3–8k out with thinking per call): about $2 a run (v1, without the long voiceover case: 9 calls, $1.02).
