# Brand Studio

Internal, brand-organised AI video studio for Reed's team. Videos are guided by a script or brief:
Brief → Script → Breakdown → Storyboard → Clips → Review → Final cut. "Quick clip" (one-off generation) also exists, always inside a brand.

Read before any work: `ops/MISSION.md`, `ops/AGENTS.md`, `ops/DECISIONS.md`, `ops/HANDOFF.md`.

## Hard rules
- Keys never go in code, commits, logs or chat. Server-side only.
- No paid call (Replicate, Claude API) outside tests the Producer approved. Log every paid call in `ops/SPEND.md`.
- Only the Release agent merges or deploys (until it exists, the Producer does).
- Keep it small: see the budgets in `ops/AGENTS.md`. Prefer deleting code to adding it.
- Plain language in anything Reed reads.
