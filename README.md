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
python -m unittest discover -s tests -v
```

## Structure and interpretation

| Path | Purpose |
| --- | --- |
| analysis/mcmis_chunked.py | Existing census streaming reports and shared numeric/geographic parsers |
| analysis/build_safety_dataset.py | Extended Ayaan pipeline: three-source ingestion, aggregation, CLI and export |
| analysis/data_quality.py | Pre-publication count, linkage and measurement invariants |
| tests/ | Original census/Ayaan tests plus end-to-end pipeline edge cases |
| docs/fmcsa_pipeline.md | Reproduction, schemas, output definitions and quality inspection |
| docs/research_questions.md | Four descriptive research questions and Week 5 plan |
| docs/variable_selection.md | Official dictionary/schema review and inclusion decisions |
| docs/data_quality_decisions.md | Missingness, dates, duplicates, geography and integration contract |
| docs/weeks3_4_progress.md | Executed validation, attribution, limitations and next steps |

The research documents are contributed independently in [PR #6](https://github.com/mmauricioj28/Reveal-SEEDS/pull/6);
merge that PR as well as the engineering stack for the complete documentation set.
The engineering stack begins at Ayaan's `ayaan/data_exploration` branch; its
commit ancestry and existing tests are preserved. Harika's variable selection,
Parquet and annual/monthly exploration scripts are on her branch.

Current validation is controlled synthetic fixtures and official API smoke
samples, not complete national extracts. Crash counts are vehicle-involvement
records. OOS totals count violations. Null measurements remain distinct from
zero; no observed record does not prove no event. Current census attributes are
not historical exposure. See the guides before interpreting linked comparisons.
