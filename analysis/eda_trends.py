"""Exploratory yearly/monthly trends and carrier-characteristic comparisons.

Reads a finished run of ``analysis.build_safety_dataset`` and applies guidance of Oct 26:

* Counts by year / month / state INCLUDE every retained record, flagged as matched,
  unmatched (usable DOT but not in the Census) or unidentified (no usable DOT).
* Comparisons by carrier characteristics use matched records only, and the number of
  excluded records is written next to the results.
* Census characteristics are a snapshot. Outputs describe observed records, not risk.

Run from the repository root (new output directory each time):
    python -m analysis.eda_trends --run-dir outputs/safety_run_01 --output-dir outputs/eda_01
"""
import argparse
import calendar
from pathlib import Path

import pandas as pd

FLEET_BINS = [(0, 0, '0'), (1, 1, '1'), (2, 5, '2-5'), (6, 20, '6-20'), (21, 100, '21-100'), (101, None, '101+')]
SOURCES = {'crash': 'TOTAL_CRASHES', 'inspection': 'TOTAL_INSPECTIONS'}


def read_table(run_dir, stem):
    """Read <stem>.parquet if present, else <stem>.csv (DOT_NUMBER always as string)."""
    parquet, csv = run_dir / f'{stem}.parquet', run_dir / f'{stem}.csv'
    if parquet.is_file():
        return pd.read_parquet(parquet)
    if csv.is_file():
        return pd.read_csv(csv, dtype={'DOT_NUMBER': 'string'}, keep_default_na=False, na_values=[''])
    raise FileNotFoundError(f'Neither {parquet.name} nor {csv.name} found in {run_dir}')


def fleet_bin(power_units):
    """Bin POWER_UNITS; missing stays 'missing' (never assumed zero)."""
    labels = pd.Series('missing', index=power_units.index, dtype='object')
    values = pd.to_numeric(power_units, errors='coerce')
    for low, high, label in FLEET_BINS:
        mask = values >= low if high is None else values.between(low, high)
        labels[mask.fillna(False)] = label
    return labels


def record_status(integrated):
    """Per source and year: linkable records split into matched / unmatched."""
    parts = []
    for source, column in SOURCES.items():
        grouped = integrated.groupby(['YEAR', 'census_matched'])[column].sum().unstack(fill_value=0)
        frame = pd.DataFrame({'source': source, 'YEAR': grouped.index,
                              'matched_records': grouped.get(1, 0).values,
                              'unmatched_records': grouped.get(0, 0).values})
        parts.append(frame)
    return pd.concat(parts, ignore_index=True)


def yearly_activity(monthly, integrated):
    totals = monthly.groupby(['source', 'YEAR'], as_index=False)['record_count'].sum()
    totals = totals.rename(columns={'record_count': 'all_retained_records'})
    result = totals.merge(record_status(integrated), on=['source', 'YEAR'], how='left').fillna(0)
    result['unidentified_records'] = (result['all_retained_records'] - result['matched_records']
                                      - result['unmatched_records'])
    result['pct_unidentified'] = (100 * result['unidentified_records'] / result['all_retained_records']).round(2)
    result['pct_unmatched_of_linkable'] = (100 * result['unmatched_records']
                                           / (result['matched_records'] + result['unmatched_records'])).round(2)
    result['yoy_change_pct'] = (result.sort_values('YEAR').groupby('source')['all_retained_records']
                                .pct_change() * 100).round(2)
    return result.sort_values(['source', 'YEAR'])


def monthly_pattern(monthly):
    """Month totals, share of each year, records per calendar day (not per vehicle mile)."""
    table = monthly.groupby(['source', 'YEAR', 'MONTH'], as_index=False)['record_count'].sum()
    table['days_in_month'] = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(table['YEAR'], table['MONTH'])]
    table['records_per_day'] = (table['record_count'] / table['days_in_month']).round(2)
    table['share_of_year_pct'] = (100 * table['record_count']
                                  / table.groupby(['source', 'YEAR'])['record_count'].transform('sum')).round(2)
    return table


def state_year(monthly):
    return (monthly.groupby(['source', 'event_state', 'YEAR'], as_index=False)['record_count'].sum()
            .sort_values(['source', 'event_state', 'YEAR']))


def characteristic_comparison(integrated, column, label):
    """Matched carrier-years only. One row per characteristic level; excluded counts reported separately."""
    matched = integrated[integrated['census_matched'] == 1].copy()
    matched[label] = matched[column] if column != 'POWER_UNITS' else fleet_bin(matched['POWER_UNITS'])
    matched[label] = matched[label].fillna('missing').astype(str)
    summary = matched.groupby(label).agg(
        carrier_years=('DOT_NUMBER', 'size'), carriers=('DOT_NUMBER', 'nunique'),
        crash_records=('TOTAL_CRASHES', 'sum'), inspection_records=('TOTAL_INSPECTIONS', 'sum'),
        median_crashes_per_carrier_year=('TOTAL_CRASHES', 'median'),
        median_inspections_per_carrier_year=('TOTAL_INSPECTIONS', 'median')).reset_index()
    return summary


def excluded_counts(monthly, integrated):
    rows = []
    for source, column in SOURCES.items():
        total = int(monthly.loc[monthly['source'] == source, 'record_count'].sum())
        unmatched = int(integrated.loc[integrated['census_matched'] == 0, column].sum())
        matched = int(integrated.loc[integrated['census_matched'] == 1, column].sum())
        rows.append({'source': source, 'all_retained_records': total, 'used_in_comparisons_matched': matched,
                     'excluded_unmatched': unmatched, 'excluded_unidentified': total - matched - unmatched,
                     'pct_excluded': round(100 * (total - matched) / total, 2) if total else None})
    return pd.DataFrame(rows)


def run(run_dir, output_dir):
    run_dir, destination = Path(run_dir), Path(output_dir)
    if destination.exists():
        raise ValueError('Output directory already exists; choose a new directory')
    integrated = read_table(run_dir, 'carrier_safety_2016_2025')
    monthly = read_table(run_dir, 'monthly_activity')
    for frame in (integrated, monthly):
        frame['YEAR'] = pd.to_numeric(frame['YEAR'])
    monthly['MONTH'] = pd.to_numeric(monthly['MONTH'])
    monthly['record_count'] = pd.to_numeric(monthly['record_count'])
    for column in ('census_matched', *SOURCES.values()):
        integrated[column] = pd.to_numeric(integrated[column])

    outputs = {
        'excluded_record_counts': excluded_counts(monthly, integrated),
        'yearly_activity': yearly_activity(monthly, integrated),
        'monthly_pattern': monthly_pattern(monthly),
        'state_year_activity': state_year(monthly),
        'by_fleet_size_matched_only': characteristic_comparison(integrated, 'POWER_UNITS', 'fleet_bin'),
    }
    if 'CARRIER_OPERATION' in integrated:
        outputs['by_carrier_operation_matched_only'] = characteristic_comparison(
            integrated, 'CARRIER_OPERATION', 'carrier_operation')
    destination.mkdir(parents=True)
    for name, frame in outputs.items():
        frame.to_csv(destination / f'{name}.csv', index=False)
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--run-dir', required=True, help='output directory of analysis.build_safety_dataset')
    parser.add_argument('--output-dir', required=True, help='new directory for EDA tables')
    args = parser.parse_args()
    outputs = run(args.run_dir, args.output_dir)
    print(outputs['excluded_record_counts'].to_string(index=False))
    print(f"Wrote {len(outputs)} tables to {args.output_dir}")


if __name__ == '__main__':
    main()
