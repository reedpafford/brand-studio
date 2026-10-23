# Automatic deploy (not switched on)

Today the live server is updated by hand (see `deploy/README.md`):
`cd ~/brand-studio/deploy && git pull && docker compose up -d --build`.

If Reed decides to deploy automatically on every merge to main, two changes switch it on.

## 1. Let the deploy run the existing checks first

In `.github/workflows/server.yml`, `web.yml` and `e2e.yml`, replace

```yaml
on:
  pull_request:
  push:
    branches: [main]
```

with

```yaml
on:
  pull_request:
  workflow_call:  # on main, deploy.yml runs this before deploying
```

## 2. Add `.github/workflows/deploy.yml`

```yaml
name: deploy
# On every push to main: run all checks, then update the live server over SSH.
# Needs repo secrets VPS_HOST, VPS_USER, VPS_SSH_KEY (optional: VPS_KNOWN_HOSTS).
on:
  push:
    branches: [main]
  workflow_dispatch:
concurrency:
  group: deploy
  cancel-in-progress: false
jobs:
  server:
    uses: ./.github/workflows/server.yml
  web:
    uses: ./.github/workflows/web.yml
  e2e:
    uses: ./.github/workflows/e2e.yml
  live:
    needs: [server, web, e2e]
    runs-on: ubuntu-latest
    environment: production
    env:
      VPS_HOST: ${{ secrets.VPS_HOST }}
      VPS_USER: ${{ secrets.VPS_USER }}
      VPS_SSH_KEY: ${{ secrets.VPS_SSH_KEY }}
      VPS_KNOWN_HOSTS: ${{ secrets.VPS_KNOWN_HOSTS }}
    steps:
      - name: Check the server secrets are set
        id: secrets
        run: |
          if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ] || [ -z "$VPS_SSH_KEY" ]; then
            echo "::warning::Not deployed: add VPS_HOST, VPS_USER and VPS_SSH_KEY repo secrets."
            echo "ready=false" >> "$GITHUB_OUTPUT"
          else
            echo "ready=true" >> "$GITHUB_OUTPUT"
          fi
      - name: Set up SSH
        if: steps.secrets.outputs.ready == 'true'
        run: |
          install -m 700 -d ~/.ssh
          printf '%s\n' "$VPS_SSH_KEY" > ~/.ssh/id_deploy && chmod 600 ~/.ssh/id_deploy
          if [ -n "$VPS_KNOWN_HOSTS" ]; then
            printf '%s\n' "$VPS_KNOWN_HOSTS" > ~/.ssh/known_hosts
            echo "STRICT=yes" >> "$GITHUB_ENV"
          else
            echo "::warning::VPS_KNOWN_HOSTS is not set, so the server's identity is not checked."
            echo "STRICT=accept-new" >> "$GITHUB_ENV"
          fi
      - name: Pull, rebuild and wait for /api/health
        if: steps.secrets.outputs.ready == 'true'
        run: |
          ssh -i ~/.ssh/id_deploy -o StrictHostKeyChecking="$STRICT" -o ConnectTimeout=20 \
            "$VPS_USER@$VPS_HOST" bash -s <<'REMOTE'
          set -euo pipefail
          cd ~/brand-studio
          git pull --ff-only
          cd deploy
          docker compose up -d --build --remove-orphans
          domain=$(grep -E '^DOMAIN=' .env | cut -d= -f2-)
          for i in $(seq 1 30); do
            if curl -fsS --max-time 5 "https://$domain/api/health"; then
              echo; echo "Live at https://$domain"; docker image prune -f >/dev/null; exit 0
            fi
            sleep 5
          done
          echo "::error::https://$domain/api/health did not come up within 150 seconds."
          docker compose ps -a
          docker compose logs --tail 40 migrate api caddy
          exit 1
          REMOTE
```

Until the secrets exist it skips with a warning, so main stays green. The **Run workflow** button
on the Actions tab (workflow_dispatch) deploys on demand.

## Reed's secrets (GitHub → Settings → Secrets and variables → Actions)

1. On the VPS, make a key used only for deploys:
   `ssh-keygen -t ed25519 -N "" -f ~/.ssh/deploy_key && cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys`
2. Add the secrets:
   - `VPS_HOST`: the VPS address.
   - `VPS_USER`: the login user (the one that owns `~/brand-studio` and can run Docker).
   - `VPS_SSH_KEY`: the whole contents of `~/.ssh/deploy_key` (the private half).
   - `VPS_KNOWN_HOSTS` (recommended): the output of `ssh-keyscan <VPS address>`, run from your
     own computer, so GitHub refuses to connect to an impostor.
3. Delete `~/.ssh/deploy_key` from the VPS once it is saved in GitHub.
