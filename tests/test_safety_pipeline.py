"""Controlled synthetic extracts exercise the actual pipeline, not a mock merge."""
import csv
import json
from pathlib import Path
import tempfile
import unittest
import hashlib
import importlib.util
import subprocess
import sys
from unittest.mock import patch

import pandas as pd

from analysis.build_safety_dataset import build_pipeline, canonicalize_dot
from analysis.data_quality import validate_integration


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

    def test_chunk_independence_across_duplicates_and_null_batches(self):
        with self.crash.open('a', newline='') as handle:
            csv.writer(handle).writerows([['001.0', '1', '20160101', '0', ''],
                                         ['2', '2', '20200101', '9', '9']])
        with patch('analysis.build_safety_dataset.pd.read_csv', wraps=pd.read_csv) as read:
            for size in (1, 2, 7, 100):
                self.run_pipeline(f'out{size}', size)
            for call in read.call_args_list:
                self.assertIn('usecols', call.kwargs)
                self.assertGreater(call.kwargs['chunksize'], 0)
        for path in (self.root / 'out1').iterdir():
            if path.name == 'run_metadata.json':
                continue
            for size in (2, 7, 100):
                self.assertEqual(path.read_bytes(), (self.root / f'out{size}' / path.name).read_bytes())
        self.assertEqual(self.quality('out1')['crash']['counts']['duplicate_rows'], 2)
        self.assertEqual(self.quality('out1')['crash']['counts']['conflicting_duplicate_rows'], 1)

    def test_invalid_identifiers_do_not_round_or_truncate(self):
        values = pd.Series(['001', '1.00', 2, 3.0, '', None, '0', '-1', '1.1', '1e2', 'bad',
                            '1000000000000000', '999999999999999'])
        self.assertEqual(list(canonicalize_dot(values)), ['1', '1', '2', '3', '999999999999999'])

    def test_missing_invalid_dot_retained_in_monthly_but_excluded_from_linkage(self):
        with self.crash.open('a', newline='') as handle:
            csv.writer(handle).writerows([['4', '', '20160101', '0', '0'], ['5', 'bad', '20160101', '', ''],
                                         ['6', '0', '20160101', '', ''], ['', '1', '20160101', '', '']])
        self.run_pipeline()
        report = self.quality()['crash']
        self.assertEqual(report['counts']['retained_unidentified'], 3)
        self.assertEqual(report['counts']['excluded_identifier'], 1)
        self.assertEqual(report['variables']['DOT_NUMBER']['missing'], 1)
        self.assertEqual(report['variables']['DOT_NUMBER']['invalid'], 2)
        self.assertEqual(sum(int(r['record_count']) for r in self.read('monthly_activity') if r['source'] == 'crash'), 6)
        self.assertEqual(sum(int(r['TOTAL_CRASHES']) for r in self.read('carrier_safety_2016_2025')), 3)

    def test_date_window_and_invalid_calendar_dates(self):
        self.crash = self.write('dates', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'],
                                [[str(i), '1', date] for i, date in enumerate(
                                    ['20151231', '20160101', '20251231', '20260101', '', '20250230',
                                     '01/02/2020', '2020-02-29', '20200101 1200'], 1)])
        self.run_pipeline()
        report = self.quality()['crash']
        self.assertEqual(report['counts']['retained_rows'], 3)
        self.assertEqual(report['counts']['excluded_window'], 2)
        self.assertEqual(report['counts']['excluded_date'], 4)
        self.assertEqual(report['parsed_date_coverage'], {'min': '2015-12-31', 'max': '2026-01-01'})
        self.assertEqual(report['retained_date_coverage'], {'min': '2016-01-01', 'max': '2025-12-31'})
        self.assertEqual(len(report['unobserved_months']), 117)

    def test_inspection_window_and_duplicate_status(self):
        self.inspection = self.write('inspection_status', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'CI_STATUS_CODE'],
                                     [['1', '1', '20151231', 'C'], ['2', '1', '20260101', 'C'],
                                      ['3', '1', '20250101', 'D'], ['3', '1', '20250101', 'C'],
                                      ['4', '1', 'bad', 'C'], ['5', '2', '20250101', 'X']])
        self.run_pipeline()
        report = self.quality()['inspection']
        self.assertEqual(report['counts']['excluded_window'], 2)
        self.assertEqual(report['counts']['excluded_status'], 1)
        self.assertEqual(report['counts']['excluded_date'], 1)
        self.assertEqual(report['counts']['retained_rows'], 2)

    def test_duplicate_census_first_wins_and_conflicts_reported(self):
        with self.census.open('a', newline='') as handle:
            csv.writer(handle).writerows([['1.00', 'NY', 'US', '100', '100'], ['', 'NJ', 'US', '', ''],
                                         ['bad', 'NJ', 'US', '', '']])
        self.run_pipeline(size=1)
        rows = self.read('carriers')
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]['PHY_STATE'], 'NJ')
        self.assertEqual(rows[0]['POWER_UNITS'], '0')
        counts = self.quality()['census']['counts']
        self.assertEqual((counts['duplicate_rows'], counts['conflicting_duplicate_rows'], counts['excluded_identifier']), (1, 1, 2))

    def test_measurements_preserve_missing_invalid_and_zero(self):
        self.inspection = self.write('measurements', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE', 'DRIVER_OOS_TOTAL'],
                                     [['1', '1', '20200101', ''], ['2', '1', '20200102', '0'],
                                      ['3', '1', '20200103', '-1'], ['4', '1', '20200104', '2'],
                                      ['5', '2', '20200101', 'N/A']])
        self.run_pipeline()
        rows = {r['DOT_NUMBER']: r for r in self.read('inspection_carrier_year')}
        self.assertEqual((rows['1']['TOTAL_DRIVER_OOS'], rows['1']['TOTAL_DRIVER_OOS_observed']), ('2', '2'))
        self.assertEqual((rows['2']['TOTAL_DRIVER_OOS'], rows['2']['TOTAL_DRIVER_OOS_observed']), ('', '0'))
        field = self.quality()['inspection']['variables']['DRIVER_OOS_TOTAL']
        self.assertEqual((field['missing'], field['invalid'], field['zero'], field['missing_fraction']), (2, 1, 1, .4))

    def test_country_state_semantics_and_unknown_domains(self):
        self.census = self.write('geo', ['DOT_NUMBER', 'PHY_STATE', 'PHY_COUNTRY', 'SAFETY_RATING', 'STATUS_CODE'],
                                 [['1', 'ca', 'ca', '', 'A'], ['2', 'CA', 'US', 'S', 'I'],
                                  ['3', 'PR', 'US', 'C', 'P'], ['4', 'XX', 'US', 'U', '?'],
                                  ['5', 'NA', 'NA', 'X', 'A'], ['6', '???', '', '', '']])
        self.run_pipeline()
        rows = {r['DOT_NUMBER']: r for r in self.read('carriers')}
        self.assertEqual([rows[str(i)]['LOCATION_GROUP'] for i in range(1, 7)],
                         ['non_us', 'us_state_or_dc', 'us_territory', 'us_unknown_state', 'non_us', 'country_unknown'])
        self.assertEqual(rows['6']['PHY_STATE'], 'invalid')
        self.assertEqual(rows['5']['PHY_COUNTRY'], 'NA')
        self.assertEqual(self.quality()['census']['variables']['SAFETY_RATING']['invalid'], 1)

    def test_lowercase_headers_and_missing_country(self):
        self.census = self.write('lower', [' dot_number ', 'phy_state'], [['1', 'CA']])
        self.run_pipeline()
        self.assertEqual(self.read('carriers')[0]['LOCATION_GROUP'], 'country_unknown')

    def test_header_only_extracts_produce_valid_empty_tables(self):
        self.census = self.write('empty_census', ['DOT_NUMBER', 'PHY_STATE'], [])
        self.crash = self.write('empty_crash', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'], [])
        self.inspection = self.write('empty_inspection', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE'], [])
        self.run_pipeline()
        self.assertEqual(self.read('carrier_safety_2016_2025'), [])
        self.assertEqual(self.read('carriers'), [])
        self.assertIsNone(self.quality()['crash']['variables']['DOT_NUMBER']['missing_fraction'])

    def test_empty_or_bad_schema_and_malformed_rows_publish_nothing(self):
        for content in ('', 'DOT_NUMBER,REPORT_DATE\n1,20200101\n',
                        'CRASH_ID,DOT_NUMBER,dot_number,REPORT_DATE\n1,1,1,20200101\n',
                        'CRASH_ID,DOT_NUMBER,REPORT_DATE,unused\n1,1,20200101\n',
                        'CRASH_ID,DOT_NUMBER,REPORT_DATE\n1,1,"broken\n'):
            with self.subTest(content=content):
                self.crash.write_text(content)
                with self.assertRaises((ValueError, csv.Error)):
                    self.run_pipeline()
                self.assertFalse((self.root / 'out').exists())
                self.assertEqual(list(self.root.glob('.fmcsa-*')), [])

    def test_output_protection_and_input_immutability(self):
        hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (self.census, self.crash, self.inspection)}
        self.run_pipeline()
        for path, digest in hashes.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        marker = self.root / 'out' / 'keep.txt'
        marker.write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.run_pipeline()
        self.assertEqual(marker.read_text(), 'keep')

    def test_input_change_aborts_publication(self):
        from analysis.build_safety_dataset import integrate
        def change_input(database):
            integrate(database)
            with self.census.open('a') as handle:
                handle.write('4,NJ,US,1,1\n')
        with patch('analysis.build_safety_dataset.integrate', side_effect=change_input):
            with self.assertRaisesRegex(ValueError, 'Input changed'):
                self.run_pipeline()
        self.assertFalse((self.root / 'out').exists())

    def test_bad_chunk_sizes_and_missing_inputs(self):
        for size in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.run_pipeline(size=size)
        self.crash.unlink()
        with self.assertRaises(OSError):
            self.run_pipeline()

    def test_reconciliation_includes_unmatched_carriers_and_census_only(self):
        self.run_pipeline()
        report = json.loads((self.root / 'out/integration_validation.json').read_text())
        self.assertTrue(report['checks_passed'])
        self.assertEqual(report['census_carriers'], 3)
        self.assertEqual(report['census_carriers_without_events'], 1)
        self.assertEqual(report['crash']['matched_records'], 2)
        self.assertEqual(report['crash']['unmatched_records'], 1)
        self.assertEqual(report['inspection']['integrated_records'], 3)

    def test_count_inflation_is_rejected(self):
        original = validate_integration
        def corrupt(database, quality, metrics):
            database.execute('UPDATE integrated SET TOTAL_CRASHES=TOTAL_CRASHES+1')
            return original(database, quality, metrics)
        with patch('analysis.build_safety_dataset.validate_integration', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'crash event totals'):
                self.run_pipeline()
        self.assertFalse((self.root / 'out').exists())

    def test_measurement_inflation_is_rejected(self):
        original = validate_integration
        def corrupt(database, quality, metrics):
            database.execute('UPDATE integrated SET TOTAL_FATALITIES=999 WHERE TOTAL_CRASHES>0')
            return original(database, quality, metrics)
        with patch('analysis.build_safety_dataset.validate_integration', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'FATALITIES measurement totals'):
                self.run_pipeline()
        self.assertFalse((self.root / 'out').exists())

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'optional pyarrow is not installed')
    def test_parquet_matches_csv_with_null_first_batch_and_empty_events(self):
        import pyarrow.parquet as pq
        self.run_pipeline('parquet', size=1, parquet=True)
        for name in ('carriers', 'crash_carrier_year', 'inspection_carrier_year', 'carrier_safety_2016_2025', 'monthly_activity'):
            table = pq.read_table(self.root / 'parquet' / (name + '.parquet'))
            self.assertEqual(table.num_rows, len(self.read(name, 'parquet')))
            self.assertEqual(table.column_names, list(self.read(name, 'parquet')[0]))
        table = pq.read_table(self.root / 'parquet/carriers.parquet').to_pylist()
        self.assertIsNone(table[0]['TOTAL_DRIVERS'])
        self.assertEqual(table[2]['TOTAL_DRIVERS'], 0)
        self.crash = self.write('empty_crash', ['CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'], [])
        self.inspection = self.write('empty_inspection', ['INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE'], [])
        self.run_pipeline('empty_parquet', size=1, parquet=True)
        table = pq.read_table(self.root / 'empty_parquet/carrier_safety_2016_2025.parquet')
        self.assertEqual(table.num_rows, 0)
        self.assertEqual(str(table.schema.field('DOT_NUMBER').type), 'string')

    def test_cli_success_and_failure(self):
        command = [sys.executable, '-m', 'analysis.build_safety_dataset', '--census', str(self.census),
                   '--crashes', str(self.crash), '--inspections', str(self.inspection),
                   '--output-dir', str(self.root / 'out'), '--chunk-size', '1']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Analytical output', result.stdout)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('already exists', result.stderr)


if __name__ == '__main__':
    unittest.main()
