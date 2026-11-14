#!/usr/bin/env bash
# Sets branch protection on next, the only branch. Safe to re-run (it replaces the rules each time).
# Needs `gh` logged in as Reed (repo admin). Reed himself is NOT enforced, so he can still merge in an emergency.
set -euo pipefail
REPO=${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner)}
# Check names = job names in .github/workflows (server and web both call theirs lint-test).
CHECKS='["guides-guard","lint-test","browser-tests"]'
BRANCHES=(next)

cat <<MSG
About to set protection on $REPO for: ${BRANCHES[*]}
  - changes must come through a pull request
  - required checks: guides-guard, lint-test (server and web), browser-tests (e2e)
  - code owners (Reed) must approve changes to guide files
  - new commits dismiss old approvals
  - no force pushes, no deleting the branch
  - admins (Reed) are not enforced
MSG
read -r -p "Type yes to apply: " ok
[ "$ok" = "yes" ] || { echo "Cancelled, nothing changed."; exit 1; }

for b in "${BRANCHES[@]}"; do
  gh api -X PUT "repos/$REPO/branches/$b/protection" --input - <<JSON
{
  "required_status_checks": {"strict": false, "contexts": $CHECKS},
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
  echo "Protected $b"
done
