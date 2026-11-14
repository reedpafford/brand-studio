# Getting Brand Studio live (phone-friendly guide)

## Old production site (retired 9 Nov 2026)

Reed's site is now the former test site: **https://thisisatestingenv.online** (also
`https://srv2091584.hstgr.cloud:8443`), branch `next`, folder `~/brand-studio-next`, Compose
project `brand-studio-next`. It deploys from `next` (`deploy/next/README.md`).

The old production site (https://srv2091584.hstgr.cloud, branch `main`, folder `~/brand-studio`,
Compose project `brand-studio`) is **stopped and kept as a snapshot. Nothing of it was moved or
deleted.** Every deploy from `main` now runs `deploy/remote-deploy.sh`, which only keeps it
stopped: it never rebuilds, resets or restarts it.

**Its web server keeps running.** The old site's Caddy container holds ports 80, 443 and 8443 for
the whole server and is also the front door of Reed's site. Never stop it (or run
`docker compose down` in `~/brand-studio/deploy`) until a separate front door replaces it.

**What the snapshot is** (all on the server):
- The old volumes `brand-studio_db` (database) and `brand-studio_files` (uploads), untouched.
- `~/old-production-snapshot/`: `old-production-db.sql.gz` (a fresh database dump made just
  before it stopped), `old-production.env` (its settings, including the database password),
  `code-commit.txt` (the code it ran), `images.txt`, `volumes.txt`, `nightly-backups.txt`, and
  `DONE` (when it was made).
- Its images, also tagged `brand-studio-server:old-production` and `brand-studio-web:old-production`.
- The folder `~/brand-studio` (its code and `deploy/.env`), never changed again. Don't delete it:
  Reed's site's deploy reads the server's address from `~/brand-studio/deploy/.env`.
- Its nightly backups in `~/brand-studio/deploy/backups/` (database plus files), kept for good:
  the nightly job was removed, so nothing prunes them.

**Never run** `docker system prune`, `docker container prune`, `docker volume prune`, or
`docker compose -p brand-studio down -v`: each destroys part of the snapshot.

### Bringing the old site back
Do these in Hostinger → VPS → **Web console**. First revert the "retire the old site" change on
`main` (or the next push to `main` stops it again); that revert also redeploys it (option B's
last line).

**A. Its containers are still there (the normal case), about 1 minute:**
```
cd ~/brand-studio/deploy
docker compose -p brand-studio start db && sleep 10
docker compose -p brand-studio start api worker claude-worker reel-worker
curl -fsS https://srv2091584.hstgr.cloud/api/health
```

**B. Its containers were removed but the volumes are still there, about 2 minutes:**
```
docker tag brand-studio-server:old-production brand-studio-server
docker tag brand-studio-web:old-production brand-studio-web
cd ~/brand-studio/deploy && git log -1 --format=%h   # should match ~/old-production-snapshot/code-commit.txt
cp ~/old-production-snapshot/old-production.env .env   # only if .env was lost
docker compose up -d --no-build   # reattaches the untouched brand-studio_db and brand-studio_files
```
Or revert the retire change on `main`: the old deploy rebuilds and starts it on the same volumes
(about 15 minutes). Either way Reed's site may blink for a few seconds while the web server restarts.

**C. The old database volume is lost:** the database from the snapshot dump; the files from the
newest nightly backup (the only copy of the old uploads besides their volume):
```
cd ~/brand-studio/deploy
docker compose up -d --no-build db && sleep 10
gunzip -c ~/old-production-snapshot/old-production-db.sql.gz | docker compose exec -T db psql -q -U brand -d brand
# only if the files volume is lost too (replace the date):
docker compose run --rm --no-deps -T api tar -xzf - -C /data < backups/files-2026-11-08.tar.gz
docker compose up -d --no-build
```

A Hostinger server snapshot (VPS → **Snapshots & backups**) also exists from 9 Nov, but restoring
it rolls Reed's site back too: for disasters only.

---

## How the old site was set up (Parts 1–9, kept for reference)

Everything runs in Docker on one Hostinger VPS: the database, the app, the background worker,
and Caddy, which serves the website and gets the HTTPS certificate by itself.

**GitHub did the deploying.** Until 9 Nov, every change merged into `main` went live by itself:
GitHub ran all the checks, logged in to the VPS, updated the code, restarted the app and checked
the site answered. Since then a deploy from `main` only keeps the old site stopped (above).

