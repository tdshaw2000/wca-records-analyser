# Project plan: our own WCA data backend on OCI

Status: **phases 1 through 3 done** (2026-09-28). Written 2026-09-26; updated 2026-09-27 with the
hosting, caching and working-practice decisions. Supersedes the open questions in
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
| Hosting | The **existing** scramble challenge OCI A1 VM also runs this web app and the build job. Render is retired at cutover |
| Front door | The scramble stack's Caddy (already on 80/443) routes by hostname; this app gets one more site entry |
| Domain | `wca-records-analyser.duckdns.org`, same IP as the scramble app (created 2026-09-27) |
| Runtime | Docker Compose, matching the scramble stack |
| Public API | None. The web app queries SQLite in-process |
| Reuse | The data layer is built so **another app can use it** without touching this one (see below) |
| Repo | Same repo as the web app, with the data layer as its own package |
| CI/CD | GitHub-hosted runners only. CI publishes an image to GHCR; the VM pulls it. **No self-hosted runners, ever** |
| Repo visibility | The repo is to become public |
| Dropped | Competitor avatars (not in the export); the mobile app (wca-analyser-mobile) |
| Freshness | Up to a day behind WCA is acceptable |
| PR caching | None up front. Measure the overview on SQLite in phase 3; precompute only if it is slow (see below) |
| Working practice | Strict TDD for every change, through the review loop in `CLAUDE.md` |

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
     (container, behind the shared Caddy)  (same file, read-only)

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
- **Measure before caching PRs.** The old overview was slow because it made one WCA API call
  per event plus profile and competition calls, not because of the PR maths (one pass over a
  few hundred values). On SQLite it becomes one indexed query. Time the overview for a heavy
  competitor (Feliks Zemdegs, `2009ZEMD01`). Only if that is noticeable, precompute every
  competitor's PR progressions during the nightly build into an **app-owned** file, never the
  shared `wca_data` database; each build replaces it whole, so it never goes stale. Caching
  on demand, or pre-warming for recent visitors, is ruled out: it needs visit logging and
  still leaves first visits slow.
- Turn `HOLDING_PAGE_ENABLED` off at cutover.

## Hosting (OCI)

This app shares the VM the scramble challenge app already runs on, instead of a new VM.

- **VM:** the existing `scramble-challenge` instance: Ampere A1, 2 OCPU, ≈11 GB RAM, 45 GB boot
  volume with ≈40 GB free (checked 2026-09-27). That is enough for both apps plus a build
  (a few GB of RAM and ≈1.5 GB of scratch disk while it runs).
- **Front door:** the scramble stack's `caddy:2` container owns 80 and 443 and gets certificates
  automatically. This app runs no Caddy of its own. Phase 4 adds a site entry for
  `wca-records-analyser.duckdns.org` to the scramble stack's Caddyfile, which lives in the
  scramble repo, and joins this app's container to that stack's Docker network so Caddy
  reaches it by container name. The app publishes no port on the host.
- **Later:** if a third app arrives, move Caddy into its own small stack (e.g. `/srv/edge`)
  that every app joins. Not now: it means a short scramble outage for no gain yet.
- **Runtime:** Docker Compose for the app and the builder (same image, different command), in
  its own Compose project next to the scramble one.
- **Network:** unchanged. The OCI security list already opens only 80 and 443 publicly.
- **Data directory:** `/srv/wca-data/`, owned by the builder, read-only mount into app
  containers.
- **Sharing politely:** the build runs at low CPU and IO priority and outside busy hours, and
  containers get memory limits, so a build can't starve the scramble app.
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

Each phase leaves `main` green and deployable. Every phase is strict TDD: each change in
behaviour is a red commit (failing tests) then a green commit, reviewed as `CLAUDE.md` describes.

1. **`wca_data` builder** — package skeleton, isolation test, test export fixture, builder,
   `meta` table, `SCHEMA.md`. Done when a real export builds locally and the Feliks Zemdegs
   check from the tradeoffs doc matches.
2. **`wca_data` read library** — read-only connect, schema-version check, search, results,
   competitions, metadata. Done: `wca_data/read.py`. Schema version 2 adds `round_types` (to
   order rounds within a competition) and `persons_cjk`, a per-character index so any part of
   a Chinese, Japanese or Korean name can be searched (a trigram index can't match the one- and
   two-character queries those names need).
3. **Web app on the new data layer** — swap `wca_client.py` over, drop avatars, add licence
   footer, time the overview (see "Measure before caching PRs"). Still behind the holding
   page on Render. Done: `wca_client.py` reads `wca_data.read.WcaData`; an unknown WCA ID is
   a 404; httpx/truststore dropped (moved to a dev-only test dependency). Timed the overview
   for Feliks Zemdegs (2009ZEMD01, 19 events) on the real export: ~76ms sequential. The
   per-event thread pool, built for the old API's round-trips, made this *slower* (~236ms) 
   against local SQLite reads with nothing to hide, so it's removed; the TTL cache stays, since
   it still helps repeat visits and warm search. No PR cache: both numbers are well under
   anything that would need one.
4. **Server and deployment** — ARM64 image to GHCR, Compose project and data directory on the
   shared VM, the Caddy site entry in the scramble stack, build timer, pull-deploy timer,
   monitoring, runbook. Remove the Render deploy job.
5. **Cutover** — holding page off, the DuckDNS name serving the app from the VM, retire Render.
6. **Go public** — history scan, repo settings, flip visibility.

## Open questions

Answered on 2026-09-27:

1. ~~OCI region and availability domain.~~ The existing scramble challenge VM.
2. ~~Domain name.~~ `wca-records-analyser.duckdns.org`.
3. ~~Plain Docker or Compose?~~ Compose, as the scramble stack does.
4. ~~Keep Render until cutover?~~ Yes, showing the holding page.

Still open, and fine to leave until a need appears:

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
| The two apps on one VM get in each other's way | Low-priority build, container memory limits; either app's deploy only touches its own Compose project |
| A broken Caddyfile change takes the scramble app down too | Validate with `caddy validate` before reloading; reload, don't restart |
| Charges beyond Always Free | Budget alert; keep to the free shapes and volumes |
| Data layer grows app-specific and becomes hard to share | Package isolation test; review rule: no app logic in `wca_data` |
