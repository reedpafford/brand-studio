# Brand Studio

Internal, brand-organised AI video studio for Reed's team. Videos are guided by a script or brief:
Brief → Script → Breakdown → Storyboard → Clips → Review → Final cut. "Quick clip" (one-off generation) also exists, always inside a brand.

## Read schedule
This schedule replaces older read-first lists in ops files, not their substantive rules. Newer user decisions still take precedence. Preserve the existing product outputs, model capability, approval behavior and QA standard.

### ALWAYS READ
- `ops/RULES.md`, in full. Until it exists, read the **Current rules** section of `ops/DECISIONS.md`, including every sub-bullet; history begins at `## History`.
- `ops/HANDOFF.md` and `ops/MISSION.md`.
- The hard rules, flow, size budgets and limits below.
- After compaction and before a new task, re-read only RULES (or the Current rules fallback) and HANDOFF. Then load the task-specific material below when its trigger applies.

### READ ONLY WHEN NEEDED
- `ops/AGENTS.md`: your role's full duties when taking an assignment; **QA review checklist** for every PR; **Context hygiene** before any restart or handoff; **Sessions** before routing or handing off work. These reads are mandatory when triggered.
- `ops/archive/` and decision history: reasons, older decisions, unresolved precedence or historical work. If unsure why a rule exists or whether an old decision applies, grep ops/archive/ before acting or ask the Producer.
- `docs/next/*`, design specifications and existing skills: the sections relevant to the assigned task. V6 work must read its approved specification, build plan and applicable user answers; preserve visual and semantic QA.
- `ops/SPEND.md`: current approved test budget and required logging before any paid call. Historical spend only when reconciling it. `ops/LOG.md`: targeted historical lookup, not a full startup read.

The complete previous startup file is preserved in `ops/archive/CLAUDE-before-context-2026-11-04.md`. No archive entry silently overrides a newer approval.

## Hard rules
- Keys never go in code, commits, logs or chat. Server-side only.
- No paid call (Replicate, Claude API) outside tests the Producer approved. Log every paid call in `ops/SPEND.md`.
- Only the Release agent merges or deploys (until it exists, the Producer does).
- Keep it small: see the budgets in `ops/AGENTS.md`. Prefer deleting code to adding it.
- Plain language in anything Reed reads.

## Flow
Producer opens issue → (Designer sketches screens) → Builder opens PR from `agent/<name>/<topic>` → QA (+ Steward, Designer) review → merge → Scribe logs → Explorer checks live.
- **Before every push, check the PR is still open.** A push to a merged PR never ships; put it in a new PR from the base branch instead.
- **Branch every PR from its base (`main` or `next`), never from another open PR.** Squash merges break stacked PRs.
- **After QA passes a head, don't push to it** unless the Producer asks; a new head needs a new pass.

## Size budgets (Steward enforces)
- Whole app: about 36,000 lines of app code (server/app Python plus web/src without tests or the generated schema.d.ts) is a guide, not a hard cap (Current rules 26). The app can grow when needed, but no redundant or duplicate code, and each change deletes what it replaces. The Steward reports the count on every PR. Any file over 400 lines needs a reason.
- One test per behaviour; no snapshot dumps. Delete tests with the code they cover.
- ops/ files: HANDOFF under 60 lines, LOG trimmed monthly, DECISIONS one line each.

## Limits
- Paid calls only within the $15/week cap, logged in ops/SPEND.md, asked through the Producer.
- Never touch story-studio or its live server.
- Never put keys in code, commits or chat.

## Scope of this efficiency change
- Preserve every product rule, exception, provider prompt and QA requirement. This read schedule authorizes no changes to app outputs or functionality.
- Opus is required for building, debugging, design, QA judgment and V6. Haiku is only for mechanical file:line search; Sonnet is only for running checks and reporting pass/fail. This user instruction takes precedence over older model labels in the role table.
- No deletion, force-push, merge, deployment, branch/workspace retirement or session retirement without Reed's explicit approval. Archiving text retains it word for word with a verification check.
- Resolve older V5 wording against the newer approved V6 instructions before V6 work; ask the Producer when the approval evidence is unclear. An efficiency edit does not settle a product decision.
