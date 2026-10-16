"""Controlled synthetic extracts exercise the actual pipeline, not a mock merge."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analysis.build_safety_dataset import build_pipeline


class SafetyPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.census = self.write('census', ['DOT_NUMBER', 'PHY_STATE', 'PHY_COUNTRY', 'POWER_UNITS', 'TOTAL_DRIVERS'],
                                 [['001', ' nj ', 'us', '0', ''], ['2', 'ON', 'CA', '5', '2'],
                                  ['3', 'CA', 'US', '', '0']])
        self.crash = self.write('crash', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE', 'FATALITIES', 'INJURIES'],
                                [['1', '1.0', '20160101', '0', ''], ['2', '001', '2016-12-31', '', '2'],
                                 ['3', '99', '20251231', '1', '0']])
        self.inspection = self.write('inspection', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'VEHICLE_OOS_TOTAL', 'DRIVER_OOS_TOTAL'],
                                     [['1', '1', '20160102', '0', ''], ['2', '1.00', '20160103', '2', ''],
                                      ['3', '2', '20250101', '', '0']])

    def write(self, name, header, rows):
        path = self.root / (name + '.csv')
        with path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def run_pipeline(self, name='out', size=2, parquet=False):
        return build_pipeline(self.census, self.crash, self.inspection, self.root / name, size, parquet)

    def read(self, file, run='out'):
        with (self.root / run / (file + '.csv')).open(newline='', encoding='utf-8') as handle:
            return list(csv.DictReader(handle))

    def quality(self, run='out'):
        return json.loads((self.root / run / 'quality.json').read_text())

    def test_multiple_events_aggregate_before_join_and_keep_unmatched(self):
        self.run_pipeline()
        rows = {(r['DOT_NUMBER'], r['YEAR']): r for r in self.read('carrier_safety_2016_2025')}
        self.assertEqual(len(rows), 3)
        row = rows['1', '2016']
        self.assertEqual((row['TOTAL_CRASHES'], row['TOTAL_INSPECTIONS']), ('2', '2'))
        self.assertEqual((row['TOTAL_FATALITIES'], row['TOTAL_FATALITIES_observed']), ('0', '1'))
        self.assertEqual((row['TOTAL_DRIVER_OOS'], row['TOTAL_DRIVER_OOS_observed']), ('', '0'))
        self.assertEqual(row['TOTAL_VEHICLE_OOS'], '2')
        self.assertEqual(rows['99', '2025']['census_matched'], '0')
        self.assertEqual(len(self.read('carriers')), 3)
        self.assertNotIn(('3', '2016'), rows)

    def test_optional_columns_and_zero_driver_values_remain_distinct(self):
        self.run_pipeline()
        carriers = {r['DOT_NUMBER']: r for r in self.read('carriers')}
        self.assertEqual(carriers['1']['TOTAL_DRIVERS'], '')
        self.assertEqual(carriers['3']['TOTAL_DRIVERS'], '0')
        self.assertEqual(carriers['2']['LOCATION_GROUP'], 'non_us')
        self.assertIn('VIOL_TOTAL', self.quality()['inspection']['metadata']['unavailable_columns'])


if __name__ == '__main__':
    unittest.main()
