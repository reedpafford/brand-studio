---
name: code-map
description: Optional local Graphify navigation for broad cross-file code questions. Use ordinary search for exact strings and always read the actual source before editing.
---

Use `python3 scripts/graphify_local.py query "specific code question"` when a cross-file relationship is unclear. If setup or a rebuild is needed, the command says so; ordinary search remains available immediately.

The index is code only. It does not contain the product approvals, specifications, prompts, design boards or current rules. Follow CLAUDE.md's read schedule independently. Never use this skill to skip required context or QA, infer a product approval, or resolve V5/V6 precedence.

Read cited source files in the workspace. Graph relations are hints, not proof. If a result is truncated, ambiguous, missing or suspicious, narrow the query or use normal search. Do not increase the budget repeatedly to retrieve the whole repository.

Each workspace builds its own index. The wrapper refuses queries after a source, branch or commit change until rebuilt. No global hooks, read restrictions, model changes, cloud upload or semantic model calls are configured.

Setup once: `python3 scripts/graphify_local.py setup`
Build when useful: `python3 scripts/graphify_local.py build`
