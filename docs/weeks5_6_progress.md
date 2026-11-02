# Weeks 5–6 technical progress

Reporting window in the time log: 19–30 October 2026. The notes below map that
work to files and commits. Commit dates are not a timesheet, and nothing here
is a meeting transcript.

The engineering stack starts at Ayaan's `ayaan/data_exploration` branch.
Weeks 3–4 documentation is unchanged in [weeks3_4_progress.md](weeks3_4_progress.md).
National source files are not in git. The completed pipeline run is dated
2026-11-02 and is summarized in [full_dataset_validation.md](full_dataset_validation.md).

## Evidence by time-log entry

| Date | Hours | Technical evidence |
| --- | ---: | --- |
| October 19 | 2 | [repository_integration_audit.md](repository_integration_audit.md). Authoritative pipeline is `analysis/build_safety_dataset.py` on Ayaan's branch. PRs #7–#9 are on that line, not only on `main`. |
| October 20 | 3 | `analysis/fetch_fmcsa_extract.py` and the 2026-11-02 run of that pipeline on the counted national extracts. Receipt: [full_dataset_validation.json](full_dataset_validation.json). `checks_passed` is true. |
| October 22 | 2 | Match status in `analysis/build_safety_dataset.py` and `analysis/data_quality.py`. Hand-counted tests in `tests/test_linkage_rules.py`. |
| October 23 | 3 | Output contract in [fmcsa_pipeline.md](fmcsa_pipeline.md) and the pass/fail list in [eda_readiness.md](eda_readiness.md). |
| October 26 | 2 | `analysis/eda_trends.py` and the tables in [eda_2016_2025](eda_2016_2025/). |
| October 27 | 3 | `analysis/plot_trends.py`, `tests/test_plot_trends.py`, and [figures/weeks5_6](figures/weeks5_6/). Fleet and operation charts are matched-only and print the excluded counts. |
| October 29 | 2 | Three questions in [research_questions.md](research_questions.md) and the measured results in [eda_findings_2016_2025.md](eda_findings_2016_2025.md). |
| October 30 | 3 | [dashboard_exports.md](dashboard_exports.md), README commands, and this note. |

## Nicole's instructions

| Instruction | How it is handled |
| --- | --- |
| Run the pipeline, then do EDA | Run on 2026-11-02 after the counted download. EDA reads that run directory. |
| Yearly and monthly patterns | `yearly_activity.csv`, `monthly_pattern.csv`, `month_of_year.csv` |
| Keep unmatched crashes in yearly, monthly, and state summaries | `monthly_activity` groups by `match_status`. Monthly sums equal retained event totals. |
| Separate linkable-unmatched from unidentified | Two statuses. The unmatched percent uses usable DOT records only. |
| Drop unmatched records from carrier comparisons, and disclose the counts | `excluded_record_counts.csv`. Crash charts repeat 22,154 unmatched and 401,579 unidentified of 1,868,953. |
| Do not hardcode the earlier 1.4% figure | Calculated unmatched share of linkable crashes is 1.5098% (22,154 / 1,467,374). The 2022 slice is 1.40%. |
| Current census attributes, with a snapshot caveat | Fleet, driver, and operation tables say the values are current. Findings repeat that a 2016 event was not necessarily hauled by today's fleet. |
| Descriptive language | Charts are labeled as counts, not rates. Findings separate observed counts from explanations that still need research. |
| Definitions consistent with the files in use | Crash `STATE` is crash location. Inspection `REPORT_STATE` is the upload jurisdiction. Census `PHY_STATE` is headquarters and is not used as the event location. |

## Tests and run metrics

`python -m unittest discover -s tests -v` on 2026-11-02: 44 tests, OK.

Pipeline: 2,552 seconds, chunk size 200,000, tracemalloc peak 239,352,214 bytes,
`checks_passed` true. Census 4,523,548; crashes 1,868,953; inspections 5,852,073.
No input row was dropped as a duplicate or as an out-of-window date. Inspection
coverage still begins on 2023-10-30. That is a property of this extract, not a
failed reconciliation.

## Questions carried forward

1. How do retained crash and inspection records vary by year and month?
2. How are retained records distributed across states, with crash location kept
   separate from inspection jurisdiction?
3. Among census-matched records, how do crash and inspection counts differ by
   current fleet size and carrier operation?

Measured answers, and the limits on them, are in
[eda_findings_2016_2025.md](eda_findings_2016_2025.md).

## Weeks 7–8

- Build the dashboard from `docs/eda_2016_2025/` and the column rules in
  [dashboard_exports.md](dashboard_exports.md). Keep match status, the exclusion
  counts, and the census-snapshot label on the carrier pages.
- Show inspection series as beginning 2023-10-30. Do not backfill 2016–2022
  with zeros unless a different official extract is obtained and reconciled.
- Draft the white paper from the three questions. Keep crash location, inspection
  jurisdiction, and headquarters in separate sentences.
- Decide whether a vehicle-level crash file is required. This extract has one
  row per `CRASH_ID`.
- Add exposure only if a defensible denominator is chosen. Current mileage and
  current power units are not historical exposure.
- Review the stacked pull requests before anything is merged. Do not merge them
  to `main` until that review.
