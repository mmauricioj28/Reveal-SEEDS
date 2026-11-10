
import os
from pathlib import Path
import duckdb

BASE = Path(
    os.environ.get("FMCSA_DATA_DIR", Path.cwd())
).resolve()

DB_PATH = BASE / "fmcsa.duckdb"
OUTPUT_DIR = BASE / "tableau_exports"

if not DB_PATH.is_file():
    raise FileNotFoundError(
        f"Database not found: {DB_PATH}\n"
        "Set FMCSA_DATA_DIR to your integration folder."
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

exports = {
    "dashboard_monthly_crashes": "monthly_crashes.csv",
    "dashboard_seasonal_crashes": "seasonal_crashes.csv",
    "dashboard_monthly_crash_averages": "monthly_crash_averages.csv",
}

with duckdb.connect(str(DB_PATH), read_only=True) as con:
    for view, filename in exports.items():
        output_path = OUTPUT_DIR / filename

        con.execute(
            f"COPY (SELECT * FROM {view}) "
            "TO ? (FORMAT CSV, HEADER TRUE)",
            [str(output_path)]
        )

        rows = con.execute(
            f"SELECT COUNT(*) FROM {view}"
        ).fetchone()[0]

        print(f"{filename}: {rows:,} rows exported")

print(f"\nExports saved to: {OUTPUT_DIR}")
print("Tableau export complete.")
