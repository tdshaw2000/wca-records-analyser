# Shared backend for web and mobile: hosted SQLite vs static JSON

Status: **decided 2026-09-26 — see [`plans/own-data-backend.md`](plans/own-data-backend.md).** Written 2026-09-23; kept as background (measurements, licence text, export format).

Covers both apps:

- **wca-records-analyser** (this repo) — Python/FastAPI web app on Render.
- **wca-analyser-mobile** — Expo/React Native Android app. Its immediate stop-gap plan is
  `docs/plans/wca-api-bot-protection.md` in that repo.

## Why this is on the table

WCA extended AWS Bot Protection to the per-person API routes sometime between late June and
September 2026. `GET /api/v0/persons/{wcaId}`, `/persons/{wcaId}/results` and
`/persons/{wcaId}/competitions` now return **403** from the AWS load balancer for any
non-browser client, regardless of `User-Agent` or network. Both apps depend on these routes and
are broken. WCA has confirmed bot protection on some routes is deliberate
([#11722](https://github.com/thewca/worldcubeassociation.org/issues/11722)); nothing was
announced for the API.

WCA's sanctioned route for bulk consumers is the **daily results export**, served from S3 and
not behind the bot protection. Owning a backend built from that export removes the dependency
on WCA's per-person API (and on the unofficial third-party mirror the mobile stop-gap uses).

## The common part: a daily build job

Whichever serving option is chosen, the pipeline is the same:

1. Poll `https://www.worldcubeassociation.org/api/v0/export/public`; compare `export_date` to
   the last build. Fail loudly if the major part of `export_version` changes (currently `v2.0.2`;
   v2 renamed tables and columns).
2. Download the TSV zip (`tsv_url`).
3. Build a trimmed SQLite database with only what the apps use.
4. Publish it (option A) or render files from it (option B).

### Measured on the 2026-09-23 export

| | Size / time |
|---|---|
| TSV zip download | **378 MB**, ~19 s |
| Full export unzipped | 1.6 GB (results 629 MB, result_attempts 442 MB, scrambles 400 MB unused) |
| Rows needed | persons 298,293 · competitions 18,730 · results 6,916,920 · result_attempts 31,882,708 |
| **Trimmed SQLite** (persons, competition start dates, results with attempts packed into a column, indexed by `(person_id, event_id)`) | **642 MB** on disk, **219 MB** zipped |
| Build time (naive Python, all attempts held in memory) | ~85 s |
| Query: all of Feliks Zemdegs' 3x3 results joined to dates, date-ordered | **3 ms**, 524 rows |

Tables needed: `persons` (`wca_id`, `name`; `sub_id = 1` rows only), `competitions` (`id`,
`year`/`month`/`day` → start date), `results` (`id`, `person_id`, `competition_id`,
`event_id`, `best`, `average`), `result_attempts` (`result_id`, `attempt_number`, `value`).

A production build should stream `result_attempts` in `result_id` order rather than holding
32M rows in a dict — the naive build needs several GB of RAM.

### Output checked against a known-good source

Feliks Zemdegs' latest 3x3 result from the local build — `AustralianNationals2026`,
`2026-07-09`, best 593, average 648, attempts `623,593,705,693,629` — matches both the WCA
site and the unofficial API.

## Option A — hosted SQLite behind an API

The web app (already a FastAPI server) holds the database and gains a small JSON API alongside
its HTML routes. The mobile app calls that API.

## Option B — static JSON files, no server

The build job also writes one JSON file per competitor and uploads them to object storage
behind a CDN. Both apps fetch files directly.

Measured on a random sample of 2,000 competitors:

| | Size |
|---|---|
| Per-competitor file | avg **2.0 KB** raw, **0.6 KB** gzipped |
| All 298k files | **~585 MB** raw, **~180 MB** gzipped, republished daily |

## Trade-offs

| | A. Hosted SQLite + API | B. Static JSON files |
|---|---|---|
| **What you operate** | An always-on process, disk, restarts, monitoring | Nothing live — a scheduled job and a storage bucket |
| **Cost** | Always-on instance + persistent disk. Free tiers typically sleep (30–60 s cold starts — bad for a phone app). Check current Render pricing | Pennies — object storage + CDN at this size |
| **Latency / availability** | One server's uptime and region; queries are fast | CDN edge-cached worldwide; fails only if the storage provider does |
| **Name search** | Trivial: SQL `LIKE` or SQLite FTS5 | Awkward: a pre-sharded search index (e.g. by name prefix), or keep using WCA's `/api/v0/persons?q=` which still works — for now |
| **New features** (compare competitors, rankings, who-was-at-this-competition) | Write a query, add an endpoint | Every access pattern must be pre-generated as more files, designed up front |
| **Daily update** | Atomic swap of one file (build to temp, `mv` into place) | Upload ~300k files — ideally only changed ones. GitHub Pages is a poor host (site-size limit, repo history bloat) |
| **Attack surface** | Public API: rate limiting and input validation needed | Read-only files; nothing to exploit; CDN absorbs load |
| **Mobile's "no backend we own" rule** | Breaks it — the phone depends on your server being up | Nearly keeps it — you own a pipeline, not a service |
| **Fit with the web app** | Natural — it becomes the API | The web app's server fetches JSON over the network — an extra hop |

## Ramifications common to both

- **Licence:** re-publishing is allowed if users are shown: “This information is based on
  competition results owned and maintained by the World Cube Association, published at
  https://worldcubeassociation.org/results as of {export date}.” Both apps need this notice.
- **Freshness:** up to a day behind WCA; results also depend on WCA's results team posting them.
- **Format versions:** check `export_version`'s major number on every build.
- **Download etiquette:** one 378 MB download a day, only when `export_date` has changed.
- **Where the job runs:** GitHub Actions (scheduled workflow) is the obvious candidate for both
  options; option A then needs a way to ship the built database to the server.

## A hybrid worth considering

Pick A now, but shape the API URLs like static files — e.g. `GET /v1/persons/2009ZEMD01.json`
returning the competitor's whole record, filtered client-side. Clients can't tell whether a
server or a CDN answered. Moving the mobile app to option B later is then: point the same build
job at a bucket and change one base URL. Search would stay on the server (or WCA).

## Open questions for the decision

1. Is paying for an always-on instance acceptable? (Decides A vs B more than anything else.)
2. Is search the only query beyond "one competitor's results", or are richer features planned?
3. Is relaxing the mobile app's "no backend we own" rule acceptable?
4. Which object storage/CDN, if B? (Cloudflare R2 has no egress fees; S3 + CloudFront is the
   AWS default.)
5. Does the web app's current Render plan have a persistent disk, and enough RAM to build
   (or should the build always happen in CI)?

## Reversibility

The build job is identical for both options; only the last step differs. Both apps already
isolate data access (`wca_client.py` here; `src/data/` repositories in mobile), so switching
source is confined to those layers. With the hybrid URL shape, moving between A and B is a
base-URL change for clients.
