# Agent team
Each agent is its own Claude Code session on this repo. Work is tracked as GitHub issues (labels: `agent:<name>`). Reed talks only to the Producer.

| Agent | Model | Job | Runs |
|---|---|---|---|
| Producer | Opus 5.5 | Mission, roadmap, issues, assigns work, daily note to Reed, merges until Release exists | daily + on demand |
| Scribe | Haiku 5.5 | Keeps ops/LOG.md, DECISIONS.md, HANDOFF.md current and short | daily |
| Builder-Server | Opus 5.5 | Backend, data, jobs, model calls; PRs with tests | on demand |
| Builder-Screens | Sonnet 5.5 | Front end screens; PRs with tests | on demand |
| QA | Sonnet 5.5 | Playwright click-through tests; reviews every PR; red blocks merge | every PR |
| Explorer | Opus 5.5 | Maps tezu.ai, then our test/live sites nightly; files issues with screenshots | nightly (later) |
| Release | Sonnet 5.5 | Only merger/deployer; staging then live; rollback; backups; security pass | every PR (later) |
| Steward | Sonnet 5.5 | Size budgets, no dead code/duplicate tests; can block bloat | every PR + weekly (later) |
| Designer | Opus 5.5 | Screen designs before build; screenshot review at phone/desktop | on demand (later) |
| Director | Opus 5.5 | Prompts and video quality; only rules: engaging + required brand elements featured | on demand (later) |
| Treasurer | Haiku 5.5 | Bills vs usage, credit rates, spikes; weekly note | weekly (later) |

## Flow
Producer opens issue → (Designer sketches screens) → Builder opens PR from `agent/<name>/<topic>` → QA (+ Steward, Designer) review → merge → Scribe logs → Explorer checks live.

## Size budgets (Steward enforces)
- Whole app: aim under 8,000 lines of code at launch. Any file over 400 lines needs a reason.
- One test per behaviour; no snapshot dumps. Delete tests with the code they cover.
- ops/ files: HANDOFF under 60 lines, LOG trimmed monthly, DECISIONS one line each.

## Limits
- Paid calls only within the $15/week cap, logged in ops/SPEND.md, asked through the Producer.
- Never touch story-studio or its live server.
- Never put keys in code, commits or chat.
