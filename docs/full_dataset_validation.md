# Full-dataset validation, 2016–2025 window

This note records one completed run. It does not treat the git history as a timesheet.

## What was executed

Download receipts already on disk are dated 2026-10-30. Each receipt stores the
portal `count(*)` before and after the download. The files were kept only because
those counts matched the rows written. The pipeline below was run on 2026-11-02
and re-hashed the same files.

```sh
python -m analysis.build_safety_dataset --census data/census.csv --crashes data/crash.csv --inspections data/inspection.csv --output-dir outputs/safety_run_2016_2025 --chunk-size 200000 --parquet
```

| Item | Value |
| --- | --- |
| Python | 3.11.9 |
| pandas | 3.0.5 |
| pyarrow | 25.0.1 |
| Chunk size | 200,000 |
| Runtime | 2,552.119 seconds |
| Tracemalloc peak | 239,352,214 bytes |
| Staged output bytes | 493,192,216 |
| `checks_passed` | true |

Tracemalloc measures traced Python allocations. It is not a full process
resident-set measurement. Source CSVs and the run directory stay in ignored
`data/` and `outputs/`. The machine-readable copy of this receipt is
[full_dataset_validation.json](full_dataset_validation.json).

## Inputs

The pipeline SHA-256 values match the 2026-10-30 download receipts.

| File | Resource | Rows | SHA-256 | Bytes |
| --- | --- | ---: | --- | ---: |
| census.csv | az4n-8mr2 | 4,523,548 | `69b0436f9b36a3fa9f0351ae562f972976378a962b47ab63ad3b1f1e8a82cd00` | 145,330,502 |
| crash.csv | aayw-vxb3 | 1,868,953 | `7bc632006f33f29b9b4337ba156f442c858838c192a036c70813f5507d1c03a6` | 65,517,436 |
| inspection.csv | fx4q-ay7w | 5,852,073 | `aae81c53662b7765af38fba500be87e4e65853a9c19d73a1aa3bc4e1728386a5` | 237,643,434 |

Crash rows are the portal result for `report_date` from 20160101 through 20251231.
Inspection rows are the portal result for `insp_date` in that same window. Census
is the current Company Census snapshot, not a historical panel. Selected columns
are listed in the JSON receipt. No requested column was absent.

## Reconciliation

Every input row was retained. Duplicate primary keys, invalid dates, out-of-window
dates, and excluded inspection statuses were all zero. `checks_passed` requires
the raw-row partition, the monthly totals, the carrier-year sums, and the
match-status totals to agree.

| Source | Input and retained | Matched | Unmatched | Unidentified |
| --- | ---: | ---: | ---: | ---: |
| Census | 4,523,548 | 4,523,548 carriers stored | — | 0 |
| Crash | 1,868,953 | 1,445,220 | 22,154 | 401,579 |
| Inspection | 5,852,073 | 5,851,766 | 307 | 0 |

Crash identity: 1,445,220 + 22,154 + 401,579 = 1,868,953.
Inspection identity: 5,851,766 + 307 + 0 = 5,852,073.

Monthly crash and inspection totals equal those retained counts, so unmatched and
unidentified crash records are still in the yearly, monthly, and state tables.
Carrier-year crash and inspection sums equal the linkable counts only. Records
with no usable DOT never enter the carrier-year join.

Unmatched share of linkable crash records: 22,154 / 1,467,374 = 1.5098%.
The denominator is retained crashes with a usable DOT. The 401,579 unidentified
crashes are not in that denominator. This percent was calculated from the run.
It is not a hardcoded 1.4%. Linkable inspection records are 307 / 5,852,073 =
0.0052% unmatched.

Integrated output: 1,569,209 carrier-years, 773,094 distinct event DOT numbers,
772,179 of those also present in the census extract, and 3,751,369 census DOT
numbers with no retained event in this join.

Linkable crash measurements, which omit unidentified records: 49,805 fatalities
and 725,174 injuries, each observed on all 1,467,374 linkable crash records.
Those are summed reported fields, not a FARS total and not a rate. Inspection
violation and out-of-service fields were present on every retained inspection
and reconciled to the integrated sums.

## Coverage

| Source | Earliest retained date | Latest retained date | Months with no retained rows |
| --- | --- | --- | ---: |
| Crash | 2016-01-01 | 2025-12-31 | 0 of 120 |
| Inspection | 2023-10-30 | 2025-12-31 | 93 of 120 |

The inspection file returned by the portal query does not contain dates before
2023-10-30. October 2023 is a partial month. 2016 through September 2023 are
unobserved for inspections. They are not recorded as zero-event months.
Crash months from January 2016 through December 2025 are all present in the
extract. Presence of a December 2025 crash date does not prove that every state
has finished reporting.

This crash extract has one row per `CRASH_ID` (no duplicate IDs). It is not the
vehicle-level crash file on Michael's branch. The pipeline would keep the first
row if a crash ID were repeated. That rule was not exercised by these inputs.

## Limits

Census attributes are the current snapshot. Grouping a 2016 crash by today's
power units does not mean the carrier had that fleet in 2016. Safety rating is
missing for 4,287,005 of 4,523,548 census rows, so it is not used as a grouping
variable. Many mileage-year values fall outside the 1900–2100 check and are not
used as exposure. Null measurements stay null. No national file is committed.