**Before you start**
- About 30 minutes, a phone (or computer) and a web browser. Use the browser (Safari or Chrome),
  not the Hostinger or GitHub apps: the apps can't do some of these steps.
- A note on your phone to hold a few things for a few minutes. **Delete the note at the end.**
- **Never paste a password, key or code into a chat**, including with Claude. They only go
  where this guide says: the Hostinger console or GitHub's secrets page.

---

## Part 1: The server (Hostinger)

You may have done this already. If you have a VPS with Docker, skip to step 1.4.

**1.1 Buy the VPS.** hostinger.com → **VPS hosting**. **KVM 2** is recommended (2 CPUs, 8 GB
memory); KVM 1 is the minimum. Any data-centre location near your team.

**1.2 Choose the template.** When asked for an operating system, choose **Applications →
Docker** (it runs on Ubuntu). Plain **Ubuntu 24.04** also works: the deploy installs Docker
itself.

**1.3 Set the root password.** On "Secure your VPS access":
1. Under **Create a root password**, tap **Generate**, tap the 👁 eye, copy it.
2. Save it in your password manager (iPhone: Settings → Passwords → **+**, website
   `hpanel.hostinger.com`, user `root`). You'll rarely need it, but keep it.
3. Leave **Add SSH key** empty. Tap through to the end. Wait until the VPS says **Running**
   (2–10 minutes).

**1.4 Find the server's address.** hpanel.hostinger.com → ☰ menu → **VPS** → tap your server.
On its overview page, note two things:
- **IP address**: four numbers with dots (like `123.45.67.89`). Copy it into your note.
- **Hostname**: like `srv1234567.hstgr.cloud`. This already works as a web address.

**1.5 Firewall.** VPS → your server → **Security → Firewall** (sometimes under Settings). If there
are no rules, skip this. If there are rules, make sure TCP **22**, **80** and **443** are allowed.

> **Leave Hostinger's "Docker Manager → Compose" alone.** GitHub runs the app; you don't create
> anything there.

---

## Part 2: The web address

**Easiest: use the server's hostname** (`srv1234567.hstgr.cloud` from step 1.4). Do nothing:
the deploy uses it automatically, with proper HTTPS. You can switch to your own address later.

**Your own address instead** (like `studio.yourdomain.com`):
1. Where your domain is managed (Hostinger: ☰ → **Domains** → your domain → **DNS / Nameservers**)
   tap **Add record**: **Type** `A`, **Name** `studio`, **Points to** the IP from step 1.4,
   TTL default. Save. On Cloudflare, set the cloud to grey (**DNS only**).
2. In Part 5, also add a `DOMAIN` secret with the full address (`studio.yourdomain.com`).
3. It can take up to an hour to start working. HTTPS only works once the name points at the
   server; until then the deploy will fail its health check (harmless; re-run it later).

---

## Part 3: Three codes from the server (the Hostinger Web console)

All three are made on the server itself, so nothing needs a computer.

