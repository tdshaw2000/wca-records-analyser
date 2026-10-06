# Runbook: the WCA Records Analyser on the OCI VM

The app runs on the OCI VM it shares with the scramble challenge app
(`instance-20260924-scramble-challenge`), behind a shared, standalone Caddy edge stack (its own
`caddy` Compose project, not part of either app's). Everything the VM runs is
in [`deploy/`](../deploy); the plan behind it is
[`docs/plans/own-data-backend.md`](plans/own-data-backend.md).

## What runs where

| Piece | Where | What it does |
|---|---|---|
| `publish` job in `.github/workflows/ci.yml` | GitHub-hosted runner | On `main`, pushes `ghcr.io/tdshaw2000/wca-records-analyser:main` (amd64 and arm64) |
| `deploy` job in `.github/workflows/ci.yml` | GitHub-hosted runner | After `publish`, on `main`: SSHes to the VM with a key restricted to one forced command. Never checks out the repo or holds any other credential |
| `~/apps/wca-records-analyser/deploy-launcher.sh` | VM, the forced command | git-updates `~/apps/wca-records-analyser/repo` to `origin/main`, then runs that checkout's `deploy/run_deploy.sh` |
| `deploy/run_deploy.sh` | VM, from the checkout | Installs the checkout's `deploy/` files into `/srv/wca-records-analyser`, then runs `pull_deploy.py` once |
| `pull_deploy.py` | VM, run by `run_deploy.sh` | Pulls `:main`; if its digest is new, pins it in `.env`, restarts `web`, keeps it if it turns healthy, otherwise rolls back |
| `web` service (`compose.yaml`) | VM, container | The app on port 8000 of the edge Caddy stack's Docker network, alias `wca-records-analyser`. No host port |
| `wca-data-build.timer` → `build` service | VM, 03:30 UTC nightly | `python -m wca_data.build` at nice 19, capped at 1 CPU and 1 GB. It also asks for idle IO, which only BFQ honours; the CPU caps are what protect the scramble app |
| `wca-admin-digest.timer` → `collect_admin_log.py` | VM, every 5 minutes | Filters `docker compose logs -t web` down to the lines naming a `wca_id`, for the `/admin` page. Runs as root (the only piece here with docker access) |
| Site block in the scramble-challenge repo's `edge/Caddyfile` | VM, the edge Caddy stack | `wca-records-analyser.duckdns.org` → `wca-records-analyser:8000` |
| `/srv/wca-data/` | VM, owned by uid 10001 | `wca.sqlite` (live) and `wca.sqlite.prev` (the one before). Mounted read-only into `web` |
| `/srv/wca-admin/` | VM, `usage.log` owned by uid 10001 | The filtered access log `/admin` reads, written by root but chowned to the uid the container reads it as. Mounted read-only into `web` |
| `/srv/wca-records-analyser/` | VM, owned by `ubuntu` | `deploy/` kept in sync from the checkout by `run_deploy.sh`, plus `.env` and `bad-images` (never committed) |

## One-time setup

Run on the VM as a user who can `sudo`. Nothing here stops or changes the scramble app until
step 8, and step 8 only reloads its Caddy.

1. **Check the tools.** `docker compose version` must be v2.17 or later (the pull deploy uses
   `up --wait --wait-timeout`). `python3 --version` must be 3.10 or later.

2. **Make the image pullable.** The first merge to `main` after this runbook lands publishes
   the image. A package published from a private repo starts private, so on GitHub open
   *Packages → wca-records-analyser → Package settings → Change visibility* and make it
   **public** (the plan's choice: the VM needs no credentials). Then check from the VM:
   `sudo docker pull ghcr.io/tdshaw2000/wca-records-analyser:main`.

3. **Create the data directory**, owned by the uid the image runs as, and the admin log
   directory (the collector writes `usage.log` into it as root, then chowns the file
   itself to that same uid, so it stays unreadable by any other local account):

   ```sh
   sudo install -d -o 10001 -g 10001 -m 755 /srv/wca-data
   sudo install -d -m 755 /srv/wca-admin
   ```

4. **Set up the deploy checkout, the launcher and the install directory.** Everything for
   this app lives under its own folder, like the scramble repo's `~/apps/scramble-challenge/`
   — a second app on this server gets its own `~/apps/<name>/` alongside it. The `ubuntu`
   user must already be in the `docker` group (the scramble repo's `server-setup.sh` does
   this on first setting up this shared server; check with `groups` if unsure):

   ```sh
   mkdir -p ~/apps/wca-records-analyser
   git clone --depth 1 https://github.com/tdshaw2000/wca-records-analyser \
       ~/apps/wca-records-analyser/repo
   cp ~/apps/wca-records-analyser/repo/deploy/deploy-launcher.sh ~/apps/wca-records-analyser/
   chmod +x ~/apps/wca-records-analyser/deploy-launcher.sh
   sudo install -d -o "$USER" -g "$USER" -m 755 /srv/wca-records-analyser
   ```

   The launcher lives as a sibling of `repo/`, not inside it — a `git reset --hard` would
   otherwise rewrite the very script currently running it (see
   `deploy/deploy-launcher.sh`'s own comment). `/srv/wca-records-analyser` is now owned by
   the deploying user (not root), since the launcher runs as that user over SSH, not as root
   under systemd.

   Generate a dedicated keypair for GitHub Actions to deploy with (not a personal key), and
   restrict it, server-side, to running nothing but the launcher:

   ```sh
   ssh-keygen -t ed25519 -f ~/wca-deploy-key -C "wca-records-analyser deploy" -N ""
   mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys
   RESTRICTION="command=\"$HOME/apps/wca-records-analyser/deploy-launcher.sh\",no-agent-forwarding,no-X11-forwarding,no-port-forwarding,no-pty"
   echo "$RESTRICTION $(cat ~/wca-deploy-key.pub)" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   ```

   In the repo's GitHub settings, add these secrets, then delete the local key files
   (`rm ~/wca-deploy-key ~/wca-deploy-key.pub`):

   - `DEPLOY_HOST` — this server's IP or hostname (the same one the scramble repo's
     `DEPLOY_HOST` secret already points at).
   - `DEPLOY_SSH_KEY` — `~/wca-deploy-key`'s private half.

5. **Write the settings file.** It holds the monitor's ping URL, so it is private:

   ```sh
   sudo install -m 600 /dev/null /srv/wca-records-analyser/.env
   sudoedit /srv/wca-records-analyser/.env
   ```

   - `WCA_DATA_PING_URL=https://hc-ping.com/<uuid>`: make a free healthchecks.io check named
     "wca-data build", period 1 day, grace 3 hours, and paste its ping URL. Every good build
     pings it, whether or not WCA published a new export, so an alert means builds are failing
     or not running.
   - `EDGE_NETWORK=<name>`, only if the edge Caddy stack's network isn't
     `scramble-challenge-edge`. Find it with
     `sudo docker inspect caddy-caddy-1 --format '{{json .NetworkSettings.Networks}}'`.
   - `ADMIN_PASSWORD=<password>`: the `/admin` page's HTTP Basic password (username
     `admin`). Leave it unset to keep that page 404ing (its default).
   - Leave `WCA_IMAGE` out; the pull deploy writes it.

6. **Build the database once** (about four minutes, and up to 2 GB of scratch disk):

   ```sh
   cd /srv/wca-records-analyser && sudo docker compose run --rm build
   ls -la /srv/wca-data     # wca.sqlite, about 720 MB
   ```

   It ends `wca_data build: built (/srv/wca-data/wca.sqlite)`, and the healthchecks.io check
   turns green.

7. **First deploy, and turn on the remaining timers:**

   ```sh
   ~/apps/wca-records-analyser/deploy-launcher.sh      # "pull deploy: deployed"
   sudo cp /srv/wca-records-analyser/systemd/* /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now wca-data-build.timer wca-admin-digest.timer
   systemctl list-timers 'wca-*'
   ```

   This runs exactly what the deploy key triggers over SSH — there's no separate manual
   path to keep in sync. The first `wca-admin-digest` run writes `/srv/wca-admin/usage.log`
   (empty until someone visits a competitor's page); `/admin` only shows anything once both
   that file exists and `ADMIN_PASSWORD` is set.

   If this first deploy fails its health check there is nothing to roll back to, so the
   unhealthy `web` container is left running: `docker compose logs web` (from
   `/srv/wca-records-analyser`) says why. Fix it, remove the digest from `bad-images`, and
   run the launcher again.

   Once a push to `main` has deployed successfully this way (check the `deploy` job in
   Actions, and `WCA_IMAGE` in `/srv/wca-records-analyser/.env` for the new digest), there is
   no longer a polling timer to turn on: deploys only happen when `main` changes.

8. **Route the hostname.** In the scramble challenge repo, add
   [`deploy/caddy/wca-records-analyser.caddy`](../deploy/caddy/wca-records-analyser.caddy)'s
   site block to its `edge/Caddyfile`. That stack has no CI/CD of its own (it changes rarely, so
   updates are manual — see its `edge/README.md`), so this isn't kept current by either app's
   deploys; redo it by hand whenever this site block changes. On the VM, check Caddy can reach
   the app, then validate and **reload** (not restart, which would drop both apps'
   connections):

   ```sh
   sudo docker exec caddy-caddy-1 wget -qO- http://wca-records-analyser:8000/ | head -3
   sudo docker exec caddy-caddy-1 caddy validate --config /etc/caddy/Caddyfile
   sudo docker exec caddy-caddy-1 caddy reload --config /etc/caddy/Caddyfile
   curl -sI https://wca-records-analyser.duckdns.org/ | head -1    # HTTP/2 200
   ```

9. **Uptime check.** Add a free external check (healthchecks.io, UptimeRobot or similar) on
   `https://wca-records-analyser.duckdns.org/`.

## Migrating an already-deployed server to the SSH-triggered deploy

One-time, only for a server that already did steps 1–9 under the old `wca-deploy.timer`
polling deploy. Nothing here stops the running app.

1. Hand off `/srv/wca-records-analyser` from root to the deploying user (it was created with
   `sudo install -d -m 755`; the SSH-triggered path runs as that user, not root):

   ```sh
   sudo chown -R "$USER":"$USER" /srv/wca-records-analyser
   ```

2. Do the rest of step 4 above (clone the checkout, install the launcher, generate and
   restrict the deploy key, add the `DEPLOY_HOST`/`DEPLOY_SSH_KEY` secrets).

3. Run `~/apps/wca-records-analyser/deploy-launcher.sh` by hand once. With nothing new to
   deploy it prints `pull deploy: up to date` — that alone proves the checkout, the launcher
   and the ownership handoff all work, without touching the running container.

4. Merge something to `main` (or re-run the `deploy` job on an existing commit) and confirm
   the `deploy` job in Actions succeeds end to end, then check `/srv/wca-records-analyser/.env`
   on the VM for the new digest.

5. Only once that real push has deployed successfully, retire the old timer:

   ```sh
   sudo systemctl disable --now wca-deploy.timer
   sudo rm -f /etc/systemd/system/wca-deploy.service /etc/systemd/system/wca-deploy.timer
   sudo systemctl daemon-reload
   ```

   `wca-data-build.timer` and `wca-admin-digest.timer` are unaffected — they're not part of
   the deploy mechanism and keep running throughout.

## Everyday operations

- **Deploys are automatic.** A merge to `main` publishes the image, then the `deploy` job
  SSHes out and the VM runs it within the same push. What happened: the `deploy` job's own
  logs in Actions, or on the VM, `journalctl -u sshd -n 50` plus
  `cat /srv/wca-records-analyser/.env` for the digest now pinned.
- **Build logs:** `journalctl -u wca-data-build.service -n 50`. Most nights say
  `wca_data build: unchanged` when WCA hasn't published since the last build.
- **Admin digest logs:** `journalctl -u wca-admin-digest.service -n 20`, or read
  `/srv/wca-admin/usage.log` directly — the same lines `/admin` groups by competitor.
- **Build now:** `sudo systemctl start wca-data-build.service`. A second build while one is
  running refuses to start.
- **Deploy now, without waiting for a push:** `~/apps/wca-records-analyser/deploy-launcher.sh`
  — the same thing the deploy key triggers.
- **When a PR changes `deploy/`:** nothing manual, with one exception. `run_deploy.sh`
  re-installs every file under `/srv/wca-records-analyser` (leaving `.env` and `bad-images`
  alone) on every deploy, so units, `compose.yaml` and the Caddy reference copy are always
  current on the next push. Only an actual systemd unit change needs a manual
  `sudo systemctl daemon-reload` afterwards (units already running aren't restarted by a file
  change alone), and only a real Caddy change needs copying into the scramble repo and
  reloading there (step 8). **The exception:** `deploy-launcher.sh` itself lives outside the
  checkout, at `~/apps/wca-records-analyser/deploy-launcher.sh`, by design (a `git reset
  --hard` must never rewrite the script currently running it) — so a change to that file is
  never picked up automatically. Repeat its install step by hand: `cp
  ~/apps/wca-records-analyser/repo/deploy/deploy-launcher.sh
  ~/apps/wca-records-analyser/ && chmod +x ~/apps/wca-records-analyser/deploy-launcher.sh`.

## When a release bumps the database schema

The container's health check is `/healthz`, which doesn't read the database, so an image
with a new `SCHEMA_VERSION` deploys even though the live database has the old one. Until the
database is rebuilt, pages that read it fail (`WcaData.open` refuses a schema mismatch).
`pull_deploy.py` starts `wca-data-build.service` itself right after every deploy, so this
rebuild is automatic; watch it with `journalctl -u wca-data-build.service -n 20` if you want to
confirm it ran.

The build rebuilds the same export for the new schema (it treats a database of another schema
version as out of date).

## When the build fails on the sentinel competitor

Every build checks that Feliks Zemdegs' (`2009ZEMD01`) latest 3x3 result in the live database
is still in the new one, unchanged. If WCA corrects that result, every nightly build fails
with:

```
wca_data build failed: SanityCheckFailed: 2009ZEMD01's latest result (...) is missing or changed in the new build
```

The site keeps serving the previous database, and the healthchecks.io check alerts after its
grace period.

1. Look at the result on <https://www.worldcubeassociation.org/persons/2009ZEMD01> (3x3
   Cube). If WCA really did change or remove it, force one build that accepts the change:

   ```sh
   cd /srv/wca-records-analyser
   sudo docker compose run --rm -e WCA_DATA_ACCEPT_SENTINEL_CHANGE=1 build
   ```

   It says it is accepting a change to the sentinel result. Every other check still runs:
   row counts within bounds, the sentinel present with 3x3 results. The next nightly build
   compares against the corrected result, so nothing else needs undoing.

2. If the WCA site still shows the result the live database has, don't force it: the export
   is wrong or the build is. Leave the old database serving and look into it.

## Rolling back

- **A bad app image** that fails its health check is rolled back automatically, and its
  digest goes in `/srv/wca-records-analyser/bad-images` so it isn't tried again. The fix is a
  new merge to `main`. An image that passes the health check but is wrong: revert on `main`
  (preferred), or by hand, with the previous digest from `.env.bak`-style history or the
  `deploy` job's own past runs in Actions:

  ```sh
  cd /srv/wca-records-analyser
  echo "<bad digest>" | tee -a bad-images
  $EDITOR .env          # WCA_IMAGE=<previous digest>
  docker compose up -d --wait web
  ```

- **A good image recorded as bad.** Any failed start counts, including host-side causes: a
  missing network, a Docker hiccup, a start slower than two minutes. Once the host is fixed,
  delete the digest's line from `/srv/wca-records-analyser/bad-images`; the next timer run
  deploys it.

- **A bad database** that passed the sanity checks: the one before is `wca.sqlite.prev`.
  Stop the timer first, or the next build rebuilds from the same export:

  ```sh
  sudo systemctl stop wca-data-build.timer
  cd /srv/wca-data
  sudo cp -p wca.sqlite.prev wca.sqlite.rollback && sudo mv wca.sqlite.rollback wca.sqlite
  ```

  The app opens the database per request, so it picks up the swap without a restart. Start
  the timer again once the cause is fixed.

## Maintenance

These are VM-wide and shared with the scramble app, so check what is already set before
changing anything.

| Area | Check |
|---|---|
| OS patches | `unattended-upgrades` on, with `Unattended-Upgrade::Automatic-Reboot "true"` and a quiet reboot time (e.g. Sunday 04:00) in `/etc/apt/apt.conf.d/50unattended-upgrades` |
| Logs | Containers rotate their own (`compose.yaml`: 3 × 10 MB). Cap the journal with `SystemMaxUse=500M` in `/etc/systemd/journald.conf.d/size.conf` |
| Disk | `df -h /` stays well clear of the 2 GB a build needs; the build deletes its download |
| Missed builds | healthchecks.io (step 5) |
| Uptime | the external check (step 9) |
| Backups | None needed: the database is rebuilt from the export, the config is in git |
| Quarterly | OCI cost against the budget alert; both alerts still fire (pause the build timer for a day to see) |
| Yearly | Move the VM to the next Ubuntu LTS when due |
