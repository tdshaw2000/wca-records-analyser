# WCA data: database schema

Schema version: **2**

The database is a single SQLite file built nightly from the
[WCA results export](https://www.worldcubeassociation.org/export/results) (format v2) by
`python -m wca_data.build`. Any app may read it, through the `wca_data` package or directly
with SQLite in any language. This file is the interface: `tests/wca_data/test_schema_doc.py`
fails if it drifts from what the builder creates.

## Reading it safely

- **Location:** the path is in the environment variable `WCA_DATA_DB_PATH`
  (on the server, `/srv/wca-data/wca.sqlite`). Don't hard-code it.
- **Read-only:** open with a URI such as `file:/srv/wca-data/wca.sqlite?mode=ro`. Never write.
- **Per request:** each build writes a new file and renames it over the old one, so open a
  connection per request (or per short job) to see the latest build. A connection that is
  already open keeps reading the file it opened.
- **Check the version:** read `meta.schema_version` on connect and stop with a clear error if
  it isn't the version your code was written for. It goes up on any breaking change.
- **Licence:** WCA requires apps showing this data to say: "This information is based on
  competition results owned and maintained by the World Cube Association, published at
  https://worldcubeassociation.org/results as of {export date}." The export date is
  `meta.export_date`.

Values are kept as WCA defines them. Times are centiseconds; `-1` is DNF, `-2` is DNS and `0`
is no result. Fewest moves is a move count (averages ×100) and multi-blind is WCA's packed
encoding. See the WCA export's README for the details.

## Tables

### `meta`

One row per key.

| Column | Type | Meaning |
|---|---|---|
| `key` | TEXT, primary key | `schema_version`, `export_date`, `export_version` or `built_at` |
| `value` | TEXT | The value: the schema version as a number; `export_date` and `built_at` as UTC `YYYY-MM-DDTHH:MM:SSZ`; `export_version` as WCA gives it, e.g. `v2.0.2` |

### `persons`

Every competitor, with their current name and country only (the export's `sub_id = 1` rows).

| Column | Type | Meaning |
|---|---|---|
| `wca_id` | TEXT, primary key | WCA ID, e.g. `2009ZEMD01` |
| `name` | TEXT | Name as WCA shows it, UTF-8, e.g. `Xiaoming Wang (王小明)` |
| `country_id` | TEXT | WCA country id, e.g. `Australia` |

### `persons_fts`

An FTS5 full-text index over `persons`, for name and WCA ID search. Its rowid is the
`persons` rowid: `SELECT p.* FROM persons_fts f JOIN persons p ON p.rowid = f.rowid WHERE
persons_fts MATCH ?`. The tokenizer is `unicode61 remove_diacritics 2`, so `zoe` finds
`Zoé`. Escape user input before using it as a MATCH query (quote each term), or FTS5 reads it
as query syntax.

| Column | Type | Meaning |
|---|---|---|
| `name` | text | `persons.name` |
| `wca_id` | text | `persons.wca_id` |

### `persons_cjk`

A second FTS5 index, for Chinese, Japanese and Korean names. Those scripts put no spaces
between words, so `persons_fts` sees `王小明` as one word and can't find `小明`. This table holds
each name's CJK characters (Han ideographs with marks such as 々 and 〇, kana and Hangul) in
order, one space between each: `王 小 明`. Search it with the characters you want, spaced the same
way, as a quoted phrase: `WHERE persons_cjk MATCH '"小 明"'` finds names with `小明` anywhere in
them. If a name has more than one CJK run, they are joined, so a phrase can span them.
`wca_data.schema.CJK_CHARACTER` lists the exact characters.

Only names with CJK characters have a row. It is contentless: read `rowid` and join to
`persons` on `rowid`, as for `persons_fts`.

| Column | Type | Meaning |
|---|---|---|
| `characters` | text | The name's CJK characters, one space between each |

### `competitions`

Competitions WCA publishes (the export leaves out ones it hides).

| Column | Type | Meaning |
|---|---|---|
| `id` | TEXT, primary key | Competition id, e.g. `AustralianNationals2026` |
| `name` | TEXT | Name |
| `start_date` | TEXT | First day, `YYYY-MM-DD` |
| `city` | TEXT | City as WCA gives it |
| `country_id` | TEXT | WCA country id |
| `latitude` | REAL, nullable | Degrees, from WCA's microdegrees; NULL if WCA has none |
| `longitude` | REAL, nullable | Degrees, from WCA's microdegrees; NULL if WCA has none |

### `events`

| Column | Type | Meaning |
|---|---|---|
| `id` | TEXT, primary key | Event id, e.g. `333`, `333bf` |
| `name` | TEXT | Name, e.g. `3x3x3 Cube` |
| `rank` | INTEGER | WCA's display order (ascending) |

### `round_types`

WCA's round types. Order a competitor's rounds within a competition by `rank`.

| Column | Type | Meaning |
|---|---|---|
| `id` | TEXT, primary key | Round type id, as in `results.round_type_id` |
| `name` | TEXT | Name, e.g. `First round`, `Final` |
| `rank` | INTEGER | WCA's round order (ascending): qualification, then first round, and so on to the final |
| `final` | INTEGER | `1` for a final round type, else `0` |

### `results`

One row per competitor per round. Indexed on `(person_id, event_id)`.

| Column | Type | Meaning |
|---|---|---|
| `id` | INTEGER, primary key | WCA result id |
| `person_id` | TEXT | `persons.wca_id` |
| `competition_id` | TEXT | `competitions.id` |
| `event_id` | TEXT | `events.id` |
| `round_type_id` | TEXT | `round_types.id`, e.g. `1`, `2`, `f` (final), `c` (combined final) |
| `best` | INTEGER | Best single |
| `average` | INTEGER | Average or mean, `0` if the round has none |
| `attempts` | TEXT | Every attempt, comma-separated in attempt order, e.g. `623,593,705,693,629`. A missing attempt number is `0`; empty if WCA lists no attempts |

## Changes

| Version | Change |
|---|---|
| 1 | First version |
| 2 | Adds `round_types` and `persons_cjk` |
