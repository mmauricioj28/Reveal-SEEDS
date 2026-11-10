import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import duckdb


class IntegratedDatabaseTest(unittest.TestCase):
    def test_builder_loads_the_five_parquets_from_the_configured_directory(self):
        script = Path(__file__).resolve().parents[1] / "Python/fmcsa_duckdb/create_duckdb.py"
        tables = ("carriers", "carrier_safety_2016_2025", "crash_carrier_year",
                  "inspection_carrier_year", "monthly_activity")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "outputs/full_integration_20261024"
            source.mkdir(parents=True)
            with duckdb.connect() as con:
                for key, table in enumerate(tables):
                    con.sql("SELECT ? AS marker", params=[key]).write_parquet(
                        str(source / f"{table}.parquet")
                    )
            subprocess.run([sys.executable, str(script)], cwd=temp, check=True,
                           env={**os.environ, "FMCSA_DATA_DIR": temp}, capture_output=True)
            with duckdb.connect(str(root / "fmcsa.duckdb"), read_only=True) as con:
                for key, table in enumerate(tables):
                    self.assertEqual(con.table(table).fetchall(), [(key,)])
