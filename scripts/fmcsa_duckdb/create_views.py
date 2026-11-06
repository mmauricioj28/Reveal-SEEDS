
import os
from pathlib import Path
import duckdb

BASE = Path(
    os.environ.get("FMCSA_DATA_DIR", Path.cwd())
).resolve()

db_path = BASE / "fmcsa.duckdb"

with duckdb.connect(str(db_path)) as con:
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_annual_crashes AS
        SELECT
            YEAR,
            SUM(TOTAL_CRASHES) AS crash_records
        FROM crash_carrier_year
        GROUP BY YEAR
    """)

    con.execute("""
        CREATE OR REPLACE VIEW dashboard_fleet_size AS
        SELECT
            CASE
                WHEN POWER_UNITS IS NULL THEN 'Missing'
                WHEN POWER_UNITS = 0 THEN '0'
                WHEN POWER_UNITS = 1 THEN '1'
                WHEN POWER_UNITS BETWEEN 2 AND 5 THEN '2-5'
                WHEN POWER_UNITS BETWEEN 6 AND 20 THEN '6-20'
                WHEN POWER_UNITS BETWEEN 21 AND 100 THEN '21-100'
                ELSE '101+'
            END AS fleet_group,
            COUNT(*) AS carrier_years,
            SUM(TOTAL_CRASHES) AS crash_records,
            SUM(TOTAL_INSPECTIONS) AS inspection_records
        FROM carrier_safety_2016_2025
        WHERE census_matched = TRUE
        GROUP BY 1
    """)

    print("Dashboard views created.")

    for view in ["dashboard_annual_crashes", "dashboard_fleet_size"]:
        count = con.execute(
            f"SELECT COUNT(*) FROM {view}"
        ).fetchone()[0]
        print(f"{view}: {count:,} rows")

