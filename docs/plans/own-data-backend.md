# Project plan: our own WCA data backend on OCI

Status: **planned — not started.** Written 2026-09-26. Supersedes the open questions in
[`docs/shared-backend-tradeoffs.md`](../shared-backend-tradeoffs.md), which remains the
background reading (measurements, licence text, export format).

## Why

On 24 September 2026 WCA's bot protection started returning 403 to non-browser clients on the
per-person API routes this app depends on. The app has shown a holding page since. WCA's
sanctioned route for bulk consumers is the **daily results export** (S3, not behind the bot
protection). We will build our own database from it and serve the app from our own server.

The earlier blocker — paying for an always-on host with enough disk and RAM — is gone: an
Oracle Cloud (OCI) Always Free Ampere A1 VM on a Pay As You Go account (budget alert already
set) covers it.

## Decisions taken

| Topic | Decision |
|---|---|
| Data source | WCA daily results export, rebuilt only when `export_date` changes |
| Storage | Trimmed SQLite database with FTS5 name search |
| Hosting | One OCI A1 VM runs the web app and the build job. Render is retired at cutover |
| Public API | None. The web app queries SQLite in-process |
| Reuse | The data layer is built so **another app can use it** without touching this one (see below) |
| Repo | Same repo as the web app, with the data layer as its own package |
| CI/CD | GitHub-hosted runners only. CI publishes an image to GHCR; the VM pulls it. **No self-hosted runners, ever** |
| Repo visibility | The repo is to become public |
| Dropped | Competitor avatars (not in the export); the mobile app (wca-analyser-mobile) |
| Freshness | Up to a day behind WCA is acceptable |

## Architecture

```
WCA export (S3) ──daily──▶ build job (VM, systemd timer)
                                │ writes temp file, atomic rename
                                ▼
                     /srv/wca-data/wca.sqlite   (read-only to consumers)
                                │
              ┌─────────────────┴──────────────────┐
              ▼                                    ▼
     wca-records-analyser web app          future app(s)
     (container, behind Caddy/HTTPS)       (same file, read-only)

GitHub Actions (hosted) ──tests, build image──▶ GHCR ◀──polls── VM deploy timer
```

## The data layer, designed for reuse

A different app may well want this data. Nothing here should make that harder than it needs to
be, so the data layer is a **separate package with a one-way dependency**, not a part of the web
app.

- **Own package:** `wca_data/` at the repo root, alongside `wca_records_analyser/`. It holds:
  - the **builder** (download export → build database), run as `python -m wca_data.build`;
  - a small **read library** (connect read-only, search persons, a person's results, a person's
    competitions, export metadata) returning plain dataclasses.
- **One-way dependency:** `wca_records_analyser` imports `wca_data`; `wca_data` never imports
  `wca_records_analyser`, FastAPI, Jinja or anything web. Enforce with a test that imports the
  package in isolation and checks it pulls in no app modules.
- **Domain-neutral contents:** the database holds WCA data as WCA defines it (persons,
  competitions, results, attempts). App-specific analysis — PRs, chart shapes, maps — stays in
  the app (`records.py`, `chart.py`, `map.py`). Don't pre-compute app-specific tables into the
  shared database; if an app needs a derived table, it builds it itself or it is added as a
  clearly general-purpose table.
- **The database file is the interface.** Other apps may use the read library or query the
  SQLite file directly in any language. So:
  - document the schema in `wca_data/SCHEMA.md`;
  - store a `meta` table: `schema_version`, `export_date`, `export_version`, `built_at`;
  - bump `schema_version` on any breaking change; readers check it on connect and fail clearly
    on a mismatch.
- **Configured location:** consumers find the database via an environment variable
  (`WCA_DATA_DB_PATH`), defaulting to `/srv/wca-data/wca.sqlite` on the VM. No path is baked
  into app code.
- **Safe for multiple readers:** consumers open read-only (`file:...?mode=ro` URI). The builder
  writes a new file and renames it into place, so readers never see a half-built database.
  Readers open a connection per request (cheap in SQLite) so they pick up the new file after a
  swap without a restart.
- **Independent of the web app's image:** the builder runs from the same image for simplicity,
  but has its own entry point and its own tests, and nothing in it assumes the web app is
  running.
- **Easy to split out later:** if a second app materialises, moving `wca_data/` (plus its tests
  and `SCHEMA.md`) to its own repo should be a directory move and a packaging change, nothing
  more. Options at that point: install it as a package from git, or have the other app only
  read the file.

### Database contents (first version)

Based on what the web app uses today; see the measurements in the tradeoffs doc (≈642 MB
on disk).

| Table | Columns | Notes |
|---|---|---|
| `persons` | `wca_id`, `name`, `country_id` | `sub_id = 1` rows only |
| `persons_fts` | FTS5 over `name`, `wca_id` | name search |
| `competitions` | `id`, `name`, `start_date`, `city`, `country_id`, `latitude`, `longitude` | lat/long for the map |
| `results` | `id`, `person_id`, `competition_id`, `event_id`, `round_type_id`, `best`, `average`, `attempts` | attempts packed into one column; index on `(person_id, event_id)` |
| `events` | `id`, `name`, `rank` | from the export, rather than a hand-kept table |
| `meta` | key/value | see above |

Keep columns general (e.g. `round_type_id`, `country_id`) even where this app doesn't use them
yet — they cost little and are the first thing another app would ask for.

### Build job

1. Fetch `https://www.worldcubeassociation.org/api/v0/export/public`. Stop quietly if
   `export_date` matches the current database's `meta`.
