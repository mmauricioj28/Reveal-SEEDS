# EDA readiness checklist

Checked against the 2026-11-02 pipeline run and the unit tests run the same day.
`checks_passed` is the pipeline's arithmetic reconciliation. It does not certify
complete state reporting.

| Check | Status | Evidence |
| --- | --- | --- |
| Census, crash, and inspection inputs match portal row counts and SHA-256 | Pass | Download receipts dated 2026-10-30; hashes repeated in `run_metadata.json` |
| Input rows equal retained + excluded + duplicates | Pass | All three sources: excluded and duplicates are 0; input equals retained |
| Match status is matched, unmatched, or unidentified | Pass | `integration_validation.json`; unidentified crashes are not in the unmatched percent |
| Monthly totals keep unmatched and unidentified records | Pass | Crash monthly sum 1,868,953; inspection monthly sum 5,852,073 |
| Carrier-characteristic tables use matched records only | Pass | Fleet crash sum 1,445,220 equals matched crashes |
| Excluded counts name the denominator | Pass | `excluded_record_counts.csv` |
| Crash months 2016-01 through 2025-12 are present | Pass | 0 unobserved crash months |
| Inspection history for 2016 through September 2023 | Fail as full-period coverage; pass as labeled non-coverage | Earliest date 2023-10-30; 93 months listed in `unobserved_months.csv`, not filled with zero |
| Year-over-year change suppressed when a year lacks 12 months | Pass | Inspection 2023 to 2024 is blank; 2024 to 2025 is reported as a count change |
| Missing fleet size stays missing | Pass | 38 matched carrier-years in the `missing` bin |
| Census snapshot limitation is stated on carrier charts and in the findings | Pass | `fleet_size_crashes.png`; [eda_findings_2016_2025.md](eda_findings_2016_2025.md) |
| Research questions use variables the pipeline actually writes | Pass | [research_questions.md](research_questions.md) questions Q1–Q3 |
| Automated tests | Pass | `python -m unittest discover -s tests -v`: 44 tests, OK |

Remaining blocker for a 2016–2025 inspection trend: the official inspection
extract used here does not contain those earlier months. A later dashboard
should keep that coverage flag on every inspection series.
