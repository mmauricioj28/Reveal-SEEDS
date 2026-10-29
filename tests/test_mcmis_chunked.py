"""Small fixtures verify carrier semantics and byte-identical aggregate reports."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from analysis.mcmis_chunked import process_csv


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "census.csv"

    def write(self, rows, header=None):
        header = header or ["DOT_NUMBER", "PHY_STATE", "PHY_COUNTRY", "TOTAL_DRIVERS",
                            "POWER_UNITS", "MCS150_MILEAGE", "MCS150_MILEAGE_YEAR"]
        with self.source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)

    def report(self, name, run="out"):
        return pd.read_csv(self.root / run / name, keep_default_na=False)

    def fixture(self):
        self.write([
            ["001", " nj ", "us", "0", "0", "0", "2025"],
            ["2", "CA", "US", "10.0", "5", "100", "2024"],
            ["1.0", "ON", "CA", "900", "900", "900", "2025"],
            ["3", "ON", "CA", "", "", "", ""],
            ["4", "XX", "US", "bad", "-1", "inf", "9999"],
            ["", "", "", "7", "7", "7", "2025"],
            ["bad", "MX", "MX", "8", "8", "8", "2025"],
            ["5", "CA", "CA", "2", "101", "200", "2025"],
            ["2", "CA", "US", "999", "999", "999", "2025"],
            ["6", "???", "US", "1.5", "2", "NULL", "0"],
        ])

    def test_chunk_size_independence(self):
        self.fixture()
        with patch("analysis.mcmis_chunked.pd.read_csv", wraps=pd.read_csv) as read:
            for size in (1, 2, 3, 100):
                process_csv(self.source, self.root / f"out{size}", size)
            for call in read.call_args_list:
                self.assertGreater(call.kwargs["chunksize"], 0)
                self.assertIn("usecols", call.kwargs)
        for name in (self.root / "out1").glob("*.csv"):
            for size in (2, 3, 100):
                self.assertEqual(name.read_bytes(), (self.root / f"out{size}" / name.name).read_bytes())

    def test_rows_uniques_states_and_duplicate_first_wins(self):
        self.fixture()
        totals = process_csv(self.source, self.root / "out", 2)
        self.assertEqual(totals, {"processed_rows": 10, "unique_carriers": 6,
                                 "duplicate_rows": 2, "missing_identifier_rows": 1,
                                 "invalid_identifier_rows": 1})
        states = self.report("state_counts.csv").set_index(["physical_country", "physical_state"])
        self.assertEqual(states.loc[("US", "NJ"), "unique_carriers"], 1)
        self.assertEqual(states.loc[("CA", "ON"), "row_count"], 2)
        self.assertEqual(states.loc[("CA", "ON"), "unique_carriers"], 1)
        self.assertEqual(states.loc[("CA", "CA"), "location_group"], "non_us")
        self.assertEqual(states.loc[("US", "XX"), "location_group"], "us_unknown_state")
        self.assertEqual(states["row_count"].sum(), 10)
        self.assertEqual(states["unique_carriers"].sum(), 6)
        stats = self.report("numeric_summary.csv").set_index("column")
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "sum"], 12)
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "valid_count"], 3)
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "mean"], 4)
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "zero_count"], 1)
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "missing_count"], 1)
        self.assertEqual(stats.loc["TOTAL_DRIVERS", "invalid_count"], 2)

    def test_missing_invalid_zero_and_fleet_bins(self):
        self.fixture()
        process_csv(self.source, self.root / "out", 3)
        quality = self.report("data_quality.csv").set_index("column")
        self.assertEqual(quality.loc["TOTAL_DRIVERS", "missing_count"], 1)
        self.assertEqual(quality.loc["TOTAL_DRIVERS", "invalid_count"], 2)
        self.assertEqual(quality.loc["MCS150_MILEAGE", "missing_count"], 2)
        self.assertEqual(quality.loc["MCS150_MILEAGE", "invalid_count"], 1)
        self.assertEqual(quality.loc["MCS150_MILEAGE_YEAR", "invalid_count"], 2)
        fleet = self.report("fleet_distribution.csv").set_index("power_units_bin")
        self.assertEqual(fleet["unique_carriers"].sum(), 6)
        self.assertEqual(fleet.loc["2-5", "unique_carriers"], 2)
        for key in ("0", "101+", "missing", "invalid"):
            self.assertEqual(fleet.loc[key, "unique_carriers"], 1)

    def test_optional_columns_absent_and_lowercase_header(self):
        self.write([["1", "PR"], ["2", "ON"]], ["dot_number", " phy_state "])
        process_csv(self.source, self.root / "out", 1)
        self.assertEqual(list(self.report("numeric_summary.csv")["available"]), [False] * 3)
        self.assertTrue((self.report("numeric_summary.csv")["sum"] == "").all())
        self.assertTrue((self.report("fleet_distribution.csv")["unique_carriers"] == "").all())
        self.assertEqual(set(self.report("state_counts.csv")["location_group"]), {"country_unknown"})
        metadata = json.loads((self.root / "out/run_metadata.json").read_text())
        self.assertEqual(metadata["analyzed_columns"], ["DOT_NUMBER", "PHY_STATE"])
        self.assertEqual(len(metadata["input_sha256"]), 64)

    def test_na_location_code_is_retained(self):
        self.write([["1", "NA", "NA", "NA", "0", "0", "2025"]])
        process_csv(self.source, self.root / "out", 1)
        state = self.report("state_counts.csv").iloc[0]
        self.assertEqual(state["physical_country"], "NA")
        self.assertEqual(state["physical_state"], "NA")
        self.assertEqual(state["location_group"], "non_us")
        quality = self.report("data_quality.csv").set_index("column")
        self.assertEqual(quality.loc["PHY_COUNTRY", "missing_count"], 0)
        self.assertEqual(quality.loc["TOTAL_DRIVERS", "missing_count"], 1)

    def test_numeric_range_no_rounding_or_integer_sum_overflow(self):
        self.write([[str(i), "NJ", "US", "000", "1.00", "999999999999999", "2025"] for i in range(1, 21)])
        process_csv(self.source, self.root / "out", 7)
        summary = self.report("numeric_summary.csv").set_index("column")
        self.assertEqual(summary.loc["MCS150_MILEAGE", "sum"], 19_999_999_999_999_980)
        self.assertEqual(summary.loc["TOTAL_DRIVERS", "zero_count"], 20)

    def test_large_sum_stays_exact_with_missing_other_metrics(self):
        self.write([[str(i), "NJ", "US", "", "", "999999999999999", "2025"]
                    for i in range(1, 10001)])
        process_csv(self.source, self.root / "out", 3333)
        with (self.root / "out/numeric_summary.csv").open(newline="") as handle:
            rows = {row["column"]: row for row in csv.DictReader(handle)}
        self.assertEqual(rows["MCS150_MILEAGE"]["sum"], "9999999999999990000")
        self.assertEqual(rows["TOTAL_DRIVERS"]["sum"], "")

    def test_multiline_fields_and_blank_lines(self):
        self.source.write_text('dot_number,phy_state,notes\n1,NJ,"two\nlines"\n\n2,ON,"ignored"\n')
        result = process_csv(self.source, self.root / "out", 1)
        self.assertEqual(result["processed_rows"], 2)
        self.assertEqual(result["unique_carriers"], 2)

    def test_empty_or_missing_required_columns_leave_no_reports(self):
        for content in ("", "DOT_NUMBER,PHY_STATE\n", "DOT_NUMBER,POWER_UNITS\n1,2\n"):
            with self.subTest(content=content):
                self.source.write_text(content)
                with self.assertRaises(ValueError):
                    process_csv(self.source, self.root / "out")
                self.assertFalse((self.root / "out").exists())
                self.assertEqual(list(self.root.glob(".mcmis-*")), [])

    def test_bad_chunk_sizes_and_missing_input(self):
        self.write([["1", "NJ"]], ["DOT_NUMBER", "PHY_STATE"])
        for size in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                process_csv(self.source, self.root / "out", size)
        with self.assertRaises(ValueError):
            process_csv(self.root / "absent.csv", self.root / "out")

    def test_existing_output_is_not_overwritten(self):
        self.fixture()
        output = self.root / "out"
        output.mkdir()
        marker = output / "important.txt"
        marker.write_text("keep")
        with self.assertRaises(ValueError):
            process_csv(self.source, output)
        self.assertEqual(marker.read_text(), "keep")

    def test_duplicate_headers_and_malformed_csv(self):
        for content in ('DOT_NUMBER,dot_number,PHY_STATE\n1,2,NJ\n',
                        'DOT_NUMBER,PHY_STATE\n1,"unterminated\n',
                        'DOT_NUMBER,PHY_STATE\n1,NJ,extra\n',
                        'DOT_NUMBER,PHY_STATE\n1\n'):
            with self.subTest(content=content):
                self.source.write_text(content)
                with self.assertRaises((ValueError, pd.errors.ParserError)):
                    process_csv(self.source, self.root / "out")
                self.assertFalse((self.root / "out").exists())

    def test_all_missing_and_invalid_numbers_do_not_report_zero_sum(self):
        self.write([["1", "NJ", "US", "", "bad", "NULL", ""],
                    ["2", "NJ", "US", "N/A", "1e3", "1000000000000000", ""]])
        process_csv(self.source, self.root / "out", 1)
        summary = self.report("numeric_summary.csv")
        self.assertTrue((summary["sum"] == "").all())
        self.assertTrue((summary["mean"] == "").all())

    def test_cli_success_and_error_exit_codes(self):
        self.fixture()
        command = [sys.executable, "-m", "analysis.mcmis_chunked", "--input", str(self.source),
                   "--output-dir", str(self.root / "out"), "--chunk-size", "2"]
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("10 rows; 6 unique carriers", result.stdout)
        result = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
