# Three-source FMCSA preprocessing

## Acquisition and schema checks

Use the [official sources in README](../README.md#setup-and-data). Portal CSV
exports are suitable; input must be uncompressed UTF-8, with optional BOM.
Record extract date, filters, and whether acquisition was complete. Do not use
administrative upload/change dates as event dates. Keep files immutable during
processing. Outputs record actual file SHA-256 and bytes, selected/unavailable
columns, versions, period and chunk size, but cannot establish extract completeness.

The metadata endpoints `/api/views/{id}.json` supply `columns[].fieldName`,
`dataTypeName` and `metadata.attachments`; construct dictionary URLs using
`/api/views/{id}/files/{assetId}?download=true`. The reviewed dictionaries are
Company Census Rev08 (2026-01-23), Crash Rev05 (2025-11-04) and Inspection Rev05
(2025-10-15). Their copies provided by the user matched the live attachments.

Small API samples can be acquired using these resource URLs and query parameters:

| Resource | Parameters for parser smoke samples |
| --- | --- |
| https://data.transportation.gov/resource/aayw-vxb3.csv | `$where=report_date >= '20160101' AND report_date < '20260101'`, `$order=crash_id`, `$limit=100` |
| https://data.transportation.gov/resource/fx4q-ay7w.csv | `$where=insp_date >= '20160101' AND insp_date < '20260101'`, `$order=inspection_id`, `$limit=100` |
| https://data.transportation.gov/resource/az4n-8mr2.csv | `$where=dot_number in (...)`, `$order=dot_number`, `$limit=1000` |

URL-encode parameters, especially spaces, quotes and `$`. In PowerShell single
quotes protect `$` from expansion. The final census sample used the union of
positive DOT identifiers from both event samples. Exact requests/checksums are
in [the sample receipt](official_sample_validation.json). Ordered samples are
nonrepresentative; targeted census matching makes sample linkage coverage
artificially high. Live endpoints may revise records, so new hashes can differ.
Michael's downloader remains on his branch; this contribution adds no competing
bulk downloader. A full export needs complete portal export or validated API
pagination, not just increasing `$limit` and assuming the server honored it.

Required headers after trim/uppercase:

- Census: `DOT_NUMBER`, `PHY_STATE`.
- Crash: `CRASH_ID`, `DOT_NUMBER`, `REPORT_DATE`.
- Inspection: `INSPECTION_ID`, `DOT_NUMBER`, `INSP_DATE`.

Optional columns are listed in `SPECS` in `analysis/build_safety_dataset.py` and
the source-verified variable reference in PR #6. Absent fields are listed in
metadata and exported as null; an absent country remains unknown. Wrong dataset,
LFS pointer, duplicate header, malformed row or invalid encoding fails the run.
A header-only extract is allowed and reported as empty; a zero-byte file fails.

## Run and inspect

Install `requirements.txt`; install `requirements-parquet.txt` for Parquet. From
the repository root:

```sh
python -m analysis.build_safety_dataset --census "data/Company_Census_File.csv" --crashes "data/Crash_File.csv" --inspections "data/Vehicle_Inspection_File.csv" --output-dir "outputs/safety_run_01" --chunk-size 100000 --parquet
python -m unittest discover -s tests -v
```

Exit code 0 confirms publication. Known input/processing errors return 2 and do
not publish a partial run. Existing output directories are never overwritten.
Temporary SQLite files are staged beside the destination and cleaned on handled
failure. A process/OS crash can leave temporary directories; inspect before
manually removing them. Allow disk for retained selected event rows, indexes,
sorts and output copies. There is a full sequential CSV validation/hash pass
before selected-column pandas ingestion. SQLite insertion is transactional per
chunk, with an 8 MiB cache target and disk temporary storage; this is not a hard
process-memory limit or a measured full-export performance guarantee.

In notebooks, call the same implementation:

```python
from analysis.build_safety_dataset import build_pipeline
path = build_pipeline("data/census.csv", "data/crashes.csv", "data/inspections.csv",
                      "outputs/notebook_run", chunk_size=100_000, parquet=True)
```

No-argument `build_pipeline()` preserves Ayaan's full-then-sample filename lookup
under `data/`; explicit paths are recommended. Importing the module creates no
output directory. The former full-frame `process_census/process_crashes/
process_inspections` helpers are replaced by the streaming ingestion/aggregation
path; there were no repository callers. `canonicalize_dot` and `get_filepath`
remain available. Default output is now a protected new `outputs/safety_run/`
directory; no silent overwrite of the former pooled carrier file occurs.

## Analytical outputs

Five CSV files are always written; `--parquet` adds equivalent `.parquet` files
with nullable int64 measurements/counts and string identifiers/geography.
Empty outputs retain their headers/schema. CSV empty cells represent null and
must not be automatically filled with zero. Read DOT_NUMBER as string.

| File stem | Grain and meaning |
| --- | --- |
| carriers | First valid census occurrence per canonical DOT; includes carriers without safety records, optional attributes and LOCATION_GROUP |
| crash_carrier_year | One DOT/year per observed crash source, TOTAL_CRASHES and reported FATALITIES/INJURIES sums with `_observed` counts |
| inspection_carrier_year | One DOT/year per observed inspection source, TOTAL_INSPECTIONS, violation/OOS sums with `_observed` counts |
| carrier_safety_2016_2025 | Union of event DOT/year keys, joined one-to-one to source aggregates and many-to-one to census; census_matched=0 preserves event-only keys |
| monthly_activity | source/year/month/event_state/REPORT_STATE counts, including valid dated records without usable DOT |

`TOTAL_FATALITIES`, `TOTAL_INJURIES`, `TOTAL_VIOLATIONS`, `TOTAL_OOS`,
`TOTAL_VEHICLE_OOS` and `TOTAL_DRIVER_OOS` sum only observed numeric values.
All-missing sums remain null. `_observed` is the number of retained source records
with a valid measurement, not miles, vehicles or drivers exposed. For example,
an OOS sum of 0 with `_observed=5` differs from null with `_observed=0`.
Missing source counts for an existing DOT/year key become 0, but measurement
sums remain null. Census TOTAL_DRIVERS is not an event metric and is never
zero-filled. Crash sums can repeat accident casualties across vehicle records.

Census-only carriers remain in `carriers`, without ten fabricated historical
carrier/year rows. Use that table for population/fleet distributions. Carrier/year
outputs support observed-event comparisons, not a balanced historical panel.
For crash monthly rows `event_state` is STATE; inspection uses REPORT_STATE,
which is the uploading jurisdiction, usually where inspection occurred. No
event country is inferred and no event geography comes from carrier domicile.

## Quality reports and review gates

- `quality.json`: input/retained/excluded/duplicate/conflicting-duplicate counts,
  raw selected-field missing/invalid/zero counts and missing fractions, source
  availability, parsed and retained date ranges, all unobserved months, retained
  geography and processing-status/inspection-level distributions. Missing
  fractions have null denominator for empty inputs; unavailable optional fields
  are listed separately, not assigned misleading missingness percentages.
- `integration_validation.json`: census carriers with/without events, unioned
  carrier/year keys, matched/unmatched event records/distinct carriers, monthly
  counts, observed measurement sums/counts and `checks_passed`.
- `run_metadata.json`: source filenames/bytes/SHA-256/schema, versions, interval,
  output grain and chunk size. No local absolute source paths are published.

Raw rows partition into mutually exclusive exclusions (invalid/missing primary
ID, unusable date, outside period, inspection duplicate status), duplicate IDs
and retained rows, in that priority order. DOT issues do not exclude otherwise
valid event records from monthly summaries. First eligible source ID wins,
including a first record without DOT; later differing cleaned payloads are
conflicts. This is deterministic across chunks, not across input reorderings.
Conflicts need review before scientific use. Unrecognized category codes remain
visible and flagged. SQL integer overflow aborts rather than publishing rounded
sums. The original census report supports larger Python-integer totals; this
integration uses signed int64/SQLite sums for practical count fields.

Before Week 5 analysis, inspect exclusions, unknown geographies, conflicting
IDs, all 120 month cells, status mix, observed measurement denominators and
unmatched records. `checks_passed` certifies arithmetic reconciliation only.
It does not certify complete reporting, scientifically appropriate duplicate
policy, valid registration, absence of selection bias or comparable exposure.

## Review dependencies

Research documentation is PR #6 against main. Preprocessing PR #7 extends
Ayaan's existing branch, quality PR #8 builds on #7, and reproducibility docs
build on #8. Review/merge the teammate dependency first, then retarget stacked
PRs as appropriate; merge #6 for the full research documentation set. No main
branch commits, force pushes or automatic PR merges are part of this work.
