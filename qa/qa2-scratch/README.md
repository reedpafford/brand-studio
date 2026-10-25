# QA-2 scratch tools (not part of the app; never merged to main)

- `qa.sh NAME ref1 [ref2…]`: makes a worktree /home/user/qa-NAME from origin/main, merges the refs
  (e.g. `pr226 pr230` after `git fetch origin pull/N/head:prN`), then runs npm ci, `npm run api`
  (schema.d.ts must not change), lint, typecheck, vitest and Playwright. Set `EXTRA="a.e2e.ts b.e2e.ts"`
  to copy scratch specs into web/e2e first (zz-* names sort them last, after the suite has made its data).
  The log is written to the scratchpad as NAME.log; the audit json is copied as NAME-audit.json.
- `zz-audit*.e2e.ts`: 390x844 audit of the main pages and every project stage (sideways scroll, controls
  under 44px). `auditdiff.py base-audit.json NAME-audit.json` shows only new or fixed offenders.
  base-audit.json is from main 48ceb31, before the redesign.
- Other zz-* specs are one-off checks: invite walk, sticky Generate, video frame, version panel,
  Variations, Usage (editor gets 404), Bulk create, library publish/read-only.
