# Repository integration audit (Weeks 5–6 baseline)

Inspected 2026-10-30 from the local clone and `origin` after `git fetch`. No local
uncommitted work was present. Existing `raghul/*` branches were already pushed.
This branch starts at `ayaan/data_exploration` (`fa6aeb1`) so the pull request
contains only the new commits.

## Where the code actually lives

| Branch | Role |
| --- | --- |
| `main` (`4898f81`) | PR #5 chunked census, PR #6 research notes, PR #10 Michael's crash Parquet/LFS exploration |
| `ayaan/data_exploration` | Authoritative three-source pipeline plus Ayaan's yearly/monthly/state EDA and charts |
| `raghul/fmcsa-preprocessing-integration` | PRs #7–#9 were merged here and into Ayaan's branch, not into `main` |
| `harika/mcmis-data-exploration` | Separate census/crash/inspection scripts. Not copied into this stack |

`monthly_activity` on this baseline groups retained events by source, year, month,
and geography. It does not keep matched / unmatched / unidentified counts. That
classification is added on the linkage branch rather than inferred after the fact.

## Pipeline contract already in place

`analysis/build_safety_dataset.py` is the integration entry point. It extends
Ayaan's carrier-year join with streaming CSV ingestion, DOT normalization from
`analysis/mcmis_chunked.py`, the inclusive 2016–2025 window, SQLite aggregation
before the join, and `analysis/data_quality.py` reconciliation. `data/` and
`outputs/` are gitignored. `main` tracks CSV/Parquet with Git LFS; those objects
are Michael's crash extracts, not a three-source run of this pipeline.

Michael's crash build report on `main` records 2,168,212 vehicle rows for
2015–2026 and 2,026,244 crash-level rows. The portal `count(*)` on 2026-10-30 for
`report_date` from 20160101 through 20251231 was 1,868,953. Census `count(*)` was
4,523,548. Inspection `count(*)` for `insp_date` in the same window was 5,852,073.
This pipeline still deduplicates on `CRASH_ID`, so a multi-vehicle crash file row
is not the same thing as a retained crash record. The full-run receipt has to
report both numbers.

## Reproduction gap closed here

Full national files were not in the working tree (LFS pointers are not datasets).
`analysis/fetch_fmcsa_extract.py` pages the official resource with `$order=:id`
and publishes a file only when the written row count equals `count(*)` before and
after the download. Outputs stay local.
