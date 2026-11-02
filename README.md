# Reveal-SEEDS

Rutgers SEED2S+Reveal research on geographic and operational patterns in US motor
carrier records. The Weeks 3–4 foundation prepares **2016–2025 inclusive** crash
and vehicle-inspection records for exploratory analysis. It does not estimate
crash risk, build a dashboard or train a model.

## Setup and data

Python 3.10+; pandas is required. Install optional pyarrow for Parquet:

```sh
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -r requirements-parquet.txt
```

Download CSVs from the official FMCSA resources into an ignored local `data/`
directory. Keep filenames/extract dates and record whether each file is a sample
or a full export. Do not mix independent samples for population inference.
A counted download of the selected columns is:

```sh
python -m analysis.fetch_fmcsa_extract --dataset all --output-dir data
```

That command writes `census.csv`, `crash.csv`, and `inspection.csv` only when
the row count matches the portal `count(*)` before and after the download.

- [Company Census](https://data.transportation.gov/Trucking-and-Motorcoaches/Company-Census-File/az4n-8mr2/about_data)
- [Crash](https://data.transportation.gov/Trucking-and-Motorcoaches/Crash-File/aayw-vxb3/about_data)
- [Vehicle Inspection](https://data.transportation.gov/Trucking-and-Motorcoaches/Vehicle-Inspection-File/fx4q-ay7w/about_data)

See [acquisition and output details](docs/fmcsa_pipeline.md). Raw data, Parquet,
outputs and environments must stay out of commits. Michael's exploration branch
has CSV Git LFS tracking in PR #3. If using its tracked files, install
[Git LFS](https://git-lfs.com), run `git lfs install` then `git lfs pull`; a pointer
file is not a dataset. The local-path pipeline does not require LFS.

## Run preprocessing

Run from the repository root; commands also work in PowerShell. Choose a new
output directory each time. Quote paths containing spaces.

```sh
python -m analysis.build_safety_dataset --census "data/Company_Census_File.csv" --crashes "data/Crash_File.csv" --inspections "data/Vehicle_Inspection_File.csv" --output-dir "outputs/safety_run_01" --chunk-size 100000 --parquet
```

Omit `--parquet` for a pandas-only run. The CLI selects verified columns, validates
dates/identifiers, filters events, deduplicates on disk and aggregates each source
by DOT/year before joining. CSVs, optional typed Parquet, source checksums,
quality profiles and count/measurement reconciliation are published together.
The original census reports remain available:

```sh
python -m analysis.mcmis_chunked --input "data/Company_Census_File.csv" --output-dir "outputs/census_run_01" --chunk-size 100000
python -m analysis.eda_trends --run-dir "outputs/safety_run_01" --output-dir "outputs/eda_01"
python -m analysis.plot_trends --eda-dir "outputs/eda_01" --output-dir "outputs/charts_01"
python -m unittest discover -s tests -v
```

Yearly, monthly, and state tables keep matched, unmatched, and unidentified
records. Fleet size, driver count, and carrier operation use matched records
only, with the excluded counts written beside them. See
[docs/dashboard_exports.md](docs/dashboard_exports.md).

## Structure and interpretation

| Path | Purpose |
| --- | --- |
| analysis/mcmis_chunked.py | Existing census streaming reports and shared numeric/geographic parsers |
| analysis/build_safety_dataset.py | Extended Ayaan pipeline: three-source ingestion, aggregation, CLI and export |
| analysis/data_quality.py | Pre-publication count, linkage and measurement invariants, including match status |
| analysis/eda_trends.py | Yearly, monthly, state, and matched-carrier tables from a pipeline run |
| analysis/plot_trends.py | Charts for those tables. Counts are not labeled as rates |
| analysis/fetch_fmcsa_extract.py | Selected-column portal download that must match `count(*)` |
| tests/ | Census, pipeline, linkage, EDA, and chart tests |
| docs/fmcsa_pipeline.md | Reproduction, schemas, output definitions and quality inspection |
| docs/dashboard_exports.md | Grain, denominators, and null rules for the EDA tables |
| docs/research_questions.md | Weeks 3–4 plan and three narrowed Weeks 5–6 questions |
| docs/eda_findings_2016_2025.md | Findings from the executed extract, with coverage limits |
| docs/weeks3_4_progress.md | Weeks 3–4 validation. Not rewritten by the later progress note |
| docs/weeks5_6_progress.md | Weeks 5–6 implementation, tests, and remaining work |

The research documents are contributed independently in [PR #6](https://github.com/mmauricioj28/Reveal-SEEDS/pull/6);
merge that PR as well as the engineering stack for the complete documentation set.
The engineering stack begins at Ayaan's `ayaan/data_exploration` branch; its
commit ancestry and existing tests are preserved. Harika's variable selection,
Parquet and annual/monthly exploration scripts are on her branch.

Crash file rows are vehicle involvements. This pipeline keeps one row per
`CRASH_ID`, so a multi-vehicle crash is not counted once for every vehicle.
OOS totals count violations. Null measurements remain distinct from zero; no
observed record does not prove no event. Current census attributes are not
historical exposure. Unmatched percentages use records with a usable DOT number
as the denominator and do not fold in missing or invalid DOT numbers. See the
guides before interpreting linked comparisons. The Weeks 5–6 run receipt is
[docs/full_dataset_validation.md](docs/full_dataset_validation.md). In that run,
crash records cover every month from 2016-01 through 2025-12. The inspection
extract’s earliest retained date is 2023-10-30, so earlier inspection months
are unobserved rather than zero.
