# Agent team
**How it actually runs now (8 Nov 2026):** one lead chat (sanaa workspace) holds state, merges as Reed and runs paid tests, and spawns builder, QA, critic and runner subagents per task. A babysitter chat (georgetown) sweeps PRs hourly and reports to Reed only. Reed critiques each style in its own desk chat and asks general questions in short Ask chats; decisions from those go into files the lead reads, never only into a chat. How desks work: ops/DESKS.md (`/desk <style>` starts one). The roles below are the long-term design; most are played by the lead's subagents today.

**Reed's site (since 9 Nov 2026)** is the old test site: https://thisisatestingenv.online, branch `next`, compose project `brand-studio-next`. It is production: real providers, real money, Reed's real work. Agents never experiment on it: never switch it to stand-ins (`NEXT_FAKE_PROVIDERS` stays `false`; the deploy refuses otherwise), never reset it or remove its volumes, and never run a paid call there without Reed's OK (logged in ops/SPEND.md). Every merge to `next` deploys straight to it, so merges happen only in Reed's windows, bundled, until a stand-in-only preview exists for agents to test on. The old production site (`main`, https://srv2091584.hstgr.cloud) is stopped and kept as a snapshot (deploy/README.md); don't touch it.

Each agent is its own Claude Code session on this repo. Work is tracked as GitHub issues (labels: `agent:<name>`). Reed talks to the Producer, and directly to the Writer for scripts.

| Agent | Model | Job | Runs |
|---|---|---|---|
| Producer | Opus 5.5 | Mission, roadmap, issues, assigns work, daily note to Reed, merges until Release exists | daily + on demand |
| Scribe | Haiku 5.5 | Keeps ops/LOG.md, DECISIONS.md, HANDOFF.md current and short | daily |
| Builder-Server | Opus 5.5 | Backend, data, jobs, model calls; PRs with tests | on demand |
| Builder-Screens | Sonnet 5.5 | Front end screens; PRs with tests | on demand |
| QA | Sonnet 5.5 | Playwright click-through tests; reviews every PR; red blocks merge | every PR |
| Explorer | Opus 5.5 | Maps tezu.ai, then Reed's site (read-only) and the preview nightly; files issues with screenshots | nightly (later) |
| Release | Sonnet 5.5 | Only merger/deployer; staging then live; rollback; backups; security pass | every PR (later) |
| Steward | Sonnet 5.5 | Size budgets, no dead code/duplicate tests; can block bloat | every PR + weekly (later) |
| Designer | Opus 5.5 | Screen designs before build; screenshot review at phone/desktop | on demand (later) |
| Director | Opus 5.5 | Prompts and video quality; only rules: engaging + required brand elements featured | on demand (later) |
| Writer | Opus 5.5 | Turns Reed's ideas into ready-to-paste Script Library scripts (asks what it needs, pitches 2–3 hooks, writes, revises). Reads the Current rules, house style, docs/references, brand kits and the script_draft prompt. Never touches the app, repo or live site; no paid calls | on demand (Reed) |
| Researcher | Opus 5.5 | Studies other tools (now Starpop) through Reed's own logged-in browser and writes findings for Reed; read-only on live sites; spends only within the budget Reed sets | on demand (Producer) |
| Treasurer | Haiku 5.5 | Bills vs usage, credit rates, spikes; weekly note | weekly (later) |

## Flow
Producer opens issue → (Designer sketches screens) → Builder opens PR from `agent/<name>/<topic>` → QA (+ Steward, Designer) review → merge → Scribe logs → Explorer checks live.
- **Before every push, check the PR is still open.** A push to a merged PR never ships; put it in a new PR from the base branch instead.
- **Branch every PR from its base (`main` or `next`), never from another open PR.** Squash merges break stacked PRs.
- **After QA passes a head, don't push to it** unless the Producer asks; a new head needs a new pass.

## Size budgets (Steward enforces)
- Whole app: about 36,000 lines of app code (server/app Python plus web/src without tests or the generated schema.d.ts) is a guide, not a hard cap (Current rules 26). The app can grow when needed, but no redundant or duplicate code, and each change deletes what it replaces. The Steward reports the count on every PR. Any file over 400 lines needs a reason.
- One test per behaviour; no snapshot dumps. Delete tests with the code they cover.
- ops/ files: HANDOFF under 60 lines, LOG trimmed monthly, DECISIONS one line each.

## Context hygiene (Reed, 2026-10-25)
- **When to restart:** when a worker finishes a batch of PRs and is above about 60% of its context (or has auto-compacted repeatedly), the Producer restarts it fresh instead of letting it compact mid-task.
- **How:** the old worker pushes everything and lists its open PRs and unopened branches, with a short handoff. The new session starts from HANDOFF, DECISIONS, this file and those PRs, and takes over watching them. The Producer sends everyone (Status Desk included) the new session ID and updates the table below, then archives the old session.
- **After any compaction, and before every new task:** re-read ops/HANDOFF.md and the Current rules at the top of ops/DECISIONS.md before acting. Newer decisions override older ones; if unclear, ask the Producer.
- **QA-Live sessions** are listed in the table below while they run, and removed when they finish.

## Sessions
The per-role session table (Oct 2026) is retired: those sessions have ended. Its last version is in git history (before 8 Nov 2026). Live agents are listed in the lead's `MAIN-HANDOFF.md`.

## QA review checklist (every PR)
- Tests: lint, typecheck and unit tests pass; the browser tests pass on the free stand-ins (`BS_FAKE_PROVIDERS`), and on the preview for screens and flows once it exists (never by experimenting on Reed's site).
- Nothing paid runs outside a test the Producer approved; every paid call is logged in ops/SPEND.md.
- Editors never see dollars, and an editor past the weekly allowance is declined with the reason (never "Ask Reed").
- Phones (390): no sideways scroll, every control at least 44px.
- After a server API change, `schema.d.ts` is regenerated and committed.
- Can the user undo or delete what they just made? (delete or archive, plus Undo after a delete or big change)
- No dead ends (Reed, 2026-10-26): every blocking problem is repaired by the server for free, turned into Advice, or has a one-click fix on the same screen. Editing the raw prompt is never the only way out.

## Limits
- Paid calls only within the $15/week cap, logged in ops/SPEND.md, asked through the Producer.
- Never touch story-studio or its live server.
- Never put keys in code, commits or chat.
