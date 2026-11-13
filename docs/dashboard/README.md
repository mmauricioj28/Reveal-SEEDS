# FMCSA activity explorer

Use this explorer to inspect when and where the extract contains crash and inspection records, then examine how many of those records link to carriers in the Company Census. The [chart definitions](charts.md) explain which comparisons each view supports. The [review and demo guide](handoff.md) includes reference values for the November run.

## Run locally

Start in this repository with Python 3.10 or later. Install the repository dependencies and run the tests.

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

With Node.js 18 or newer, run `node --test tests/dashboard.test.cjs` for the browser aggregation and load-error checks. The viewer itself runs in a browser without Node.

The example below uses a sibling checkout called `integration` for the upstream data. Put the archived national run in its `outputs/safety_run_2016_2025` directory. Use the independent [November 2 receipt](https://github.com/mmauricioj28/Reveal-SEEDS/blob/cc4143ae0feb318e5678163a77c31277c60ac710/docs/full_dataset_validation.json) from that checkout. The builder needs `monthly_activity.parquet`, `carrier_safety_2016_2025.parquet`, `integration_validation.json` and `run_metadata.json` from the same run.

```sh
python -m dashboard.export --run-dir ../integration/outputs/safety_run_2016_2025 --receipt ../integration/docs/full_dataset_validation.json --output-dir dashboard/data
python -m http.server 8000 --bind 127.0.0.1 --directory dashboard
```

Open [the local explorer](http://127.0.0.1:8000/). The server is rooted in the dashboard directory. No carrier identifiers or row-level events are needed by the browser. For a refresh, export to a new directory, inspect its receipt and totals, then stop the server and swap directories. The exporter refuses to replace an existing export.

### Obtain the integration inputs

The [integration checkout](https://github.com/mmauricioj28/Reveal-SEEDS/tree/cc4143ae0feb318e5678163a77c31277c60ac710) has the upstream pipeline, the independent receipt and reference aggregates. Git LFS on the default branch supplies the team's separate Census and crash Parquets. It does not supply this three-source integration run. A reviewer with the archived raw files can reproduce the run separately from the dashboard branch.

```sh
git fetch origin raghul/weeks5-6-eda-handoff
git worktree add --detach ../integration cc4143ae0feb318e5678163a77c31277c60ac710
cd ../integration
python -m pip install -r requirements-parquet.txt
python -m analysis.build_safety_dataset --census data/census.csv --crashes data/crash.csv --inspections data/inspection.csv --output-dir outputs/safety_run_2016_2025 --chunk-size 200000 --parquet
```

Use archived input files whose SHA-256 values match the receipt. For a new extraction, the upstream `python -m analysis.fetch_fmcsa_extract --dataset all --output-dir data` downloads each source with its own count and hash. A new vintage needs its own reviewed receipt with raw input hashes, requested years, linkage reconciliation and observed date ranges. Preserve the pipeline version alongside it. Return to the dashboard checkout before running the export.

### Tableau

Open `calendar.csv`, `activity.csv` and `carriers.csv` as separate text data sources. The [chart definitions](charts.md) give the dimensions, measures and filters. Joining these files row by row would multiply counts. For the original October database and its existing Tableau workflow, see the [team's DuckDB module](../../Python/fmcsa_duckdb/). This viewer opens DuckDB in memory and reads Parquet directly.

### If a run fails

| Symptom | Check |
| --- | --- |
| Parquet read error or a missing column | Check the integration directory and linkage schema. For separate default-branch data, use `git lfs install` and `git lfs pull` to materialize pointer files. |
| Receipt, coverage or count mismatch | Check both input vintages and the upstream commit. Preserve the discrepancy for review before generating charts. |
| Browser cannot load its export | Start HTTP in `dashboard` and confirm that `data/dashboard.json` exists beneath it. A file opened directly from disk cannot use the same fetch path reliably. |
| Empty inspection chart for an early year | Switch to the full period and read the first observed date. Absence can be a property of the extract. |
