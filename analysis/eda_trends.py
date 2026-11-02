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
STATUS = ('matched', 'unmatched', 'unidentified')
GEOGRAPHY = {
    'crash': 'crash file STATE: reported crash location, not carrier headquarters',
    'inspection': 'inspection REPORT_STATE: uploading jurisdiction, not carrier headquarters',
}


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


def status_counts(monthly, keys):
    """Sum records by match_status. Missing statuses in an observed group are zero; missing months are omitted."""
    if 'match_status' not in monthly.columns:
        raise ValueError('monthly_activity has no match_status; rerun analysis.build_safety_dataset')
    columns = [*keys, *(f'{name}_records' for name in STATUS), 'all_retained_records',
               'pct_unmatched_of_linkable', 'pct_unidentified_of_retained']
    if monthly.empty:
        return pd.DataFrame(columns=columns)
    frame = monthly.copy()
    if 'event_state' in frame.columns:
        frame['event_state'] = frame['event_state'].replace('', 'unavailable').fillna('unavailable')
    grouped = frame.groupby(keys + ['match_status'], as_index=False)['record_count'].sum()
    wide = grouped.pivot_table(index=keys, columns='match_status', values='record_count', fill_value=0).reset_index()
    for name in STATUS:
        if name not in wide.columns:
            wide[name] = 0
    wide = wide.rename(columns={name: f'{name}_records' for name in STATUS})
    wide['all_retained_records'] = wide[[f'{name}_records' for name in STATUS]].sum(axis=1)
    linkable = wide['matched_records'] + wide['unmatched_records']
    percent = (100 * wide['unmatched_records'] / linkable).round(2)
    wide['pct_unmatched_of_linkable'] = percent.where(linkable > 0)
    wide['pct_unidentified_of_retained'] = (100 * wide['unidentified_records'] / wide['all_retained_records']).round(2)
    return wide[columns]


def yearly_activity(monthly):
    result = status_counts(monthly, ['source', 'YEAR']).sort_values(['source', 'YEAR'])
    if result.empty:
        result['yoy_change_pct'] = []
        return result
    previous = result.groupby('source')['all_retained_records'].shift()
    previous_year = result.groupby('source')['YEAR'].shift()
    change = (result['all_retained_records'] - previous) / previous * 100
    result['yoy_change_pct'] = change.where((previous_year + 1 == result['YEAR']) & (previous > 0)).round(2)
    return result


def monthly_pattern(monthly):
    """Observed months only. records_per_day is a calendar-day count, not an exposure rate."""
    table = status_counts(monthly, ['source', 'YEAR', 'MONTH'])
    if table.empty:
        return table.assign(days_in_month=[], records_per_day=[], share_of_year_pct=[])
    table['days_in_month'] = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(table['YEAR'], table['MONTH'])]
    table['records_per_day'] = (table['all_retained_records'] / table['days_in_month']).round(2)
    table['share_of_year_pct'] = (100 * table['all_retained_records']
                                  / table.groupby(['source', 'YEAR'])['all_retained_records'].transform('sum')).round(2)
    return table.sort_values(['source', 'YEAR', 'MONTH'])


def month_of_year(pattern):
    """Average observed years only. Unobserved months are left out, not filled with zero."""
    columns = ['source', 'MONTH', 'years_observed', 'mean_records_per_day', 'note']
    note = ('Mean of records per calendar day across years that contain this month. '
            'Not an exposure rate. Unobserved months are omitted.')
    if pattern.empty:
        return pd.DataFrame(columns=columns)
    grouped = pattern.groupby(['source', 'MONTH'], as_index=False).agg(
        years_observed=('YEAR', 'nunique'), mean_records_per_day=('records_per_day', 'mean'))
    grouped['mean_records_per_day'] = grouped['mean_records_per_day'].round(2)
    grouped['note'] = note
    return grouped[columns].sort_values(['source', 'MONTH'])


def unobserved_months(monthly):
    """Months absent from the extract. They are not coded as zero events."""
    present = set()
    if len(monthly):
        present = set(zip(monthly['source'].astype(str), monthly['YEAR'].astype(int), monthly['MONTH'].astype(int)))
    rows = [{'source': source, 'YEAR': year, 'MONTH': month, 'coverage': 'unobserved_not_zero'}
            for source in ('crash', 'inspection') for year in range(2016, 2026) for month in range(1, 13)
            if (source, year, month) not in present]
    return pd.DataFrame(rows, columns=['source', 'YEAR', 'MONTH', 'coverage'])


def state_year(monthly):
    table = status_counts(monthly, ['source', 'event_state', 'YEAR'])
    if table.empty:
        return table.assign(geography=[])
    table['geography'] = table['source'].map(GEOGRAPHY)
    return table.sort_values(['source', 'event_state', 'YEAR'])


def characteristic_comparison(integrated, column, label):
    """Matched carrier-years only. One row per characteristic level; excluded counts reported separately."""
    matched = integrated[integrated['census_matched'] == 1].copy()
    if column in ('POWER_UNITS', 'TOTAL_DRIVERS'):
        matched[label] = fleet_bin(matched[column])
    else:
        matched[label] = matched[column]
    matched[label] = matched[label].fillna('missing').astype(str).replace('', 'missing')
    summary = matched.groupby(label, dropna=False).agg(
        carrier_years=('DOT_NUMBER', 'size'), carriers=('DOT_NUMBER', 'nunique'),
        crash_records=('TOTAL_CRASHES', 'sum'), inspection_records=('TOTAL_INSPECTIONS', 'sum'),
        median_crashes_per_carrier_year=('TOTAL_CRASHES', 'median'),
        median_inspections_per_carrier_year=('TOTAL_INSPECTIONS', 'median')).reset_index()
    return summary


def excluded_counts(monthly):
    totals = status_counts(monthly, ['source'])
    rows = []
    for source in ('crash', 'inspection'):
        picked = totals[totals['source'] == source] if len(totals) else totals
        if picked.empty:
            total = matched = unmatched = unidentified = 0
        else:
            row = picked.iloc[0]
            total, matched = int(row.all_retained_records), int(row.matched_records)
            unmatched, unidentified = int(row.unmatched_records), int(row.unidentified_records)
        linkable = matched + unmatched
        rows.append({'source': source, 'all_retained_records': total, 'used_in_comparisons_matched': matched,
                     'excluded_unmatched': unmatched, 'excluded_unidentified': unidentified,
                     'pct_excluded': round(100 * (unmatched + unidentified) / total, 2) if total else None,
                     'exclusion_denominator': 'all_retained_records',
                     'pct_unmatched_of_linkable': round(100 * unmatched / linkable, 2) if linkable else None,
                     'unmatched_denominator': 'usable DOT records only; unidentified records are not in this denominator'})
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
        if column in integrated:
            integrated[column] = pd.to_numeric(integrated[column])

    pattern = monthly_pattern(monthly)
    outputs = {
        'excluded_record_counts': excluded_counts(monthly),
        'yearly_activity': yearly_activity(monthly),
        'monthly_pattern': pattern,
        'month_of_year': month_of_year(pattern),
        'unobserved_months': unobserved_months(monthly),
        'state_year_activity': state_year(monthly),
        'by_fleet_size_matched_only': characteristic_comparison(integrated, 'POWER_UNITS', 'fleet_bin'),
    }
    if 'TOTAL_DRIVERS' in integrated:
        outputs['by_driver_count_matched_only'] = characteristic_comparison(integrated, 'TOTAL_DRIVERS', 'driver_bin')
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
