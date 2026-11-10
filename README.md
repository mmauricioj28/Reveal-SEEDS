# Reveal-SEEDS

SEED2S + Reveal Fall 2026: exploring motor carrier registration and safety patterns across U.S. states using
public FMCSA data (Crash File and Company Census File from [data.transportation.gov](https://data.transportation.gov)).

The cleaned data is stored in this repo as Parquet files (via Git LFS). The two DuckDB databases are **built
locally** from those files and are never committed.

## 1. Setup

1. Install [Git LFS](https://git-lfs.com), then run once:
   ```bash
   git lfs install
   ```
2. Clone the repo (or, if you already have it, download the LFS files):
   ```bash
   git clone https://github.com/mmauricioj28/Reveal-SEEDS.git
   cd Reveal-SEEDS
   git lfs pull
   ```
   If a `.parquet` file is only a few hundred bytes, it is an LFS pointer: run `git lfs pull`.
3. Install the Python packages (Python 3.10+):
   ```bash
   python -m pip install -r requirements.txt
   ```

## 2. Build the databases (about 2 minutes)

The processed Parquet files are already in `data/processed/`, so you only need:

```bash
python Python/database/build_crash_db.py     # -> DB/crash.duckdb   (~1.5 GB)
python Python/database/build_census_db.py    # -> DB/census.duckdb  (~1.8 GB)
```

Each script creates `DB/` if needed, rebuilds the database from scratch and prints every table's row count.
Scripts can be run from any folder.

## 3. (Optional) Refresh the data from the FMCSA API

Only needed to pull newer data. Run in order, then rebuild the databases (step 2):

| Step | Command | Writes | Time |
|---|---|---|---|
| Crash download | `python Python/crash/crash_download.py` | `data/raw/crash/` (one file per year, 2015+) | ~25 min |
| Crash clean/split | `python Python/crash/crash_build_parquet.py` | `data/processed/crash/` + `_build_report.txt` | ~5 min |
| Census download | `python Python/census/census_download.py` | `data/raw/census/` (21 DOT-number chunks) | ~15 min |
| Census clean/split | `python Python/census/census_build_parquet.py` | `data/processed/census/` + `_build_report.txt` | ~5 min |

Downloads skip files that already exist; delete a file to re-download it. Each `_build_report.txt` lists the
data-quality checks and counts from that run.

## 4. Use the databases

**Python / notebooks** (both databases in one session, joined on `dot_number`):

```python
import duckdb
con = duckdb.connect("DB/crash.duckdb", read_only=True)
con.execute("ATTACH 'DB/census.duckdb' AS census (READ_ONLY)")
con.sql("""
    SELECT cc.fleet_bin, COUNT(*) AS crash_vehicles
    FROM crash_vehicle v
    JOIN census.census_carrier cc ON cc.dot_number = v.dot_number
    GROUP BY 1 ORDER BY 1
""").df()
```

**VS Code:** install the *DuckDB* extension (ChuckJonas), run **DuckDB: Attach Database...** for each file in
`DB/` (read-only), then run queries from a `.sql` file. `SQL/playground.sql` has examples.

Open the databases **read-only** when querying: a normal connection locks the file for every other program.

## Repository layout

```
Reveal-SEEDS/
├── data/                         all data (Parquet in Git LFS)
│   ├── raw/
│   │   ├── crash/                crash_2015 … crash_2026.parquet   (API download, all text)
│   │   ├── census/               census_<dot range>.parquet        (API download, all text)
│   │   └── archive/              early date-only crash CSV (not used by the pipeline)
│   └── processed/
│       ├── crash/                crash, crash_vehicle, crash_carrier, crash_event, rollups, dim_* lookups
│       └── census/               census_carrier, census_cargo, census_classification, rollups, dim_* lookups
├── Python/
│   ├── crash/                    crash_download.py, crash_build_parquet.py, crash_questions_exploration.ipynb
│   ├── census/                   census_download.py, census_build_parquet.py
│   ├── database/                 build_crash_db.py, build_census_db.py
│   └── fmcsa_duckdb/             integrated FMCSA DuckDB + Tableau export scripts (see its README)
├── SQL/                          create_crash_db.sql, create_census_db.sql (tables + keys), playground.sql
├── DB/                           crash.duckdb, census.duckdb - built locally, ignored by git
├── analysis/                     MCMIS processing and EDA modules (see docs/mcmis_processing.md)
├── tests/                        unit tests for analysis/ (python -m unittest discover -s tests -v)
└── docs/                         research questions, variable selection, data-quality decisions
```

## Things to know about the data

- **Crash grain:** `crash` has one row per crash (`crash_key`); `crash_vehicle` and `crash_carrier` have one row
  per commercial vehicle in a crash (`crash_id`). Count crashes, fatalities and injuries from `crash` - summing
  them over vehicle rows double counts multi-truck crashes.
- **Census is a snapshot:** fleet size, drivers and status are today's values, not historical ones.
  `add_date` is when a record was created *or reactivated/updated*, so it is not a clean first-registration date.
- **Recent data is incomplete:** 2026 is a partial year and late reports keep arriving for the latest months.
  The team's analysis period is 2016–2025.
- About 21% of crash vehicles have no USDOT number, so they can't be joined to the census.

## Company Census processing (analysis module)

See [the MCMIS processing guide](docs/mcmis_processing.md) for a chunked pandas pipeline, reproducible reports,
counting rules and test instructions.
