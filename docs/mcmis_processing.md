# MCMIS Company Census processing

Run from the repository root with Python 3.10 or newer. pandas is the only
third-party dependency; tests use the standard library's unittest.

```sh
python -m pip install -r requirements.txt
python -m analysis.mcmis_chunked --input "data/Company_Census_File.csv" --output-dir "outputs/census_run_01" --chunk-size 100000
python -m unittest discover -s tests -v
```

The same commands work in PowerShell, macOS and Linux shells. Quote paths with
spaces. The output directory must not already exist: choose a new directory for
each run. Keep input files and generated reports out of commits. The module is
also callable from notebooks:

```python
from analysis.mcmis_chunked import process_csv
summary = process_csv("data/Company_Census_File.csv", "outputs/notebook_run", chunk_size=100_000)
```

## Verified schema and integration

The [official DOT Company Census dataset](https://data.transportation.gov/Trucking-and-Motorcoaches/Company-Census-File/az4n-8mr2/about_data)
and its [metadata API](https://data.transportation.gov/api/views/az4n-8mr2.json)
were inspected on October 9, 2026. Its attached dictionary is
`MCMIS Company Census Data Dictionary(Rev08)2026-01-23.pdf`; this implementation
verified names against the metadata and an actual 100-row API CSV, rather than
assuming that Harika's selected columns exist in every export.

| Column | Treatment |
| --- | --- |
| DOT_NUMBER | Required; canonical positive integer identifier |
| PHY_STATE | Required; physical state/province code |
| PHY_COUNTRY | Optional; separates US and foreign locations |
| TOTAL_DRIVERS | Optional; driver-count summaries |
| POWER_UNITS | Optional; numerical summaries and fleet-size bins |
| MCS150_MILEAGE | Optional; reported mileage summaries |
| MCS150_MILEAGE_YEAR | Optional; quality checks for mileage context |

Headers are normalized for case and surrounding whitespace, so both uppercase
bulk-export headers and lowercase Socrata headers work. Duplicate normalized
headers are rejected. The sample has 147 columns; only the verified columns
above are loaded into pandas. Missingness reports cover these analyzed columns,
not every field in the census.

Harika's `harika/mcmis-data-exploration` branch contains a preliminary 100-row
exploration script. Michael's `Michael_FMCSA_exploration` branch contains crash
downloading, notebooks and CSV LFS tracking. The saved loading error is from
Michael's crash-data notebook; this contribution addresses the same full-frame
loading pattern specifically for the Company Census schema. It does not replace
either teammate's work or implement another downloader.

At inspection, PR #3 was open and `.gitattributes` was absent from main. Its
`*.csv filter=lfs diff=lfs merge=lfs -text` rule is deliberately left to that PR.
This pipeline works independently of its merge. No raw CSV fixtures are committed;
tests create fixtures in temporary directories. Git LFS was already installed and
was initialized locally. A downloaded LFS pointer is not a census CSV: retrieve
the actual LFS object before processing.

## Processing and memory

There are two streaming passes. The first validates CSV quoting and field counts
and computes the exact file SHA-256. The second uses `pd.read_csv` with explicit
string dtypes, selected columns and configurable chunks (default 100,000).
Malformed records fail the run instead of silently disappearing through
`usecols`. Blank lines are ignored; quoted multiline fields are supported.
Input is an uncompressed UTF-8 CSV, with or without a BOM.

Incremental counters and integer totals avoid retaining previous chunks. A
standard-library SQLite index records canonical identifiers and first-row
positions, with an index on row position and an 8 MiB page-cache target.
Deduplication storage grows with distinct identifiers on disk, rather than as an
unbounded Python set in RAM. Temporary storage is placed beside the output
folder and is removed on normal success or handled failure. Leave sufficient disk
space; the SQLite cache target is not a hard bound on total process memory.
The parser and derived Series also use memory proportional to chunk size.

Reports are assembled in a temporary directory and published together by a
same-filesystem directory rename only after successful processing. Existing
output directories are never overwritten. The input's size and modification time
are checked before publication; keep the source immutable during a run. File
checksum, analyzed/absent columns, chunk size and Python/pandas versions are
recorded in the run metadata. CSV aggregate outputs are deterministic for the
same input regardless of chunk size; metadata intentionally records the chosen
chunk size and environment. No timestamps or local absolute paths are written.

## Counting and cleaning rules

- `processed_rows` counts input records. `unique_carriers` counts distinct valid
  DOT identifiers, not rows. Positive decimal identifiers are canonicalized:
  `001`, `1` and `1.0` identify the same carrier.
- The first valid identifier occurrence in input order supplies that carrier's
  location and numerical values. Later duplicate rows remain in row-level
  missingness and location counts, but do not inflate carrier statistics.
  Reordering conflicting duplicate records can change the retained values;
  this is not a latest-registration selection algorithm.
- Rows with missing or malformed identifiers contribute to raw quality and
  location counts but are excluded from unique-carrier metrics. Blank strings,
  whitespace, `NA`, `N/A`, `NULL` and `NaN` are missing in numeric fields
  (case insensitive). Location fields retain the two-letter `NA` code, including
  Namibia, and treat the other listed tokens as missing.
- Counts and mileage accept nonnegative decimal whole numbers, including `.0`
  suffixes. Zero is a valid reported value, never imputed. Negative, fractional,
  scientific-notation, comma-formatted, infinite and nonnumeric values are invalid.
  More than 15 significant integer digits are rejected to bound corrupt inputs
  and preserve exact conversion. This validates syntax, not FMCSA registration.
- Mileage years outside 1900-2100 are invalid, including year zero. The range is a
  plausibility check, not evidence that a report is current.
- State and country codes are trimmed and uppercased. Two-letter unknown codes
  remain in the output. Missing and malformed codes get separate `missing` and
  `invalid` buckets; malformed raw strings are not exported. Grouping by country
  and state keeps Canadian and US `CA` codes distinct. US states/DC, US territories,
  other US codes, non-US countries and unknown countries are labeled separately.
  If PHY_COUNTRY is unavailable or invalid, country is unknown, not inferred.

## Outputs

| File | Meaning |
| --- | --- |
| overview.csv | Total rows, distinct carriers, duplicate and unidentified rows |
| data_quality.csv | Raw-row missing/invalid counts, missing fraction, numeric zeros |
| state_counts.csv | Row counts and retained unique carriers by physical country/state |
| fleet_distribution.csv | Unique-carrier POWER_UNITS bins: 0, 1, 2-5, 6-20, 21-100, 101+, missing, invalid |
| numeric_summary.csv | Unique-carrier valid/missing/invalid/zero counts, exact sum, min, max and mean |
| run_metadata.json | Input checksum, byte size, filename, versions and schema availability |

Unavailable numerical fields have `available=False` and blank statistics, not
zero estimates. An available field with no valid values has blank sum/min/max/mean;
a genuine collection of valid zeros has a zero sum. State row counts sum to total
rows; state unique-carrier counts sum to distinct retained carriers. The fleet
bins sum to unique carriers when POWER_UNITS is available.

Fleet bins are explicitly derived from POWER_UNITS. The source's FLEETSIZE
category codes are not interpreted as unit counts. Mileage statistics pool valid
reported values across mileage years; they are descriptive values, not a common-
year exposure measure. Year missingness and validity help assess whether a
later year-aligned analysis is feasible. No crash rates, safety comparisons,
causal findings, exact medians or percentiles are inferred from these aggregates.
The census includes entities beyond active motor carriers; the script applies no
status/operation filter, so the universe is registered census identifiers.

## Executed validation

On October 9, 2026, Windows with Python 3.11.9 and pandas 3.0.5:

- `python -m unittest discover -s tests -v`: 14 tests passed. Tests check
  chunk-size independence (1, 2, 3 and 100), cross-chunk duplicates and totals,
  missing/invalid/zero values, state/country retention, absent optional columns,
  exact integer sums beyond int64, quoted multiline fields, malformed/empty CSVs, bad chunk sizes, output protection
  and CLI exit codes.
- Separate real-data smoke check used
  `https://data.transportation.gov/resource/az4n-8mr2.csv?$limit=100&$order=dot_number`
  with chunk size 17: 100 rows, 100 distinct identifiers, 0 duplicate rows and 0
  unidentified rows. The downloaded CSV was 46,715 bytes with 147 columns;
  SHA-256 `80c7eb1155a859bd3edf8dc882d91747304d9da86345b8098819c8ebb06c926d`.
  All six reports were generated outside the repository; the five CSV outputs
  were identical for chunk sizes 17 and 100. This API sample is
  ordered and nonrepresentative; it supports parsing validation, not US findings.

The full approximately 2 GB export was not downloaded or benchmarked. macOS and
Linux execution and other pandas versions have not been tested locally. Potential
follow-ups are CI across platforms, snapshot/year-aware duplicate reconciliation,
year-aligned mileage summaries and full-export memory/runtime measurements.
