# Brand Studio

Internal, brand-organised AI video studio for Reed's team. Videos are guided by a script or brief:
Brief → Script → Breakdown → Storyboard → Clips → Review → Final cut. "Quick clip" (one-off generation) also exists, always inside a brand.

Read before any work: `ops/MISSION.md`, `ops/HANDOFF.md`, and the "Current rules" section at the top of `ops/DECISIONS.md` (stop at "## History"; grep the History for your topic, don't read it whole). Open `ops/AGENTS.md` when you need roles or the PR flow. Never read `ops/LOG.md` or `ops/SPEND.md` whole: tail or grep them.
The live V6 lead's state is outside the repo, in the sanaa workspace: `.context/MAIN-HANDOFF.md` (current) and `.context/team/LEDGER.md` (history, append-only).

## Hard rules
- Keys never go in code, commits, logs or chat. Server-side only.
- No paid call (Replicate, Claude API) outside tests the Producer approved. Log every paid call in `ops/SPEND.md`.
- Only the Release agent merges or deploys (until it exists, the Producer does). One exception (Reed, 16 Nov 2026): a PR that only adds rows to `ops/SPEND.md` is merged by the agent that opened it, as soon as its checks pass, without asking.
- Keep it small: see the budgets in `ops/AGENTS.md`. Prefer deleting code to adding it.
- Plain language in anything Reed reads.
