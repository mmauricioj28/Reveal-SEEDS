# Weeks 3–4 technical progress

Reporting window: October 5–16, 2026. This contribution was implemented and
validated on October 16. Dates/timestamps were not backdated. The supplied
October 9 mentor guidance informed the 2016–2025 interval, selected-column
processing, dictionary review and exploratory questions; no meeting transcript
or personal-hours certification is implied. Planned scholar activities are not
evidence of hours personally worked.

## Completed contributions

| Deliverable | Implemented result | Evidence / review |
| --- | --- | --- |
| Research plan | Four testable descriptive questions, units, measures, limitations, dashboard uses and Week 5 acceptance plan | PR #6: docs/research_questions.md |
| Variable/dictionary review | Actual 147-column census, 59-column crash and 63-column inspection schemas; selected definitions, nullable types and exclusions | PR #6: docs/variable_selection.md and data_quality_decisions.md |
| Processing and integration | Extend existing three-source script with selected-string pandas chunks, SQLite ID deduplication, 2016–2025 filtering, source DOT/year aggregates and unioned linkage | PR #7: analysis/build_safety_dataset.py |
| Quality validation | Raw/retained/excluded partitions, duplicate conflicts, missing/invalid/zero profiles, geography, date/month coverage, matched/unmatched carrier counts and event/measurement reconciliation | PR #8: analysis/data_quality.py and tests/test_safety_pipeline.py |
| Reproducibility | Practical CLI, CSV/optional typed Parquet, source checksums and machine-readable receipts, README and usage guide | This documentation PR |

## Existing team work preserved

- PR #5 (`4570a3d`) was already merged into main (`41c4a83`). Its census
  processor, documentation history, pandas dependency and all 14 tests are
  preserved. The new workflow reuses its exact integer/location parsers.
- Ayaan's `ayaan/data_exploration` (`5c6e5b7`) already implemented three-source
  carrier integration and two tests. PR #7 extends that script, retains its
  ancestry/tests and avoids a competing pipeline. Its full-frame helper APIs
  are replaced by streaming internals as explained in the reproduction guide.
- Harika's branch includes preliminary variable selection, safety missingness,
  selected census Parquet, annual crash/inspection and monthly inspection
  analyses. These were inspected; no teammate script or reported full-census
  result is presented as new work here. This contribution applies the supplied
  2016–2025 guidance even where earlier plans mentioned 2015.
- Michael's PR #3 remains open with downloader/notebooks, CSV LFS rules and a
  date-only crash extract. A date-only extract cannot support DOT linkage; obtain
  the required identity fields. His branch/files were not overwritten.
- Armaan's fetched FARS branch had no diff from current main at inspection.

## Executed validation

Environment: Windows, Python **3.12.14**, pandas **3.0.1**, pyarrow **23.0.1**.
The optional Arrow package was installed in a local directory outside the repo.
Windows sandbox ACLs on that installation required running Arrow validation
outside the sandbox; no production service or cloud runtime was needed.

`python -m unittest discover -s tests -v`: **37 tests passed**, comprising the
14 original census tests, two existing Ayaan tests and 21 pipeline tests. Coverage
includes multiple events per carrier, DOT formatting/invalid/missing IDs, both
window boundaries, invalid calendar dates, cross-chunk duplicate conflicts,
unmatched carriers, missing/zero measurements, US/non-US/unknown geography,
missing columns/header-only extracts, output protection/source immutability,
CLI exit codes and typed Parquet with null-first batches/empty event tables.
Injected count inflation and measurement inflation both fail publication.
Compileall and `git diff --check` passed. Synthetic fixtures are generated in
temporary directories; they are not real research results.

Official dictionaries and live metadata were retrieved on October 16. The three
user-provided dictionary PDFs match official attachment bytes by SHA-256; their
checksums are recorded in [the machine-readable receipt](official_sample_validation.json).
No authoritative field meaning was inferred from metadata's blank descriptions.
Field-specific blank versus non-applicable measurement meanings remain unresolved
where the dictionary does not establish a distinction.

The final real-data smoke run used the exact requests/checksums in that receipt:

| Check | Executed result |
| --- | --- |
| Census queried by union of sampled positive event DOTs | 170 rows retained; 170 unique carriers |
| Crash sample, ordered CRASH_ID within requested window | 100 records; January 1–6, 2016; 18 missing DOT; 82 linkable records |
| Inspection sample, ordered INSPECTION_ID within requested window | 100 records; October 15–16, 2023; all 100 linkable |
| Integrated output | 174 DOT/year keys, 170 distinct carriers; 82 crash records + 100 inspections |
| Census matching | All usable sampled DOTs matched; census was intentionally selected by those DOTs, so this is not a population match-rate estimate |
| Monthly outputs | Preserve all 100 crash records and all 100 inspections, including the 18 unidentified crash records |
| Chunk sizes | 17 and 100 produced byte-identical five CSVs, quality.json and integration_validation.json |
| Parquet | All five Arrow tables equal across chunk sizes, including types/nulls; file bytes need not be identical because row-group sizes differ |
| Invariants | Raw/retained partitions, source/integrated counts, union keys, matched/unmatched counts and observed measurement sums/counts passed |

The new workflow also processed initial unfiltered 100-row samples; those crash
rows were from 1990 and correctly excluded. The final in-window samples above
are the integration validation evidence. Raw samples and generated analytical
outputs remain outside Git under the local `../source-verification/` directory.

## Current limits and Week 5 work

This is a working preprocessing foundation validated on fixtures and narrow API
samples. **Full national files were not downloaded/processed or benchmarked.**
The sample does not establish coverage of all 120 months or support substantive
national trends, fleet comparisons or seasonal findings. Other platforms,
Python/pandas/Arrow versions and CI execution have not been validated here.

The first eligible duplicate wins; conflicting revisions require review and input
ordering matters. Processing statuses other than inspection D remain included.
Inspect status/recordability policy and all exclusions before interpreting
safety counts. Country syntax is validated, but unrecognized two-letter country
codes are not certified official. Unknown/non-applicable measurements remain
nullable, with observed-value denominators. SQLite/int64 sum overflow aborts a
run; disk/runtime requirements need full-export measurement.

Current census principal-office location, fleet and mileage describe a snapshot,
not historical operating exposure. Crash records represent vehicle involvements;
severity sums may repeat casualties across records. Inspection totals describe
selected inspections and violations, not random fleet exposure. No crash-risk
or causal interpretation is supported by these outputs.

Week 5 should acquire complete dated exports with verified acquisition receipts,
measure runtime/peak memory/disk on full inputs, inspect all month/state/status
coverage and missingness, review duplicate conflicts and unmatched carriers,
then begin descriptive EDA using the documented questions. Investigate dated
census snapshots and compatible exposure measures before any rate estimates.
Use state-stratified sampling with documented weights only if necessary; the
pipeline itself does not sample. Dashboard/model implementation remains deferred.

## GitHub handoff

PR #6 is independent research documentation against main. PR #7 targets Ayaan's
existing branch; PR #8 targets #7's feature branch; this documentation branch
targets #8's feature branch. Ayaan's branch must land before retargeting #7 to
main, and #6 must also merge for the full research documentation set. Review
dependencies explicitly; no unreviewed PR was merged, main was not committed
to, teammates' branches were not changed, and no force push was used.

The GitHub connector denied PR creation with HTTP 403; the repository's existing
Git credential successfully pushed branches and opened PRs through the GitHub
API. Credentials were neither printed nor written into repository files.
