"""eda_trends must reconcile matched + unmatched + unidentified to the retained total."""
import csv
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from analysis.build_safety_dataset import build_pipeline
from analysis.eda_trends import run


class EdaTrendsTests(unittest.TestCase):
    def test_counts_reconcile_and_unmatched_excluded_from_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def write(name, header, rows):
                with (root / name).open('w', newline='') as handle:
                    writer = csv.writer(handle)
                    writer.writerow(header)
                    writer.writerows(rows)
                return root / name

            census = write('c.csv', ['DOT_NUMBER', 'PHY_STATE', 'PHY_COUNTRY', 'POWER_UNITS'],
                           [['1', 'NJ', 'US', '3'], ['2', 'TX', 'US', '50']])
            crash = write('k.csv', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE', 'STATE', 'REPORT_STATE'],
                          [['1', '1', '20160105', 'NJ', 'NJ'], ['2', '99', '20160106', 'NJ', 'NJ'],
                           ['3', '', '20160107', 'NJ', 'NJ']])
            inspection = write('i.csv', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'REPORT_STATE'],
                               [['1', '2', '20160108', 'TX']])
            build_pipeline(census, crash, inspection, root / 'run', chunk_size=2)
            outputs = run(root / 'run', root / 'eda')
            excluded = outputs['excluded_record_counts'].set_index('source').loc['crash']
            self.assertEqual(
                (excluded.all_retained_records, excluded.used_in_comparisons_matched,
                 excluded.excluded_unmatched, excluded.excluded_unidentified), (3, 1, 1, 1))
            self.assertEqual(int(outputs['by_fleet_size_matched_only']['crash_records'].sum()), 1)
            with self.assertRaises(ValueError):
                run(root / 'run', root / 'eda')


if __name__ == '__main__':
    unittest.main()
