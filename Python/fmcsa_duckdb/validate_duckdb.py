
import os
from pathlib import Path
import duckdb

BASE = Path(
    os.environ.get("FMCSA_DATA_DIR", Path.cwd())
).resolve()

DB_PATH = BASE / "fmcsa.duckdb"
expected = {
    "carriers": (4509823, ["DOT_NUMBER"]),
    "carrier_safety_2016_2025": (1578012, ["DOT_NUMBER", "YEAR"]),
    "crash_carrier_year": (749386, ["DOT_NUMBER", "YEAR"]),
    "inspection_carrier_year": (967321, ["DOT_NUMBER", "YEAR"]),
    "monthly_activity": (7699, None),
}

with duckdb.connect(str(DB_PATH), read_only=True) as con:
    for table, (expected_count, keys) in expected.items():
        count = con.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0]

        assert count == expected_count, (
            f"{table}: expected {expected_count}, got {count}"
        )

        print(f"{table}: {count:,} rows - PASS")

        if keys:
            key_sql = ", ".join(f'"{key}"' for key in keys)

            duplicates = con.execute(
                f'SELECT COUNT(*) - COUNT(DISTINCT ({key_sql})) '
                f'FROM "{table}"'
            ).fetchone()[0]

            missing = con.execute(
                f'SELECT COUNT(*) FROM "{table}" '
                'WHERE "DOT_NUMBER" IS NULL'
            ).fetchone()[0]

            assert duplicates == 0, f"{table}: duplicate keys"
            assert missing == 0, f"{table}: missing DOT_NUMBER"

            print("  Unique keys: PASS")
            print("  Missing DOT_NUMBER: PASS")

    for source in ["crash_carrier_year", "inspection_carrier_year"]:
        missing_links = con.execute(f"""
            SELECT COUNT(*)
            FROM "{source}" AS s
            LEFT JOIN carrier_safety_2016_2025 AS c
              ON s.DOT_NUMBER = c.DOT_NUMBER
             AND s.YEAR = c.YEAR
            WHERE c.DOT_NUMBER IS NULL
        """).fetchone()[0]

        assert missing_links == 0, (
            f"{source}: {missing_links} missing carrier-year links"
        )

        print(f"{source} relationships: PASS")

print("\nALL DATABASE VALIDATION CHECKS PASSED")

