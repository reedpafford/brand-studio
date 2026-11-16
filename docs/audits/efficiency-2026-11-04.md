# Brand Studio usage audit — approval requested

Audit date: 2026-11-04, America/New_York. Scope: local Conductor Claude workflows, with V6 protected. This is a plan, not an authorization to change workflows, retire sessions, merge, or deploy.

## What is protected

The two untracked root PRODUCT.md copies in `bangkok` and `design-brief-plan` were identical: 47 lines, 4,288 bytes; `diff -u` produced no differences. The exact file was committed to the existing V6 branch and pushed. No other file in those workspaces was changed.

- [V6 PRODUCT backup, 7cd5a362](https://github.com/reedpafford/brand-studio/commit/7cd5a3620dc07cd472a5b932575b04f70472bda4)
- [Main checkpoint, pre-efficiency-2026-11-04](https://github.com/reedpafford/brand-studio/tree/pre-efficiency-2026-11-04): `95ed6ac0fd6d65bcc7646b4f4f7f77f55ae8ea71`.
- [V6 checkpoint, pre-efficiency-2026-11-04-v6](https://github.com/reedpafford/brand-studio/tree/pre-efficiency-2026-11-04-v6): `a3f67aa19a8ce82e1db3730c849fd61641662099`.

Git cannot attach one tag name to two commits, so V6 has the `-v6` suffix. Remote refs were verified with `git ls-remote` after an atomic push. The V6 checkpoint-to-head diff contains only the new root PRODUCT.md: 47 added lines. The existing V6 directory includes its PRODUCT, README, build plan, coverage, flow, review and boards, including S-gaps-01. These remain in the tagged Git tree.

This is protection for committed V6 content and the two named untracked files, not a claim that every other untracked asset or unsent decision in every workspace is backed up. Before a session is retired, its unsaved files, decisions, pending approvals, branches and PRs must be inventoried and handed off. No session was retired or reset during this audit.

## What is actually expensive

The largest measured issue is accumulated context in long-running conversations. Conductor's read-only database reports:

| Chat | Context tokens | Window used | Last message, UTC | State at inspection |
|---|---:|---:|---|---|
| MAIN / kuala-lumpur | 587,706 | 58.77% | Nov 4, 22:55 | idle |
| V6 design / bangkok | 721,891 | 72.19% | Nov 4, 22:35 | idle |
| BABYSITTER / georgetown | 241,627 | 24.16% | Nov 4, 23:01 | idle |
| Testing / doha | 29,335 | 2.93% | Nov 3, 21:46 | idle |
| Technical testing / nassau | 29,281 | 2.93% | Nov 3, 21:46 | idle |
| Newly opened / sofia | 0 | not reported | Nov 5, 00:03 | idle |

These sessions are configured as `opus-5-5-1m`. Idle is not finished and does not establish that a session has no open work. An idle session does not burn tokens just because it exists; new model calls and scheduled wakes do. This Codex audit session is separate and was not changed to another model.

MAIN is near the existing 60% handoff threshold; V6 design is above it. This supports preparing a lossless handoff at a safe task boundary, not clearing either chat now. Restarting the app or switching accounts resumes the same large history; it is not a fresh-context handoff.

### Startup files

Measurements at the main checkpoint; KB below means 1,000 bytes. Tokens are a rough bytes/4 planning estimate, not tokenizer output or subscription metering.

| File | Lines | Bytes | Estimated tokens |
|---|---:|---:|---:|
| CLAUDE.md | 13 | 769 | 192 |
| ops/MISSION.md | 26 | 2,250 | 563 |
| ops/AGENTS.md | 77 | 6,822 | 1,706 |
| ops/DECISIONS.md | 212 | 58,104 | 14,526 |
| ops/HANDOFF.md | 46 | 8,143 | 2,036 |
| Total prescribed startup reads | 374 | 76,088 | 19,022 |

CLAUDE.md is automatically loaded; the other files are prescribed reads, not all automatically injected. The shorter repeat-task rule says Current rules, not the entire DECISIONS history. That distinction changes savings estimates.

DECISIONS contains 35 numbered current rules, about 17,136 bytes including their section, and 40,587 bytes of history. Several rules have multiple paragraphs, exceptions and pending transitions. HANDOFF already meets the 60-line target; long lines still make it expensive. It is dated October 29 and says 31 rules, while DECISIONS now contains 35. SPEND is 42,212 bytes, LOG is 92,236 bytes, and `du -sh docs` is 18 MB here, not the supplied 30 KB and 40 MB estimates. None of those sizes proves their entire content is loaded.

### Transcript evidence

Tool calls were deduplicated by tool-use ID: the transcripts contain mirrored records. Counts of references are not claims that the files were fully read each time.

| Transcript | Distinct Agent calls | Distinct sends | DECISIONS references in Read/Bash | HANDOFF references | Explicit compact boundaries |
|---|---:|---:|---:|---:|---:|
| MAIN | 48 | 227 | 18 | 2 | 1, Nov 3 23:18 UTC |
| V6 design | 1 | 15 | 11 | 2 | 0 |
| BABYSITTER | 0 | 0 | 9 | 5 | 0 |

Agent calls include launches/resumes and are not a live-agent census. MAIN's calls specify Opus 37 times, Sonnet 8 times and inheritance 3 times. These are historical calls, not approval to keep using Sonnet for judgment or building under the new instruction.

A bounded approximately 2 MB tail of MAIN has 45 distinct sends and 81 unique API message IDs. Reported usage totals in that sample: 39,033,092 cached input tokens, 1,122,182 cache-creation tokens, 210 other input tokens, 47,432 output tokens. That is about 97.2% cached input by token volume. Caching is working; it does not make a half-million-token context free. Do not read this cumulative reuse as 39 million new tokens or convert it directly into a five-hour quota percentage.

Largest serialized tool-result contents in sampled tails were about 269 KB in V6 design and 402 KB in BABYSITTER. Serialization may include structured content; these are not exact prompt-token counts. They warrant bounded output and artifact links, not removing visual QA.

The available evidence does not establish repeated auto-compaction as the main cause. MAIN has one explicit compact marker and V6 design none in the inspected parent transcripts. Child transcripts and earlier sessions may differ.

### MCP, plugins and memory

The default `~/.claude.json` names `node_repl` and `story_studio`; the three Hats profile config files have no direct MCP entries. Shared settings list no enabledPlugins; this checkout has no `.claude` configuration. One Brand Studio auto-memory index was found, 361 bytes. No global CLAUDE.md was found at the checked ancestor locations.

This does not prove the actual sessions have no other integrations: account connectors and Conductor can supply them. MAIN actually calls Google Drive search six times. V6 design uses Claude-in-Chrome and Conductor's question tool. Preserve these. No matching QuickBooks, Shopify or Notion use was found in the three parent transcripts or the bounded tracked-source search. That is evidence for further checking, not proof they are unused by every child or workflow.

Exact live system-prompt, tool-schema, skill-list and plugin-token totals remain unmeasured. Use the installed Claude `/context` and `/usage` diagnostics in a controlled fresh test after approval; do not assume all advertised schemas load eagerly. No paid audit agent or model call was started. Four web search queries were used, followed by direct official-document lookups. LOG was never read in full.

## Ranked changes for approval

N=24 below is the number of rows in the standing-session table, not a claim that 24 agents are currently running. Multiply by the actual number of starts to estimate a real workload. Savings overlap where noted and are not guaranteed quota savings.

| Order / separate PR | Estimated tokens saved per startup × N | Capability or workflow risk | How the risk is covered | Undo |
|---|---|---|---|---|
| 1. Split DECISIONS into RULES plus verbatim archive | History-only: about 10,147 × 24 = 243,522. If a complete 4 KB RULES is validated: about 13,526 × 24 = 324,624 | Dropping exceptions; freezing outdated V5 rules; mixing live behavior with approved V6 intent | First preserve exact original bytes. Map all 35 entries and newer decisions. Keep live/approved/pending status. Do not force 4 KB by losing a rule | Revert only this PR; archive remains reachable |
| 2. Short HANDOFF, archive older text | Target 3 KB: about 1,286 × 24 = 30,858 | Losing open work or pending questions | Under 60 lines AND a byte budget; retain owners, open PRs, next steps and approval blocks; exact archive check | Revert PR |
| 3. CLAUDE read lists and context hygiene | CLAUDE + full AGENTS 7,591 bytes to roughly 2 KB: about 1,398 × 24 = 33,546, before role-specific reads | Omitting hard rules or required role duties | Always load rules, handoff, mission, hard constraints; route role/QA/deploy details by task; require archive lookup on uncertainty | Revert PR |
| 4. Reconcile finished/duplicate sessions | No honest fixed startup saving; zero for merely idle sessions | Abandoning PRs, branches or unsaved decisions | Per-session evidence and your separate yes; owner handoff first; preserve records | Reopen preserved session and restore table entry |
| 5. Narrow default searches and output | 0 inherent startup saving; avoids large result bursts | Hiding history or design assets needed for judgment | Explicit source paths and text globs; history lookup remains allowed; visuals still inspected when relevant | Remove search defaults |
| 6. Project-only MCP/plugin cleanup | Unmeasured; modern tool deferral may already save most schema cost | Removing a needed integration | Verify actual tool listing, child use and workflow requirements first; keep Google Drive, browser and Conductor; never change global settings | Restore that project's settings |
| 7. On-demand QA, SPEND, handoff, deploy and V6-check skills | Mostly included in row 3; no double-count | Agent forgets a required procedure | CLAUDE lists each name and trigger; mandatory task gates; deploy still requires authorized owner | Revert skill PR and restore instructions |
| 8. Scout / verifier / builder definitions | Unmeasured; subagent starts also cost tokens | Weak judgment or tool access loss | Haiku only file:line search; Sonnet only executing checks; Opus for building/debugging/design/QA judgment/V6. Verify model and worktree on launch | Remove definitions through an approved revert |
| 9. Event-driven, short coordination and bounded logs | Runtime saving; no fixed per-start figure | Missing a review or treating truncated output as success | Same roles and PR flow; report changes/blocks/completion, not unchanged polling. Full judgment for server, prompts, V6 AND rule changes. Preserve command exit codes and full logs as artifacts | Restore messaging convention |
| 10. Independent parallel tasks, explicit ownership | No guaranteed saving; intended to prevent duplicated work | File collisions or lost integration work | One owner per module, one builder worktree/branch, same reviewers. Merge promptly only after your existing approval gate | Revert convention; keep branches/workspaces until authorized |
| 11. Safe handoffs and tested compaction hooks | Adds about 1,750 tokens per compact at 7 KB rules+handoff; prevents much larger reconstruction | Lost state, overwritten checkpoints, hook failure or duplicate context | Per-session filenames; explicit next-step note; bounded output; hooks tested inside Conductor before rollout; handoff at safe boundaries near 60% | Disable only added hooks and preserve checkpoint files |

If rows 1–3 reach their targets without losing meaning, startup reads fall from 76.1 KB / ~19,022 tokens to about 11.25 KB / ~2,813 tokens: roughly 85% less startup-file context, or ~389,000 fewer tokens across 24 starts. This is NOT an 85% reduction in total usage. The conservative first step is to stop reading 40.6 KB of history on every startup. Task-specific reads, MCP, system prompts, images, output and accumulated conversation remain additional costs.

## No-rule-loss review gate

No rule has been trimmed in this PR. The adjacent coverage inventory lists all 35 source rule IDs with their line ranges and byte hashes. Its proposed destination keeps every ID: a short RULES entry plus its complete archived text. This checks inventory, not semantic equivalence of a future summary.

Before approving the RULES rewrite, the side-by-side review must contain: complete source clause; proposed short clause; full-entry archive link; status (live, approved V6, pending or explicitly superseded); newer approval evidence; and reviewer sign-off. A rule with ten sub-bullets needs ten checks, not a single checkmark for its number. Any uncertainty stops that individual rewrite, not unrelated work.

Known reconciliation blocks: rule 33 still makes V5 authoritative; rules 3/34 retain older cost caps; rules 4/5/11/21 contain conditional transitions. The current user instruction also overrides the old deletion and model recommendations. The preserved V6 build plan and exact later user approvals must resolve these before publishing an authoritative short RULES file. Neither old main text nor an open PR alone is proof of the newest approval. A full no-in-force-rule-dropped certificate would be premature today.

For each future trim PR, archive the original file byte for byte and test its SHA-256 against the pre-change file. Also compare removed-line multisets against archived lines, retaining whitespace and duplicate occurrences. Link the short file to stable archive entries. The test proves text preservation; Opus QA separately checks meaning and precedence. Keep all pending decisions visible.

## Sessions: candidates, not retirement approvals

`ops/AGENTS.md:40–66` has 24 standing entries with older `session_...` IDs. The local Conductor sessions use UUIDs. The table is not an authoritative inventory of this week's V6 child agents, and neither a similarly named branch nor a shared GitHub author proves ownership.

| Candidate | Evidence | Last activity / replacement / open-work proof | Recommendation |
|---|---|---|---|
| Researcher | Table explicitly says Starpop phases 1–2 done | Actual last activity, branch and PR ownership not linked to this old ID | First candidate for your approval after artifact/PR handoff |
| Builder-Screens; Builder-Screens-3 | Both remain beside Builder-Screens-4; Screens-3 says it replaced Screens-2 | Does not prove Screens-4 replaced every duty; last activity and branches unknown | Investigate; do not retire |
| Builder-Server-5 | Says it replaced -3 and -4, not that it was replaced by -7/-8 | These have different named assignments; no proof of duplication | Keep pending owner evidence |
| QA-Live 6 | Supposed to exist only while its run is active | Completion, test report and ownership not established | Verify run complete before asking to retire |
| Status Desk | Standing relay role | Current session mapping and unresolved deliveries unknown | Keep role; propose event-driven relays, not removal |
| Testing / Technical testing | Local database shows idle since Nov 3 | Idle is not completed or duplicate | Keep |
| MAIN and V6 design | Large context; MAIN near and design above restart threshold | Twelve open PRs remain in the repo; complete handoff ownership not established | Prepare handoff after approval; do not reset |

The remaining standing roles also remain unchanged. At inspection the open PRs were #1299, #1308, #1311, #1313, #1318, #1324, #1327, #1329, #1331, #1332, #1333 and #1334. The cut-editor PR #1311 explicitly says it is stacked on #1299: an existing dependency to preserve, not automatically rebase. Current PR titles alone cannot validate that full QA occurred or that a worker is redundant.

## What the current documentation changes about the plan

- `@imports` load the imported text; they are not lazy pointers. Use plain paths for history and imports only for genuinely always-needed small files. [Claude memory](https://code.claude.com/docs/en/memory)
- MCP tool search now defers tools by default on supported models. Do not disable ToolSearch to save tokens: that can load definitions upfront. Project `disabledMcpServers` differs from `.mcp.json` approval settings. [Claude MCP](https://code.claude.com/docs/en/mcp)
- Project/local plugin settings permit scoped changes; no global disable is proposed. Confirm installed IDs and dependencies before selecting any. [Plugin management](https://code.claude.com/docs/en/plugins/install), [settings scope](https://code.claude.com/docs/en/settings)
- Permanent `Read` deny rules conflict with keeping archives intentionally accessible. Prefer search scope and on-demand access for these files; reserve deny for material that truly must not be read. `.claudeignore` is not an effective control. [Permissions](https://code.claude.com/docs/en/permissions)
- Skill descriptions occupy context; their full instructions load when invoked. Avoid preloading every skill into every custom agent. [Skills](https://code.claude.com/docs/en/skills)
- Custom agents can specify models/tools and inherit CLAUDE.md. Built-in Explore/Plan differ. Worktree isolation must be verified on the actual launch; named teammates can have different isolation behavior. A scout is not a QA judge. [Subagents](https://code.claude.com/docs/en/sub-agents)
- Cache-friendly work keeps the tool set/model stable during a task. File edits do not automatically invalidate the entire cache; CLAUDE.md updates are loaded at lifecycle boundaries. Avoid repeated account/model/plugin changes and gratuitous restarts. [Prompt caching](https://code.claude.com/docs/en/prompt-caching)
- Conductor documents repository instructions, skills and agent-specific MCP configuration. It does not establish that our proposed compaction hooks have fired in these sessions. [Conductor agent behavior](https://www.conductor.build/docs/reference/agent-behavior), [Conductor MCP](https://www.conductor.build/docs/reference/mcp)

### Hook plan, not installed configuration

Use `SessionStart` with matcher `compact` to restore small RULES/HANDOFF content, and `PreCompact` with `manual|auto` to save state. SessionStart text can add context; PreCompact input has session ID, cwd, transcript path, trigger and custom instructions—not an authoritative next-step field. The agent must maintain its next step explicitly. Hook stdout has a 10,000-character cap, so assert size rather than silently truncating. [Hook reference](https://code.claude.com/docs/en/hooks)

Checkpoint current branch/HEAD, porcelain status, open PR references and an agent-written next step into `ops/sessions/<session-id>.md`, atomically and without overwriting another agent. Preserve previous checkpoints. If PR lookup fails, record failure and retain the last known PR list. Git status alone does not back up uncommitted file contents. Before any restart, verify those contents and pending decisions are safely preserved; before retirement, get your yes. Do not block auto-compaction or disable its fallback until recovery has been tested.

After approval, test manual compaction and the automatic lifecycle in an isolated Conductor test session, with markers proving both hooks executed and the correct rule version/next step returned. Include hook failure, missing files and concurrent sessions. No hook success is claimed now. The earlier Hats rate-limit hook test is a different event and does not prove compaction recovery.

## Alternatives to adding more accounts

Claude's current help distinguishes context length from account-wide usage limits. Paid-plan session and weekly allowances are shared across Claude surfaces; more workspaces on the same account do not create more quota. Exact remaining allowance and reset times must come from each account's Usage view, not inference from transcript bytes. [Usage limits](https://support.claude.com/en/articles/11647753-how-do-usage-and-length-limits-work)

For continuous Opus work, compare a larger eligible plan or explicitly budgeted usage credits/API billing after measuring the lean workflow. Those are capacity purchases, not token savings, and they cannot promise zero interruption or unchanged spending. Keep the existing models and tooling; do not turn on paid overage as part of this audit. [Usage credits](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans)

The installed local Hats build selects a backup at the next process start after a confirmed rate limit. It does not reduce token use, refresh quota, compact history or automatically resume a stopped chat. Its one-hour cooldown is not Anthropic's reset time. At audit time secondary had a recorded cooldown; primary/third were eligible but their actual remaining quota was unknown. This is not a substitute for the workflow changes above.

## Approval and acceptance

Recommended first approval: rows 1–3, with the rule-by-rule reconciliation gate and one reversible PR each. Then row 9's coordination/output policy and row 11's tested handoff protection. Keep rows 4 and 6 individually gated by evidence and your yes. Rows 7–8 and 10 remain optional proposals; they do not replace existing team roles.

For the comparison after approved changes: use a fresh Opus agent on one bounded real task, retain the same tests, tools, review standard and acceptance criteria as a similar prior task, and record startup bytes, `/context` breakdown, unique API usage/cache counters, wall time, test results and any missed rule. Include role-specific reads in the after total. Treat differences as indicative, since task complexity varies. A missing decision, worse output or slower critical path blocks rollout; revert only the offending PR.

Final acceptance must show archive hashes and removed-line checks passing, verified compaction recovery, the model policy intact, session count before/after with individual approvals, and the V6 checkpoint diff still containing only PRODUCT.md. Only after approved implementation, log the new rule and update the context-hygiene section and session roster. No such live instruction edits have been made by this audit.