2. Stop loudly if the major part of `export_version` is not the one we support (currently v2).
3. Download the TSV zip (≈378 MB), build into a temp file, stream `result_attempts` in
   `result_id` order (don't hold 32M rows in memory, even though the VM could).
4. Sanity checks before swapping: row counts within expected bounds of the previous build, a
   known competitor's latest result present.
5. Atomic rename into place; keep the previous file as `wca.sqlite.prev` for rollback.
6. Delete the download and extracted files; ping the missed-build monitor.

Test-first against a tiny hand-made export zip in the test suite — no network in tests.

## Changes to the web app

- Replace the HTTP functions in `wca_client.py` with calls to the `wca_data` read library,
  keeping the same function signatures and dataclasses so `web.py` barely changes. Remove
  httpx/truststore if nothing else needs them.
- Remove avatars from `Person`, templates and tests.
- Add the WCA licence notice with the export date to the page footer:
  “This information is based on competition results owned and maintained by the World Cube
  Association, published at https://worldcubeassociation.org/results as of {export date}.”
- The existing TTL cache may become unnecessary; measure before removing.
- Turn `HOLDING_PAGE_ENABLED` off at cutover.

## Hosting (OCI)

- **VM:** Ampere A1, 2 OCPU / 12 GB is enough (smaller than the free maximum, which also makes
  it easier to get capacity). Ubuntu LTS (ARM64). Boot volume well within the 200 GB free
  total.
- **If "out of host capacity":** try each availability domain, retry later.
- **Runtime:** Docker for the app and the builder (same image, different command). Caddy in
  front for HTTPS with automatic certificates.
- **Network:** OCI security list opens only 80 and 443 publicly. SSH limited to your IP or
  via OCI Bastion.
- **Data directory:** `/srv/wca-data/`, owned by the builder, read-only mount into app
  containers.
- **Image:** ARM64 (or multi-arch, so it still runs on x86 locally).

## CI/CD and keeping the repo public-safe

The scramble challenge app's self-hosted runner is what stops that repo going public. This
project must not repeat that.

- **GitHub Actions runs only on GitHub-hosted runners.** It tests, builds the image and
  publishes it to GHCR (public image) using only the automatic `GITHUB_TOKEN`. It holds no
  server credentials and never connects to the VM.
- **The VM pulls.** A systemd timer checks GHCR every few minutes for a new `main` image;
  if found it pulls, restarts, checks `/` responds, and rolls back to the previous image if not.
- **Repo rules** (add to `CLAUDE.md` when the project starts):
  - no self-hosted runners;
  - no `pull_request_target` workflows;
  - no secrets in the repo; the only token Actions uses is `GITHUB_TOKEN`;
  - the data build runs on the VM, not in Actions;
  - server config is committed as templates; IPs, OCIDs and SSH details stay in a gitignored
    file on the VM.
- **Repo settings:** require approval before Actions runs on pull requests from forks.
- **Before making the repo public:** scan the full git history for secrets (e.g. gitleaks);
  remove the Render deploy job, its `RENDER_DEPLOY_HOOK_URL` secret and `render.yaml`.

## Maintenance plan (to become a runbook in phase 4)

| Area | Approach |
|---|---|
| OS security patches | `unattended-upgrades`, automatic reboot in a quiet window (e.g. Sunday 04:00) |
| App updates | Automatic via the pull deploy; rollback to the previous image on failed health check |
| Data build failures | Old database keeps serving; missed-build alert (e.g. healthchecks.io ping) |
| Uptime | Free external check on `/` |
| Disk | Delete export downloads after each build; disk-usage alert |
| Logs | Docker log rotation; journald size cap |
| Backups | None needed — the database is rebuildable, config is in git |
| Cost | Budget alert (set) |
| Quarterly | Review cost, patch status, alerts still firing correctly |
| Yearly | Move to the next Ubuntu LTS when due |

## Build order

Each phase leaves `main` green and deployable.

1. **`wca_data` builder** — package skeleton, isolation test, test export fixture, builder,
   `meta` table, `SCHEMA.md`. Done when a real export builds locally and the Feliks Zemdegs
   check from the tradeoffs doc matches.
2. **`wca_data` read library** — read-only connect, schema-version check, search, results,
   competitions, metadata.
3. **Web app on the new data layer** — swap `wca_client.py` over, drop avatars, add licence
   footer. Still behind the holding page on Render.
4. **Server and deployment** — ARM64 image to GHCR, VM setup, Caddy, build timer, pull-deploy
   timer, monitoring, runbook. Remove the Render deploy job.
5. **Cutover** — holding page off, DNS to the VM, retire Render.
6. **Go public** — history scan, repo settings, flip visibility.

## Open questions

1. OCI region and availability domain.
2. Domain name for the app (and whether it's already pointing at Render).
3. Plain Docker, or Docker Compose for the app + Caddy + timers?
4. Keep Render running (holding page) until cutover, or switch it off earlier?
5. If another app arrives: does it live on the same VM (reads the file directly) or elsewhere
   (then the database needs publishing, e.g. to OCI Object Storage)?
6. Should the builder also keep historic exports (e.g. one a month) for a future app that wants
   history, or is "latest only" enough? Latest only unless a need appears.

## Risks

| Risk | Mitigation |
|---|---|
| WCA changes the export format | Major-version check fails the build loudly; old database keeps serving |
| WCA restricts the export too | Unlikely (it is their sanctioned bulk route); would need a new plan |
| No A1 capacity in the region | Smaller shape, other availability domains, retry |
| Single VM goes down | Uptime alert; everything is rebuildable from git + export |
| Charges beyond Always Free | Budget alert; keep to the free shapes and volumes |
| Data layer grows app-specific and becomes hard to share | Package isolation test; review rule: no app logic in `wca_data` |
