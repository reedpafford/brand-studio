# Director evals (offline)

Five cases in `cases.json` (3 fomo, 2 Iron Paws) that test the prompts in `app/prompts/` against
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

Iron Paws: a dog product in a bag; the real bag is its required element, stored as a brand screen (being confirmed with Reed).

## Running (paid; needs the Producer's go-ahead)
No runner is checked in yet: it needs the Claude client (PR #23). A run calls each case's steps with
`prompts.system(step)` + `prompts.brand_block(...)`, saves each answer to
`<out>/<case>.<step>.json` (and the working script to `<case>.script.txt`), then:

```bash
python -m evals.score <out> "v1"
```

One full run is 11 Claude calls. Estimate at the prices in `app/claude.py` (about 3k system + 1k user tokens in,
3–8k out with thinking per call): about $1.50 a run. Comparing two prompt versions: about $3.
