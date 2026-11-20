"""Exercise the public exporter with small, synthetic integrated Parquet files."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pyarrow as pa
import pyarrow.parquet as pq

from dashboard.export import export


MONTHLY = "monthly_activity"
INTEGRATED = "carrier_safety_2016_2025"
SCHEMAS = {
    MONTHLY: [
        ("source", pa.string()), ("YEAR", pa.int64()), ("MONTH", pa.int64()),
        ("event_state", pa.string()), ("REPORT_STATE", pa.string()),
        ("match_status", pa.string()), ("record_count", pa.int64()),
    ],
    INTEGRATED: [
        ("DOT_NUMBER", pa.string()), ("YEAR", pa.int64()), ("census_matched", pa.int64()),
        ("POWER_UNITS", pa.int64()), ("CARRIER_OPERATION", pa.string()),
        ("TOTAL_CRASHES", pa.int64()), ("TOTAL_INSPECTIONS", pa.int64()),
    ],
}


class DashboardExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run_dir = self.root / "integrated"
        self.run_dir.mkdir()
        self.receipt_path = self.root / "receipt.json"
        self.output = self.root / "export"
        self.rows = {
            MONTHLY: [
                ("crash", 2024, 2, "NJ", "PA", "matched", 2),
                ("crash", 2024, 2, "NJ", "NY", "matched", 1),
                ("crash", 2024, 2, "NJ", "PA", "unmatched", 5),
                ("crash", 2024, 2, None, "PA", "unidentified", 4),
                ("crash", 2025, 4, "PA", "NJ", "matched", 7),
                ("inspection", 2025, 4, "NY", "NY", "matched", 1),
            ],
            INTEGRATED: [
                ("10", 2024, 1, 0, "A", 3, 0),
                ("10", 2025, 1, 0, "A", 7, 0),
                ("20", 2025, 1, None, "Q", 0, 1),
                ("30", 2024, 0, None, None, 5, 0),
            ],
        }
        inputs = {name: {"sha256": str(i) * 64}
                  for i, name in enumerate(("census", "crash", "inspection"), start=1)}
        self.metadata = {"period": [2024, 2025], "inputs": inputs}
        self.checks = {
            "checks_passed": True,
            "integrated_carrier_years": 4, "event_union_carrier_years": 4,
            "integrated_distinct_carriers": 3,
            "crash": self.source_counts(10, 5, 4),
            "inspection": self.source_counts(1, 0, 0),
        }
        self.receipt = {
            "checks_passed": True, "period_requested": [2024, 2025], "inputs": inputs,
            "reconciliation": self.checks,
            "coverage": {
                "crash": {"min": "2024-02-05", "max": "2025-04-03", "unobserved_month_count": 22},
                "inspection": {"min": "2025-04-17", "max": "2025-04-17", "unobserved_month_count": 23},
            },
        }
        self.write_sources()

    @staticmethod
    def source_counts(matched, unmatched, unidentified):
        return {"matched_records": matched, "unmatched_records": unmatched,
                "unidentified_records": unidentified, "monthly_records": matched + unmatched + unidentified,
                "integrated_records": matched + unmatched, "retained_linkable_records": matched + unmatched}

    def write_sources(self):
        for name, fields in SCHEMAS.items():
            schema = pa.schema(fields)
            table = pa.Table.from_pylist([dict(zip(schema.names, row)) for row in self.rows[name]], schema)
            pq.write_table(table, self.run_dir / f"{name}.parquet")
        for path, document in [(self.receipt_path, self.receipt),
                               (self.run_dir / "run_metadata.json", self.metadata),
                               (self.run_dir / "integration_validation.json", self.checks)]:
            path.write_text(json.dumps(document), encoding="utf-8")

    def generate(self):
        export(self.run_dir, self.receipt_path, self.output)
        return json.loads((self.output / "dashboard.json").read_text(encoding="utf-8"))

    def assert_rejected(self):
        with self.assertRaises(ValueError):
            self.generate()
        self.assertFalse(self.output.exists())

    def test_geography_periods_and_linkage(self):
        data = self.generate()
        self.assertEqual(data["version"], 1)
        snapshot = data["snapshot"]
        self.assertEqual(snapshot["period"], [2024, 2025])
        self.assertEqual(snapshot["coverage"]["inspection"]["min"], "2025-04-17")
        counts = {(r["source"], r["year"], r["month"], r["state"]):
                  (r["matched"], r["unmatched"], r["unidentified"]) for r in data["activity"]}
        self.assertEqual(counts, {
            ("crash", 2024, 2, "NJ"): (3, 5, 0), ("crash", 2024, 2, "Unknown"): (0, 0, 4),
            ("crash", 2025, 4, "PA"): (7, 0, 0), ("inspection", 2025, 4, "NY"): (1, 0, 0),
        })
        categories = {(r["year"], r["dimension"], r["category"]):
                      (r["carrier_years"], r["crash_records"], r["inspection_records"]) for r in data["carriers"]}
        self.assertEqual(categories, {
            (2024, "fleet", "0"): (1, 3, None), (2024, "operation", "A"): (1, 3, None),
            (2025, "fleet", "0"): (1, 7, 0), (2025, "operation", "A"): (1, 7, 0),
            (2025, "fleet", "Missing"): (1, 0, 1), (2025, "operation", "Q"): (1, 0, 1),
        })

    def test_cli_and_export_order(self):
        expected = self.generate()
        other = self.root / "repeat"
        subprocess.run([sys.executable, "-m", "dashboard.export", "--run-dir", str(self.run_dir),
                        "--receipt", str(self.receipt_path), "--output-dir", str(other)],
                       check=True, capture_output=True, text=True)
        for name in ("activity.csv", "carriers.csv", "calendar.csv", "dashboard.json"):
            content = (self.output / name).read_bytes()
            self.assertEqual(content, (other / name).read_bytes())
            self.assertNotIn(b"\r\n", content)
        for name in ("activity", "carriers"):
            with (other / f"{name}.csv").open(encoding="utf-8", newline="") as stream:
                self.assertEqual(list(csv.DictReader(stream)),
                                 [{k: "" if v is None else str(v) for k, v in row.items()}
                                  for row in expected[name]])
        with self.assertRaises(FileExistsError):
            self.generate()
        self.assertEqual(json.loads((self.output / "dashboard.json").read_text(encoding="utf-8")), expected)
        for rows in self.rows.values():
            rows.reverse()
        self.write_sources()
        self.output = self.root / "reordered"
        reordered = self.generate()
        self.assertNotEqual(expected["snapshot"]["id"], reordered["snapshot"]["id"])
        for name in ("activity.csv", "carriers.csv", "calendar.csv"):
            self.assertEqual((self.output / name).read_bytes(), (other / name).read_bytes())

    def test_calendar_distinguishes_unobserved_and_observed_zero(self):
        self.generate()
        with (self.output / "calendar.csv").open(encoding="utf-8", newline="") as stream:
            calendar = {(r["source"], r["year"], r["month"]): r for r in csv.DictReader(stream)}
        self.assertEqual(len(calendar), 48)
        gap = calendar["inspection", "2025", "3"]
        self.assertEqual((gap["coverage"], gap["matched"]), ("unobserved", ""))
        observed = calendar["inspection", "2025", "4"]
        self.assertEqual((observed["coverage"], observed["matched"], observed["unmatched"]),
                         ("partial boundary", "1", "0"))

    def test_snapshot_mismatch_and_failed_receipt(self):
        self.metadata["inputs"] = {**self.metadata["inputs"], "census": {"sha256": "f" * 64}}
        self.write_sources()
        self.assert_rejected()
        self.metadata["inputs"] = self.receipt["inputs"]
        self.receipt["checks_passed"] = False
        self.write_sources()
        self.assert_rejected()

    def test_inconsistent_coverage(self):
        self.receipt["coverage"]["inspection"]["unobserved_month_count"] -= 1
        self.write_sources()
        self.assert_rejected()

    def test_stale_linkage_counts(self):
        self.checks["crash"] = self.source_counts(10, 4, 5)
        self.write_sources()
        self.assert_rejected()

    def test_inspection_reporting_geography(self):
        self.rows[MONTHLY][-1] = ("inspection", 2025, 4, "CA", "NY", "matched", 1)
        self.write_sources()
        self.assert_rejected()

    def test_yearly_reconciliation_even_when_global_totals_match(self):
        rows = self.rows[INTEGRATED]
        rows[0] = (*rows[0][:-2], 4, 0)
        rows[1] = (*rows[1][:-2], 6, 0)
        self.write_sources()
        self.assert_rejected()

    def test_snapshot_characteristics_agree_across_event_years(self):
        self.rows[INTEGRATED][1] = ("10", 2025, 1, 2, "A", 7, 0)
        self.write_sources()
        self.assert_rejected()

    def test_invalid_source_values(self):
        for name, field, value in [
            (MONTHLY, "MONTH", 13), (MONTHLY, "YEAR", 2026),
            (MONTHLY, "match_status", "undetermined"), (MONTHLY, "record_count", -1),
            (INTEGRATED, "census_matched", 2), (INTEGRATED, "POWER_UNITS", -2),
            (INTEGRATED, "TOTAL_CRASHES", None), (INTEGRATED, "DOT_NUMBER", "invalid"),
        ]:
            with self.subTest(table=name, field=field):
                original = self.rows[name][0]
                row = list(original)
                row[pa.schema(SCHEMAS[name]).get_field_index(field)] = value
                self.rows[name][0] = row
                self.write_sources()
                self.assert_rejected()
                self.rows[name][0] = original

    def test_duplicate_grains(self):
        for name in SCHEMAS:
            with self.subTest(table=name):
                self.rows[name].append(self.rows[name][0])
                self.write_sources()
                self.assert_rejected()
                self.rows[name].pop()

    def test_missing_field_and_wrong_type(self):
        path = self.run_dir / f"{MONTHLY}.parquet"
        original = pq.read_table(path)
        for invalid in (original.drop(["match_status"]),
                        original.set_column(original.schema.get_field_index("record_count"), "record_count",
                                            original["record_count"].cast(pa.string()))):
            pq.write_table(invalid, path)
            self.assert_rejected()

    def test_no_observations(self):
        for rows in self.rows.values():
            rows.clear()
        self.checks.update(integrated_carrier_years=0, event_union_carrier_years=0,
                           integrated_distinct_carriers=0)
        for source in ("crash", "inspection"):
            self.checks[source] = self.source_counts(0, 0, 0)
            self.receipt["coverage"][source] = {"min": None, "max": None, "unobserved_month_count": 24}
        self.write_sources()
        data = self.generate()
        self.assertEqual(data["activity"], [])
        self.assertEqual(data["carriers"], [])
        self.assertIsNone(data["snapshot"]["coverage"]["inspection"]["min"])
