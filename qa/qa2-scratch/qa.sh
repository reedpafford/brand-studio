#!/usr/bin/env bash
# usage: qa.sh NAME ref1 [ref2...]  -> worktree of origin/main merged with refs, runs all checks
set -uo pipefail
name=$1; shift
cd /home/user/brand-studio
wt=/home/user/qa-$name
git worktree remove --force $wt 2>/dev/null; git branch -D qa-$name 2>/dev/null
git worktree add -q -b qa-$name $wt origin/main || exit 1
cd $wt
for r in "$@"; do git merge -q --no-edit $r || { echo "MERGE CONFLICT $r"; git diff --name-only --diff-filter=U; exit 1; }; done
git log --oneline -1
log=${QA2_OUT:-/tmp/qa2}/$name.log
{
if ! git diff --quiet origin/main -- server; then echo "== server"; (cd server && uv run pytest -q 2>&1 | tail -3); fi
cd web
echo "== ci"; npm ci --silent >/dev/null 2>&1 && echo ok
echo "== api"; npm run -s api >/dev/null 2>&1; git status --short src/ | grep schema || echo "schema unchanged"
echo "== lint"; npm run -s lint 2>&1 | tail -5
echo "== typecheck"; npm run -s typecheck 2>&1 | tail -5
echo "== vitest"; npx vitest run 2>&1 | grep -E "Tests|Test Files|FAIL|✗|×" | head -20
[ -n "${EXTRA:-}" ] && cp $EXTRA e2e/
echo "== e2e"; PW_CHROMIUM=$(ls -d /opt/pw-browsers/chromium-*/chrome-linux*/chrome | head -1) npx playwright test 2>&1 | grep -vE "^\s+✓" | tail -40
} > $log 2>&1
cat $log
echo "== outside web/ (must be empty)"; git diff --name-only origin/main...HEAD -- . ':!web' | grep -v '^ops/' ; git diff --name-only origin/main...HEAD -- web/src/api/schema.d.ts
[ -f test-results/qa2-audit.json ] && cp test-results/qa2-audit.json ${QA2_OUT:-/tmp/qa2}/$name-audit.json
