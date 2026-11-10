
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
          AND YEAR BETWEEN 2016 AND 2025
          AND MONTH BETWEEN 1 AND 12
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

    # 7. Seasonal crash trends by calendar year
    # Winter = Dec, Jan, Feb within the same calendar year.
    # Spring = Mar-May; Summer = Jun-Aug; Fall = Sep-Nov.
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_seasonal_crashes AS
        SELECT
            YEAR,
            CASE
                WHEN MONTH IN (12, 1, 2) THEN 'Winter'
                WHEN MONTH IN (3, 4, 5) THEN 'Spring'
                WHEN MONTH IN (6, 7, 8) THEN 'Summer'
                WHEN MONTH IN (9, 10, 11) THEN 'Fall'
            END AS season,
            CASE
                WHEN MONTH IN (12, 1, 2) THEN 1
                WHEN MONTH IN (3, 4, 5) THEN 2
                WHEN MONTH IN (6, 7, 8) THEN 3
                WHEN MONTH IN (9, 10, 11) THEN 4
            END AS season_order,
            COUNT(*) AS months_observed,
            SUM(crash_records) AS crash_records,
            ROUND(AVG(crash_records), 2)
                AS avg_monthly_crashes
        FROM dashboard_monthly_crashes
        GROUP BY YEAR, season, season_order
    """)

    # 8. Average crash records for each calendar month
    con.execute("""
        CREATE OR REPLACE VIEW dashboard_monthly_crash_averages AS
        SELECT
            MONTH,
            COUNT(DISTINCT YEAR) AS years_observed,
            ROUND(AVG(crash_records), 2)
                AS avg_monthly_crashes,
            MIN(crash_records) AS min_monthly_crashes,
            MAX(crash_records) AS max_monthly_crashes,
            SUM(crash_records) AS total_crashes
        FROM dashboard_monthly_crashes
        GROUP BY MONTH
    """)

    print("Dashboard views created successfully.\n")

    # List all eight dashboard views
    views = [
        "dashboard_annual_crashes",
        "dashboard_fleet_size",
        "dashboard_monthly_crashes",
        "dashboard_crashes_by_state",
        "dashboard_inspections_by_state",
        "dashboard_carrier_operation",
        "dashboard_seasonal_crashes",
        "dashboard_monthly_crash_averages",
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
        (
            "Annual linked crashes",
            "dashboard_annual_crashes",
            "crash_records"
        ),
        (
            "Monthly retained crashes",
            "dashboard_monthly_crashes",
            "crash_records"
        ),
        (
            "State retained crashes",
            "dashboard_crashes_by_state",
            "crash_records"
        ),
        (
            "State retained inspections",
            "dashboard_inspections_by_state",
            "inspection_records"
        ),
        (
            "Seasonal retained crashes",
            "dashboard_seasonal_crashes",
            "crash_records"
        ),
    ]

    totals = {}

    for label, view, column in checks:
        total = con.execute(
            f'SELECT COALESCE(SUM("{column}"), 0) '
            f'FROM "{view}"'
        ).fetchone()[0]

        totals[label] = total
        print(f"{label}: {total:,}")

    # Validate seasonal aggregation
    print("\nSeasonal analysis validation:")

    monthly_total = totals["Monthly retained crashes"]
    seasonal_total = totals["Seasonal retained crashes"]

    if monthly_total != seasonal_total:
        raise ValueError(
            "Seasonal totals do not match monthly crash totals."
        )

    print("PASS: Seasonal and monthly crash totals match.")

    # Check expected coverage: 10 years x 12 months
    monthly_rows = con.execute("""
        SELECT COUNT(*)
        FROM dashboard_monthly_crashes
    """).fetchone()[0]

    seasonal_rows = con.execute("""
        SELECT COUNT(*)
        FROM dashboard_seasonal_crashes
    """).fetchone()[0]

    print(f"Monthly observations: {monthly_rows}")
    print(f"Seasonal observations: {seasonal_rows}")

    if monthly_rows != 120:
        print(
            "WARNING: Expected 120 monthly observations "
            "for 2016-2025."
        )
    else:
        print("PASS: All 120 monthly observations present.")

    if seasonal_rows != 40:
        print(
            "WARNING: Expected 40 seasonal observations "
            "for 2016-2025."
        )
    else:
        print("PASS: All 40 seasonal observations present.")

    # Verify each seasonal group has three months
    incomplete_seasons = con.execute("""
        SELECT YEAR, season, months_observed
        FROM dashboard_seasonal_crashes
        WHERE months_observed != 3
        ORDER BY YEAR, season_order
    """).fetchall()

    if incomplete_seasons:
        print("WARNING: Incomplete seasons detected:")
        for year, season, months in incomplete_seasons:
            print(f"  {year} {season}: {months} months")
    else:
        print("PASS: Every seasonal group has three months.")

print("\nAll dashboard views processed.")
