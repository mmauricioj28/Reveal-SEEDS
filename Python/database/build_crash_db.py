"""
Run from the repo root:  python SQL/build_crash_db.py
Then query it from Python:
    import duckdb
    con = duckdb.connect("SQL/crash.duckdb")
    con.sql("SELECT state, SUM(crashes) FROM agg_state_year GROUP BY 1 ORDER BY 2 DESC").show()
"""
from pathlib import Path

import duckdb

DB_PATH = Path("SQL") / "crash.duckdb"
SCRIPT = Path("SQL") / "create_crash_db.sql"

DB_PATH.unlink(missing_ok=True)  # rebuild from scratch (tables with foreign keys can't simply be replaced)
# write the file in DuckDB 1.x format so VS Code extensions (which bundle DuckDB 1.5) can open it
con = duckdb.connect(str(DB_PATH), config={"storage_compatibility_version": "v1.0.0"})
con.execute(SCRIPT.read_text(encoding="utf-8"))

for (table,) in con.execute("SELECT table_name FROM duckdb_tables() ORDER BY table_name").fetchall():
    rows = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"{table:24s} {rows:>10,} rows")
con.close()
print("Saved", DB_PATH)
