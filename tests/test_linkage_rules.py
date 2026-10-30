"""Hand-counted matched, unmatched, and unidentified records."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from analysis.build_safety_dataset import build_pipeline
from analysis.eda_trends import run


class LinkageRuleTests(unittest.TestCase):
    def write(self, root, name, header, rows):
        path = root / name
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def test_status_totals_match_a_hand_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            census = self.write(root, 'c.csv',
                                ['DOT_NUMBER', 'PHY_STATE', 'PHY_COUNTRY', 'POWER_UNITS', 'TOTAL_DRIVERS', 'CARRIER_OPERATION'],
                                [['1', 'NJ', 'US', '3', '2', 'A'], ['2', 'TX', 'US', '50', '', 'B'],
                                 ['3', 'CA', 'US', '0', '0', 'C']])
            crash = self.write(root, 'k.csv',
                               ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE', 'STATE', 'REPORT_STATE'],
                               [['1', '1', '20160105', 'NJ', 'NJ'], ['2', '1', '20160120', 'NJ', 'NJ'],
                                ['3', '99', '20160106', 'NJ', 'NJ'], ['4', '', '20160107', 'NJ', 'NJ'],
                                ['5', 'bad', '20160201', 'TX', 'TX'], ['6', '2', '20151231', 'TX', 'TX'],
                                ['7', '0', '20160301', 'NJ', 'NJ']])
            inspection = self.write(root, 'i.csv',
                                    ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'REPORT_STATE'],
                                    [['1', '2', '20160301', 'TX'], ['2', '', '20160302', 'TX'],
                                     ['3', '99', '20160304', 'TX']])
            build_pipeline(census, crash, inspection, root / 'run', chunk_size=2)
            report = json.loads((root / 'run' / 'integration_validation.json').read_text(encoding='utf-8'))
            self.assertEqual((report['crash']['matched_records'], report['crash']['unmatched_records'],
                              report['crash']['unidentified_records']), (2, 1, 3))
            link = report['crash']['unmatched_of_linkable']
            self.assertEqual((link['numerator'], link['denominator']), (1, 3))
            self.assertNotIn('1.4', json.dumps(link))
            with (root / 'run' / 'monthly_activity.csv').open(encoding='utf-8') as handle:
                monthly = list(csv.DictReader(handle))
            crash_rows = [row for row in monthly if row['source'] == 'crash']
            self.assertEqual(sum(int(row['record_count']) for row in crash_rows), 6)
            counts = {}
            for row in crash_rows:
                counts[row['match_status']] = counts.get(row['match_status'], 0) + int(row['record_count'])
            self.assertEqual(counts, {'matched': 2, 'unmatched': 1, 'unidentified': 3})

            outputs = run(root / 'run', root / 'eda')
            excluded = outputs['excluded_record_counts'].set_index('source').loc['crash']
            self.assertEqual((excluded.all_retained_records, excluded.used_in_comparisons_matched,
                              excluded.excluded_unmatched, excluded.excluded_unidentified), (6, 2, 1, 3))
            self.assertEqual(excluded.pct_unmatched_of_linkable, 33.33)
            self.assertEqual(excluded.unmatched_denominator.startswith('usable DOT'), True)
            self.assertEqual(int(outputs['by_fleet_size_matched_only']['crash_records'].sum()), 2)
            self.assertNotIn('0', set(outputs['by_fleet_size_matched_only']['fleet_bin'].astype(str)))
            self.assertIn('missing', set(outputs['by_driver_count_matched_only']['driver_bin'].astype(str)))
            pattern = outputs['monthly_pattern']
            observed = set(zip(pattern.loc[pattern['source'] == 'crash', 'YEAR'].astype(int),
                               pattern.loc[pattern['source'] == 'crash', 'MONTH'].astype(int)))
            self.assertNotIn((2016, 4), observed)
            april = outputs['unobserved_months']
            april = april[(april['source'] == 'crash') & (april['YEAR'] == 2016) & (april['MONTH'] == 4)]
            self.assertEqual(april.iloc[0]['coverage'], 'unobserved_not_zero')
            year = outputs['yearly_activity']
            year = year[(year['source'] == 'crash') & (year['YEAR'] == 2016)].iloc[0]
            self.assertEqual(int(year.all_retained_records),
                             int(year.matched_records) + int(year.unmatched_records) + int(year.unidentified_records))
            states = outputs['state_year_activity']
            nj = states[(states['source'] == 'crash') & (states['event_state'] == 'NJ') & (states['YEAR'] == 2016)]
            self.assertEqual(int(nj['matched_records'].sum()), 2)
            self.assertIn('not carrier headquarters', states.loc[states['source'] == 'crash', 'geography'].iloc[0])
            self.assertIn('uploading jurisdiction', states.loc[states['source'] == 'inspection', 'geography'].iloc[0])

    def test_empty_extract_does_not_invent_zero_months(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            census = self.write(root, 'c.csv', ['DOT_NUMBER', 'PHY_STATE'], [])
            crash = self.write(root, 'k.csv', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'], [])
            inspection = self.write(root, 'i.csv', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE'], [])
            build_pipeline(census, crash, inspection, root / 'run', chunk_size=1)
            report = json.loads((root / 'run' / 'integration_validation.json').read_text(encoding='utf-8'))
            self.assertEqual(report['crash']['unmatched_of_linkable']['denominator'], 0)
            self.assertIsNone(report['crash']['unmatched_of_linkable']['percent'])
            outputs = run(root / 'run', root / 'eda')
            self.assertEqual(int(outputs['excluded_record_counts']['all_retained_records'].sum()), 0)
            self.assertEqual(len(outputs['monthly_pattern']), 0)
            self.assertEqual(len(outputs['unobserved_months']), 240)
            self.assertTrue((outputs['unobserved_months']['coverage'] == 'unobserved_not_zero').all())


if __name__ == '__main__':
    unittest.main()