**3.1 Open the console.** VPS → your server → **Web console** (top right, or on the Docker
Manager page). A black screen opens. If it asks to log in: type `root`, tap return, then the root
password (it won't show as you type), return. You're in when the line ends in `#`.

How to paste a command: long-press in the black area → **Paste**, then tap **return**.
How to copy output: long-press the text, drag the handles over all of it, tap **Copy**. Turning
the phone sideways or pinch-zooming out helps with long lines.

**3.2 The deploy key** (lets GitHub log in to the server). Paste:
```
ssh-keygen -t ed25519 -N "" -f ~/.ssh/deploy_key -q && cat ~/.ssh/deploy_key.pub >> ~/.ssh/authorized_keys && base64 -w0 ~/.ssh/deploy_key; echo
```
It prints **one very long line** of letters and numbers. Copy all of it into your note as `KEY`.
(This also puts the key's public half in the server's list of allowed logins,
`~/.ssh/authorized_keys`. The long line is the private half, written on one line so it's easy to
copy; GitHub turns it back into a normal key.)

**3.3 The server's identity** (so GitHub only ever talks to *your* server). Paste:
```
cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub
```
It prints one line starting `ssh-ed25519 AAAA…`. Copy it into your note as `HOSTKEY`.
This one isn't secret.

**3.4 The setup code** (used once, to create your owner account). Paste:
```
openssl rand -hex 32
```
Copy the 64-character line into your note as `SETUP`.

Leave the console open; you'll come back in step 5.3.

> **If you can't use the console**, a computer works too: on a Mac or Linux, Terminal; on
> Windows, PowerShell. For 3.3 run `ssh-keyscan -t ed25519 <IP>` and use the part after the
> address. For 3.2 run `ssh-keygen -t ed25519 -f deploy_key`, add the contents of
> `deploy_key.pub` in Hostinger under VPS → **Settings → SSH keys**, and paste the whole of the
> `deploy_key` file into the secret instead of the long line (either form works).

---

## Part 4: Open GitHub's secrets page

1. In the browser, go to **github.com/reedpafford/brand-studio** and sign in.
2. **Switch to the desktop site** (the phone layout hides Settings):
   Safari: tap **aA** in the address bar → **Request Desktop Website**.
   Chrome: tap **⋮** → tick **Desktop site**.
3. Tap **Settings** (the ⚙ tab above the code; zoom in if it's small).
4. In the left-hand list: **Secrets and variables** → **Actions**. You're on the **Secrets** tab.

---

## Part 5: Add the secrets

**5.1** For each row: tap **New repository secret**, type the **Name** exactly (capitals and
underscores), paste the value, tap **Add secret**.

| Name | Value | Needed? |
|---|---|---|
| `VPS_HOST` | the IP address from step 1.4 | yes |
| `VPS_USER` | `root` | yes |
| `VPS_SSH_KEY` | `KEY` from step 3.2 | yes |
| `VPS_HOST_KEY` | `HOSTKEY` from step 3.3 | yes |
| `BS_SETUP_TOKEN` | `SETUP` from step 3.4 | yes, for now |
| `DOMAIN` | your own address, e.g. `studio.yourdomain.com` | only if you did Part 2's "own address" |

GitHub never shows a secret again after saving, not even to you; that's normal. To fix a
mistake, tap the secret → **Update**.

**5.2 Don't add the Replicate or Claude keys yet**, and don't create any variables. Paid
generation stays off (see Part 9).

**5.3 Tidy up.** Back in the Hostinger console, paste `rm ~/.ssh/deploy_key` and tap return.
Delete the `KEY` line from your note. Keep `SETUP` until Part 7.

---

## Part 6: The first deploy

1. On GitHub (desktop site), tap the **Actions** tab.
2. In the left-hand list tap **deploy**, then **Run workflow** (right side) → **Run workflow**.
3. A new run appears with a yellow dot. Tap it to watch. It takes about **10–15 minutes** the
   first time (checks first, then the server installs and builds everything).
4. **Success** is a green ✓ on the run. Tap the **live** box: near the end it says
   **Live at https://…** with your address.

If the **live** box is green but says "Not deployed: add VPS_HOST, …", one of the four required
secrets is missing or misnamed: check Part 5 and run it again.

---

## Part 7: Create your account

1. Open **https://\<your address\>/setup** (for example `https://srv1234567.hstgr.cloud/setup`).
2. Fill in the studio name, your name, email and a password, and paste `SETUP` as the setup
   code. Submit: you're signed in as the owner.
3. **Lock setup again:** GitHub → Settings → Secrets and variables → Actions → `BS_SETUP_TOKEN` →
   **Remove**. Then Actions → deploy → **Run workflow** once more; that removes the code from
   the server.
4. Delete your note.

From now on, every merged change deploys by itself. Invite your team from the app.

---

## Part 8: If something goes wrong

- **A red ✗ on a run:** tap it, then the red box. The last lines say what failed (secrets show as
  `***`, never their values). Send the **link to the run** (copy it from the address bar) to the
  Producer or Claude. Don't send screenshots of the secrets page.
- **"did not answer within 5 minutes":** usually the address doesn't point at the server yet
  (Part 2), or ports 80/443 are blocked (step 1.5). Fix it, then **Run workflow** again.
- **"Permission denied (publickey)":** `VPS_SSH_KEY` was copied incompletely. Redo step 3.2 and
  update the secret.
- **"Host key verification failed":** `VPS_HOST_KEY` doesn't match the server (for example after
  rebuilding the VPS). Redo step 3.3 and update the secret.
- Re-running is always safe: it never deletes your data.

---

## Part 9: Later, not now: paid generation

Generation (Replicate video and pictures, Claude writing) costs money and stays **off** until you
decide otherwise. When you're ready, and only with your explicit go:
1. Add two more secrets (Part 5): `REPLICATE_API_TOKEN` (replicate.com → Account → API tokens)
   and `STUDIO_ANTHROPIC_KEY` (console.anthropic.com → API keys). They go to the server only and
   are never shown to editors.
2. Switch it on: Settings → Secrets and variables → Actions → **Variables** tab → **New
   repository variable**: name `BS_GENERATION_ENABLED`, value `true`. Run the deploy.
3. To switch it off again, change the value to `false` (or delete the variable) and run the
   deploy.

**Omni straight from Google (optional; Reed, 10 Nov).** Omni 1.2 video takes cost about $0.07 a
second on Google's own API against $0.11 through Replicate. To switch to Google: put a Gemini API
key (aistudio.google.com → Get API key, on a project with billing) in the server's `deploy/.env`
as `BS_GOOGLE_API_KEY=...` and restart (`docker compose up -d`, or run the deploy). From then on
new Omni takes go to Google and every price shown for them is Google's; nothing else changes, and
no other model moves. To switch back: empty or delete that line and restart, and new Omni takes
go through Replicate at its price again. Let takes that are being made finish first: one already
sent to Google can't be checked on without the key. Note that each deploy rewrites `deploy/.env`
from the GitHub secrets, so for the key to last, the deploy must write it too: a `GOOGLE_API_KEY`
secret passed by the workflow and written by `remote-deploy.sh` (and `next/remote-deploy.sh` for
the test site) as `BS_GOOGLE_API_KEY`, the same way `REPLICATE_API_TOKEN` is. If Google ever
refuses to start a take in the background, add `BS_GOOGLE_BACKGROUND=false`: takes are then made
one at a time in one long call.

**Pausing Google (Reed, 12 Nov).** Google caps how much Omni one key makes a day (it reset at
08:00 UTC and ran out after about 40-50 takes); past it every take fails "RESOURCE_EXHAUSTED".
To carry on through Replicate without touching the key: add an empty file
`deploy/next/google-paused` on `next` and let the deploy run. Omni takes then cost $0.11 a second
instead of $0.07, and Nano Banana pictures go through Replicate too. Delete the file to go back.
Let takes that are being made finish first.

**Real-looking people through KIE (Reed, 12 Nov).** Seedance refuses an uploaded picture of a
real-looking face, but takes a character sheet its own Seedream drew on the same KIE account. So
two models go through KIE (kie.ai): "Seedream 5.5" draws the sheet from the character's notes
($0.0315 a sheet), and "Seedance 2.5 (KIE)" makes the clip with that sheet attached ($0.14 a
second at 480p; Replicate's Seedance 2.5 is $0.10 and stays as it is for the animated styles).
They use the KIE key real songs already use, on the worker only, so on Reed's site nothing new
has to be set: they work while `NEXT_KIE_SUNO` is `true` (that switch is what carries the
`KIE_API_KEY` secret to the server) and stop, unsent and uncharged ("KIE has no key here"), when
it isn't. Their spend counts against `NEXT_REAL_BUDGET_USD` like any paid job, not against the
songs' `NEXT_KIE_BUDGET_USD`. What they make is downloaded only from KIE's file host
`aiquickdraw.com` (the default of `BS_KIE_MEDIA_DELIVERY_HOSTS` in `server/app/settings.py`; the
deploy doesn't write it, and the songs' `NEXT_KIE_DELIVERY_HOSTS` is separate). No style uses
them by itself yet: pick them per sheet and per clip.

---

## Reference

**What each deploy from `main` does since 9 Nov** (`deploy/remote-deploy.sh`, run on the server
by `.github/workflows/deploy.yml`): the first time, makes the snapshot above; every time, stops
the old site's database, API and workers (never its web server), removes its nightly backup job,
saves a copy of Reed's site's database to `~/brand-studio-next/deploy/backups/`, and checks
https://thisisatestingenv.online answers. Safe to run again. Until 9 Nov it installed git and
Docker, downloaded the latest code, wrote `deploy/.env`, rebuilt and restarted the old site, and
kept its nightly backup on (git history has that version).

**Backups.** Until 9 Nov the old site's database and uploads were saved every night to
`~/brand-studio/deploy/backups/`; those files are kept (see the snapshot above). Reed's site's
backups: `deploy/next/README.md`.

**Handy commands** (Web console, from `~/brand-studio/deploy`): `docker compose ps -a` (what's
running and what's stopped), `docker compose logs --tail 50 caddy` (the front door's recent
messages). Never `docker compose restart`, `up` or `down` here unless you're bringing the old site
back. Never delete `deploy/.env` on the server: it holds the old database password and the
server's address.

**Optional hardening, later:** a non-root `deploy` user with a key limited to running the deploy,
instead of `root`. Not needed to go live.
