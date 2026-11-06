"""
Run from the repo root:  python SQL/build_census_db.py
Then query it from Python:
    import duckdb
    con = duckdb.connect("SQL/census.duckdb")
    con.sql("SELECT phy_state, active_carriers FROM agg_census_state ORDER BY 2 DESC").show()
Use it alongside the crash DB (one connection, join on dot_number):
    con = duckdb.connect("SQL/crash.duckdb", read_only=True)
    con.execute("ATTACH 'SQL/census.duckdb' AS census (READ_ONLY)")
    con.sql("SELECT ... FROM crash_vehicle v JOIN census.census_carrier c ON c.dot_number = v.dot_number").show()
"""
from pathlib import Path

import duckdb

DB_PATH = Path("SQL") / "census.duckdb"
SCRIPT = Path("SQL") / "create_census_db.sql"

DB_PATH.unlink(missing_ok=True)  # rebuild from scratch (tables with foreign keys can't simply be replaced)
# write the file in DuckDB 1.x format so VS Code extensions (which bundle DuckDB 1.5) can open it
con = duckdb.connect(str(DB_PATH), config={"storage_compatibility_version": "v1.0.0"})
con.execute(SCRIPT.read_text(encoding="utf-8"))

for (table,) in con.execute("SELECT table_name FROM duckdb_tables() ORDER BY table_name").fetchall():
    rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:24s} {rows:>10,} rows")
con.close()
print("Saved", DB_PATH)
