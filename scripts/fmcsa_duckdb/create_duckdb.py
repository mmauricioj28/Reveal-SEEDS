import os
from pathlib import Path
import duckdb

BASE = Path(
    os.environ.get("FMCSA_DATA_DIR", Path.cwd())
).resolve()

SOURCE = BASE / "outputs" / "full_integration_20261024"
DB_PATH = BASE / "fmcsa.duckdb"tables = {
    "carriers": "carriers.parquet",
    "carrier_safety_2016_2025": "carrier_safety_2016_2025.parquet",
    "crash_carrier_year": "crash_carrier_year.parquet",
    "inspection_carrier_year": "inspection_carrier_year.parquet",
    "monthly_activity": "monthly_activity.parquet",
}

# Check all input files before creating the database
for filename in tables.values():
    filepath = SOURCE / filename
    if not filepath.is_file():
        raise FileNotFoundError(f"Missing file: {filepath}")

with duckdb.connect(str(DB_PATH)) as con:
    for table, filename in tables.items():
        print(f"Loading {table}...")

        con.execute(
            f'CREATE OR REPLACE TABLE "{table}" AS '
            "SELECT * FROM read_parquet(?)",
            [str(SOURCE / filename)]
        )

        count = con.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        print(f"Loaded {count:,} rows")

print(f"\nDatabase ready: {DB_PATH}")
