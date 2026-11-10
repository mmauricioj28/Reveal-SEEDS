"""
Run:  python Python/database/build_census_db.py
Then query it from Python:
    import duckdb
    con = duckdb.connect("DB/census.duckdb")
    con.sql("SELECT phy_state, active_carriers FROM agg_census_state ORDER BY 2 DESC").show()
Use it alongside the crash DB (one connection, join on dot_number):
    con = duckdb.connect("DB/crash.duckdb", read_only=True)
    con.execute("ATTACH 'DB/census.duckdb' AS census (READ_ONLY)")
    con.sql("SELECT ... FROM crash_vehicle v JOIN census.census_carrier c ON c.dot_number = v.dot_number").show()
"""
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]  # Python/database/build_census_db.py -> repo root
DB_PATH = ROOT / "DB" / "census.duckdb"
SCRIPT = ROOT / "SQL" / "create_census_db.sql"
os.chdir(ROOT)  # the SQL file's read_parquet() paths are relative to the repo root

DB_PATH.parent.mkdir(exist_ok=True)  # DB/ isn't in git (databases are built locally)
DB_PATH.unlink(missing_ok=True)  # rebuild from scratch (tables with foreign keys can't simply be replaced)
# write the file in DuckDB 1.x format so VS Code extensions (which bundle DuckDB 1.5) can open it
con = duckdb.connect(str(DB_PATH), config={"storage_compatibility_version": "v1.0.0"})
con.execute(SCRIPT.read_text(encoding="utf-8"))

for (table,) in con.execute("SELECT table_name FROM duckdb_tables() ORDER BY table_name").fetchall():
    rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:24s} {rows:>10,} rows")
con.close()
print("Saved", DB_PATH)
