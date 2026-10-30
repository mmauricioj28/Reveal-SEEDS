"""Charts render from the EDA tables, including an empty extract."""
import csv
from pathlib import Path
import tempfile
import unittest

from analysis.build_safety_dataset import build_pipeline
from analysis.eda_trends import run as eda_run
from analysis.plot_trends import run as plot_run


def write(root, name, header, rows):
    path = root / name
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return path


class PlotTrendTests(unittest.TestCase):
    def test_figures_render_for_labeled_and_empty_extracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            census = write(root, 'c.csv',
                                 ['DOT_NUMBER', 'PHY_STATE', 'PHY_COUNTRY', 'POWER_UNITS', 'CARRIER_OPERATION'],
                                 [['1', 'NJ', 'US', '3', 'A']])
            crash = write(root, 'k.csv', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE', 'STATE'],
                          [['1', '1', '20160105', 'NJ'], ['2', '99', '20160201', 'TX'], ['3', '', '20160301', 'NJ']])
            inspection = write(root, 'i.csv', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'REPORT_STATE'],
                               [['1', '1', '20160108', 'NJ']])
            build_pipeline(census, crash, inspection, root / 'run', chunk_size=1)
            eda_run(root / 'run', root / 'eda')
            names = plot_run(root / 'eda', root / 'charts')
            for name in ('yearly_crash.png', 'yearly_inspection.png', 'monthly_crash.png', 'monthly_inspection.png',
                         'states_crash.png', 'states_inspection.png', 'fleet_size_crashes.png',
                         'carrier_operation_crashes.png'):
                self.assertIn(name, names)
                self.assertGreater((root / 'charts' / name).stat().st_size, 1000)
            empty_census = write(root, 'empty_c.csv', ['DOT_NUMBER', 'PHY_STATE'], [])
            empty_crash = write(root, 'empty_k.csv', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'], [])
            empty_inspection = write(root, 'empty_i.csv', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE'], [])
            build_pipeline(empty_census, empty_crash, empty_inspection, root / 'empty-run', chunk_size=1)
            eda_run(root / 'empty-run', root / 'empty-eda')
            empty_names = plot_run(root / 'empty-eda', root / 'empty-charts')
            self.assertIn('yearly_crash.png', empty_names)
            self.assertGreater((root / 'empty-charts' / 'yearly_crash.png').stat().st_size, 1000)


if __name__ == '__main__':
    unittest.main()
