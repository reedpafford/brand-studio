# Director evals (offline)

Eight cases in `cases.json` (4 fomo, 4 Iron Paws) that test the prompts in `app/prompts/` against
the two creative rules: **engaging**, and **the brand's required screens featured**.

Each case has:
- `steps`: the Claude steps it runs, in order (Enhance's suggestions are all accepted before the next step).
- `good`: what a reviewer checks by eye (hook, cuts, reactions, restraint, screens in the right places).
- `expect`: what `score.py` checks mechanically, on top of `app/prompts/check.py` (quotes found,
  no dialogue rewritten, screens at their moments, clip lengths and reference limits).

What each case is for:
| Case | Tests |
|---|---|
| fomo-thanksgiving | Full chain on a messy draft: no line changes, add the missing screens, a note on the made-up screen, a visible hook, seams |
| fomo-tight | Restraint: a script that already works gets 3 marks or fewer |
| fomo-draft-salesman | Drafting from a brief: different hooks, right length, screens on ★ lines |
| ironpaws-rescue | Breakdown + clips with a product (the bag) instead of app screens: shown exactly, no face, good seams |
| ironpaws-slow-start | Enhance on a slow script: visible beats and the bag added, problems in the words only as notes |
| ironpaws-pitbull-1 | **Definition of done.** Reed's real script with the peanut-butter bag: long dog voiceover, keep every word, find the pictures, show the right bag (no flavor note needed) |
| fomo-adapt-altar | **Definition of done.** Reed's altar reel remade for fomo: same story, every line word for word, the montage as fomo trading with real screens, the live tag replaced by fomo's call to action |
| ironpaws-pb-excerpt | 15 s excerpt: "mixed it into my food… peanut butter flavor… finished the bowl" with the real bag |
| fomo-montage-excerpt | 12 s excerpt: only the altar reel's montage, as wordless fomo trading with the real screens |

Iron Paws: a human-grade greens powder for dogs; the real bag is its required element, stored as a brand screen.

Answers in `results/v1` and `results/v2-partial` predate Reed's no-edit rule (they have cut and scene-break marks and no notes), so the current scorer can't read them; the verdict files keep what they showed.

## Running (paid; needs the Producer's go-ahead)
```bash
python -m evals.run <out> --cap-usd 2   # 11 Claude calls, key from STUDIO_ANTHROPIC_KEY
python -m evals.score <out> "v1"
```
`run.py` accepts every Enhance suggestion before the next step, saves each answer to
`<out>/<case>.<step>.json` (plus `<case>.script.txt` and `cost.json`), and stops at the cap.

One full run is 12 Claude calls. Estimate at the prices in `app/claude.py` (about 3k system +
1k user tokens in, 3–8k out with thinking per call): about $2 a run (v1, without the long voiceover case: 9 calls, $1.02).
