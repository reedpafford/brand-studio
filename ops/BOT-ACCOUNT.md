# Bot account: so GitHub can tell you from the agents

Today every agent acts as you (reedpafford), so GitHub cannot tell your approval from an agent's.
A second account for the agents fixes that. Only you can do steps 1 to 4.

1. **Create the account.** New GitHub account, e.g. `brand-studio-agents`, with its own email
   (a Gmail "+agents" alias may not work; use a separate inbox).
2. **Invite it.** Repo, Settings, Collaborators, add the account with **Write** access. Accept the invite while
   logged in as the bot.
3. **Make its token.** Logged in as the bot: Settings, Developer settings, Fine-grained tokens. Limit it to
   this one repo. Permissions: Contents, Pull requests, Issues = Read and write. Nothing else
   (no Administration, no Secrets).
4. **Give agents the token.** Either works:
   - Set `GH_TOKEN` in the Conductor workspace environment (Repository settings, environment variables), or
   - in each session run `gh auth login --with-token` and paste it.
   I could not check Conductor's docs from here, so confirm which of the two it offers.
   Never put the token in code, commits or chat.
5. **Tell the lead.** The lead then runs `scripts/protect-branches.sh` (as you, it asks before changing
   anything). That makes `main` and `next` require a pull request and passing checks, and requires your
   approval for guide changes.

## What changes for you
- Agents open and merge PRs as the bot. The Release and Producer agents merge as the bot too.
- A PR that touches the guides, `rules.md`, `DECISIONS.md`, `MISSION.md`, `CODEOWNERS`, the workflows or the protect script cannot merge until you
  click **Approve** on its latest commit. The `guides-guard` check turns green after that.
  If it stays red after you approve, press "Re-run" on the check.
- Any other PR needs no click from you.
- You can still merge in an emergency (admins are not enforced).
- Your own PRs are never blocked by the guard.
