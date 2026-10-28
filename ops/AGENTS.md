# Agent team
Each agent is its own Claude Code session on this repo. Work is tracked as GitHub issues (labels: `agent:<name>`). Reed talks to the Producer, and directly to the Writer for scripts.

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
| Writer | Opus 5.5 | Turns Reed's ideas into ready-to-paste Script Library scripts (asks what it needs, pitches 2–3 hooks, writes, revises). Reads the Current rules, house style, docs/references, brand kits and the script_draft prompt. Never touches the app, repo or live site; no paid calls | on demand (Reed) |
| Researcher | Opus 5.5 | Studies other tools (now Starpop) through Reed's own logged-in browser and writes findings for Reed; read-only on live sites; spends only within the budget Reed sets | on demand (Producer) |
| Treasurer | Haiku 5.5 | Bills vs usage, credit rates, spikes; weekly note | weekly (later) |

## Flow
Producer opens issue → (Designer sketches screens) → Builder opens PR from `agent/<name>/<topic>` → QA (+ Steward, Designer) review → merge → Scribe logs → Explorer checks live.

## Size budgets (Steward enforces)
- Whole app: about 36,000 lines of app code (server/app Python plus web/src without tests or the generated schema.d.ts) is a guide, not a hard cap (Current rules 26). The app can grow when needed, but no redundant or duplicate code, and each change deletes what it replaces. The Steward reports the count on every PR. Any file over 400 lines needs a reason.
- One test per behaviour; no snapshot dumps. Delete tests with the code they cover.
- ops/ files: HANDOFF under 60 lines, LOG trimmed monthly, DECISIONS one line each.

## Context hygiene (Reed, 2026-10-25)
- **When to restart:** when a worker finishes a batch of PRs and is above about 60% of its context (or has auto-compacted repeatedly), the Producer restarts it fresh instead of letting it compact mid-task.
- **How:** the old worker pushes everything and lists its open PRs and unopened branches, with a short handoff. The new session starts from HANDOFF, DECISIONS, this file and those PRs, and takes over watching them. The Producer sends everyone (Status Desk included) the new session ID and updates the table below, then archives the old session.
- **After any compaction, and before every new task:** re-read ops/HANDOFF.md and the Current rules at the top of ops/DECISIONS.md before acting. Newer decisions override older ones; if unclear, ask the Producer.
- **QA-Live sessions** are listed in the table below while they run, and removed when they finish.

## Sessions (current)
| Agent | Session |
|---|---|
| Builder-Server-5 (replaced Builder-Server-3 and -4 on 2026-10-27, context hygiene; montage trading screens) | session_01FRDAYJJv6AhprHx2GkXuCr |
| Builder-Server-6 (role matching, duplicate roles) | session_01FRDAYJUwbJh3yTNjVjfofU |
| Writer (Reed talks to it directly) | session_01FRDAYF8xUEnyc2USaQdPNF |
| Researcher (Starpop, Phases 1–2, done) | session_01FRDAYGsMfXmbBgso61qMqh |
| Next-Lead (branch `next`, ops/NEXT.md) | session_01FRDAYGxkc3gPaKGXtreXsy |
| Next-Server | session_01FRDAYHAqt6VpjWXU1MbtNR |
| Next-Screens | session_01FRDAYFB7SvzZ39XgExCxPt |
| Flow-QA | session_01FRDAYFWiQrAfCDjT614hkp |
| Builder-Screens | session_01YVSDg6CB1ysUhPvZfDfqx9 |
| Builder-Screens-3 (editor video flow; replaced Builder-Screens-2 on 2026-10-26) | session_01RY7gQZ2FyTVwVAYrbX5MXu |
| QA (server, prompts) | session_01Jj3pwffX4avJkR9J5MmiiE |
| QA-2 (web) | session_0151NB9uZupi8GLzzTbeAtEv |
| Designer | session_01USbuJ9znkRnKbNV4cnJUNW |
| Director | session_01HeFuWAEdxcgfha4QYoAC3Z |
| Steward | session_01FRDAYFCGf1CkVUYdddfvi7 |
| QA-Live 6 (live checks, while it runs) | session_01FRDAYFjPARnHGEy8SXNuo8 |
| Scribe-2 | session_01FRDAYHZyBA1pmnXw7MYEdi |
| Release | session_01BGZgB9afnDnbYURA7D11gk |
| Status Desk | session_01GYxBJctxeeNdzejMuRiCW6 |

## QA review checklist (every PR)
- Tests: lint, typecheck and unit tests pass; the browser tests pass on the free stand-ins (`BS_FAKE_PROVIDERS`).
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
