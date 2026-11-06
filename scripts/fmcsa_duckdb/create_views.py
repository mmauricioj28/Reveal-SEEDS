

import os
from pathlib import Path
import duckdb

# Database location
BASE = Path(
    os.environ.get("FMCSA_DATA_DIR", Path.cwd())
).resolve()

DB_PATH = BASE / "fmcsa.duckdb"

if not DB_PATH.is_file():
    raise FileNotFoundError(
        f"Database not found: {DB_PATH}\n"
        "Set FMCSA_DATA_DIR to your integration folder."
    )

with duckdb.connect(str(DB_PATH)) as con:

    # 1. Annual carrier-linked crash trends
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_annual_crashes AS
        SELECT
            YEAR,
            SUM(TOTAL_CRASHES) AS crash_records
        FROM crash_carrier_year
        GROUP BY YEAR
    """)

    # 2. Fleet-size comparisons for Census-matched carriers
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

    # 3. Monthly crash trends across retained event records
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_monthly_crashes AS
        SELECT
            YEAR,
            MONTH,
            SUM(record_count) AS crash_records
        FROM monthly_activity
        WHERE LOWER(source) = 'crash'
        GROUP BY YEAR, MONTH
    """)

    # 4. Crash records by event state
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_crashes_by_state AS
        SELECT
            event_state AS state,
            SUM(record_count) AS crash_records
        FROM monthly_activity
        WHERE LOWER(source) = 'crash'
          AND event_state IS NOT NULL
        GROUP BY event_state
    """)

    # 5. Inspection records by reporting state
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_inspections_by_state AS
        SELECT
            REPORT_STATE AS state,
            SUM(record_count) AS inspection_records
        FROM monthly_activity
        WHERE LOWER(source) = 'inspection'
          AND REPORT_STATE IS NOT NULL
        GROUP BY REPORT_STATE
    """)

    # 6. Carrier operation comparisons
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_carrier_operation AS
        SELECT
            COALESCE(
                CAST(CARRIER_OPERATION AS VARCHAR),
                'Missing'
            ) AS carrier_operation,
            COUNT(*) AS carrier_years,
            SUM(TOTAL_CRASHES) AS crash_records,
            SUM(TOTAL_INSPECTIONS) AS inspection_records
        FROM carrier_safety_2016_2025
        WHERE census_matched = TRUE
        GROUP BY 1
    """)

    print("Dashboard views created successfully.\n")

    views = [
        "dashboard_annual_crashes",
        "dashboard_fleet_size",
        "dashboard_monthly_crashes",
        "dashboard_crashes_by_state",
        "dashboard_inspections_by_state",
        "dashboard_carrier_operation",
    ]

    for view in views:
        count = con.execute(
            f'SELECT COUNT(*) FROM "{view}"'
        ).fetchone()[0]

        print(f"{view}: {count:,} rows")

    # Check source labels before interpreting event summaries
    print("\nMonthly activity source labels:")
    sources = con.execute("""
        SELECT
            source,
            SUM(record_count) AS total_records
        FROM monthly_activity
        GROUP BY source
        ORDER BY source
    """).fetchall()

    for source, total in sources:
        print(f"  {source}: {total:,}")

    # Show totals for each dashboard view
    print("\nDashboard record totals:")

    checks = [
        ("Annual linked crashes",
         "dashboard_annual_crashes", "crash_records"),
        ("Monthly retained crashes",
         "dashboard_monthly_crashes", "crash_records"),
        ("State retained crashes",
         "dashboard_crashes_by_state", "crash_records"),
        ("State retained inspections",
         "dashboard_inspections_by_state", "inspection_records"),
    ]

    for label, view, column in checks:
        total = con.execute(
            f'SELECT COALESCE(SUM("{column}"), 0) '
            f'FROM "{view}"'
        ).fetchone()[0]

        print(f"{label}: {total:,}")

print("\nAll dashboard views processed.")
