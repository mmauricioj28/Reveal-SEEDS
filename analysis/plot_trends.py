"""Turn the tables written by ``analysis.eda_trends`` into PNG charts.

Run from the repository root (new output directory each time):
    python -m analysis.plot_trends --eda-dir outputs/eda_01 --output-dir outputs/charts_01

Charts describe observed records, not crash risk. Carrier characteristics come from the current
Census snapshot and may differ from earlier years.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use('Agg')  # write files; no window needed
import matplotlib.pyplot as plt
import pandas as pd

from analysis.eda_trends import GEOGRAPHY

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
SNAPSHOT_NOTE = 'Carrier characteristics are a current Census snapshot and may differ in earlier years.'
COLORS = {'matched': '#2a6f97', 'unmatched': '#e07a1f', 'unidentified': '#8d99ae'}
OPERATION = {'A': 'A interstate', 'B': 'B intrastate hazmat', 'C': 'C intrastate non-hazmat'}


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def exclusion_note(eda_dir, source):
    path = Path(eda_dir) / 'excluded_record_counts.csv'
    if not path.is_file():
        return ''
    rows = pd.read_csv(path)
    picked = rows[rows['source'] == source]
    if picked.empty:
        return ''
    row = picked.iloc[0]
    return (f"Excluded {int(row.excluded_unmatched)} unmatched and {int(row.excluded_unidentified)} unidentified "
            f"of {int(row.all_retained_records)} retained {source} records.")


def yearly_chart(eda_dir, out):
    data = pd.read_csv(eda_dir / 'yearly_activity.csv')
    for source in ('crash', 'inspection'):
        frame = data[data['source'] == source].sort_values('YEAR') if len(data) else data
        fig, ax = plt.subplots(figsize=(9, 5))
        if frame.empty:
            ax.set_title(f'{source.title()} records per year')
            ax.text(0.5, 0.5, 'No retained records', ha='center', va='center')
        else:
            bottom = pd.Series(0.0, index=frame.index)
            for column, label in (('matched_records', 'matched'), ('unmatched_records', 'unmatched'),
                                  ('unidentified_records', 'unidentified')):
                ax.bar(frame['YEAR'].astype(int), frame[column], bottom=bottom, label=label, color=COLORS[label])
                bottom += frame[column]
            ax.set_title(f'{source.title()} records per year, by Census match status')
            ax.set_xlabel('Year')
            ax.set_ylabel('Records (counts, not rates)')
            ax.set_xticks(frame['YEAR'].astype(int))
            ax.legend(title='Status')
            ax.text(0, -0.28, 'Unidentified = missing or invalid USDOT. Unmatched = usable USDOT absent from Census.\n'
                    'Unmatched percent uses usable DOT records only. Absent years are omitted, not drawn as zero.\n'
                    'A year with fewer than 12 observed months is partial.',
                    transform=ax.transAxes, fontsize=8, va='top')
        save(fig, out / f'yearly_{source}.png')


def monthly_chart(eda_dir, out):
    data = pd.read_csv(eda_dir / 'monthly_pattern.csv')
    for source in ('crash', 'inspection'):
        frame = data[data['source'] == source] if len(data) else data
        fig, ax = plt.subplots(figsize=(9, 5))
        if frame.empty:
            ax.set_title(f'{source.title()} records per calendar day')
            ax.text(0.5, 0.5, 'No retained records. Absent months are not shown as zero.', ha='center')
        else:
            for year, group in frame.groupby('YEAR'):
                group = group.sort_values('MONTH')
                ax.plot(group['MONTH'].astype(int), group['records_per_day'], marker='o', label=str(int(year)))
            ax.set_title(f'{source.title()} records per calendar day, by month')
            ax.set_xlabel('Month')
            ax.set_ylabel('Records per calendar day (not per mile)')
            ax.set_xticks(range(1, 13))
            ax.set_xticklabels(MONTHS)
            ax.legend(title='Year', ncol=2, fontsize=8)
            ax.text(0, -0.2, 'Observed months only. A missing month is not a measured zero.',
                    transform=ax.transAxes, fontsize=8, va='top')
        save(fig, out / f'monthly_{source}.png')


def season_chart(eda_dir, out):
    path = Path(eda_dir) / 'month_of_year.csv'
    fig, ax = plt.subplots(figsize=(9, 5))
    data = pd.read_csv(path) if path.is_file() else pd.DataFrame()
    if data.empty:
        ax.text(0.5, 0.5, 'No observed months. Missing months are not plotted as zero.', ha='center', va='center')
    else:
        for source, group in data.groupby('source'):
            group = group.sort_values('MONTH')
            ax.plot(group['MONTH'].astype(int), group['mean_records_per_day'], marker='o', label=source)
        ax.legend(title='Source')
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(MONTHS)
    ax.set_title('Mean records per calendar day, by month of year')
    ax.set_xlabel('Month')
    ax.set_ylabel('Mean records per calendar day (not per mile)')
    ax.text(0, -0.2, 'Average of years in which that month was observed. Not an exposure rate.',
            transform=ax.transAxes, fontsize=8, va='top')
    save(fig, out / 'month_of_year.png')


def state_chart(eda_dir, out, top=10):
    data = pd.read_csv(eda_dir / 'state_year_activity.csv')
    for source in ('crash', 'inspection'):
        frame = data[data['source'] == source] if len(data) else data
        fig, ax = plt.subplots(figsize=(8, 5.4))
        if frame.empty:
            ax.text(0.5, 0.5, 'No retained records', ha='center')
        else:
            totals = frame.groupby('event_state')[['matched_records', 'unmatched_records', 'unidentified_records']].sum()
            totals['all'] = totals.sum(axis=1)
            totals = totals.sort_values('all').tail(top)
            left = pd.Series(0.0, index=totals.index)
            for column, label in (('matched_records', 'matched'), ('unmatched_records', 'unmatched'),
                                  ('unidentified_records', 'unidentified')):
                ax.barh(totals.index.astype(str), totals[column], left=left, label=label, color=COLORS[label])
                left += totals[column]
            ax.legend(title='Status', fontsize=8)
        ax.set_title(f'{source.title()} records by geography')
        ax.set_xlabel('Records (counts, not rates; areas differ in exposure)')
        ax.text(0, -0.22, GEOGRAPHY[source] + ' A code such as US is not a state boundary.',
                transform=ax.transAxes, fontsize=8, va='top')
        save(fig, out / f'states_{source}.png')


def category_chart(eda_dir, out, filename, category, output_name, title, xlabel):
    path = Path(eda_dir) / filename
    fig, ax = plt.subplots(figsize=(9, 5))
    if not path.is_file():
        ax.text(0.5, 0.5, 'Source table not in this run', ha='center')
    else:
        data = pd.read_csv(path, keep_default_na=False)
        if data.empty:
            ax.text(0.5, 0.5, 'No matched carrier-years', ha='center')
        else:
            if category == 'fleet_bin':
                order = ['0', '1', '2-5', '6-20', '21-100', '101+', 'missing']
                data[category] = pd.Categorical(data[category].astype(str), categories=order, ordered=True)
                data = data.sort_values(category)
            labels = data[category].astype(str).map(lambda value: OPERATION.get(value, value))
            ax.bar(labels, data['crash_records'], color=COLORS['matched'])
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel('Crash records (matched counts, not rates)')
    ax.text(0, -0.22, SNAPSHOT_NOTE + '\n' + exclusion_note(eda_dir, 'crash'),
            transform=ax.transAxes, fontsize=8, va='top')
    save(fig, out / output_name)


def fleet_chart(eda_dir, out):
    category_chart(eda_dir, out, 'by_fleet_size_matched_only.csv', 'fleet_bin', 'fleet_size_crashes.png',
                   'Crash records by current fleet size (matched carriers only)',
                   'Power units in the current Census snapshot')


def operation_chart(eda_dir, out):
    category_chart(eda_dir, out, 'by_carrier_operation_matched_only.csv', 'carrier_operation',
                   'carrier_operation_crashes.png',
                   'Crash records by current carrier operation (matched carriers only)',
                   'CARRIER_OPERATION in the current Census snapshot')


def run(eda_dir, output_dir):
    eda_dir, out = Path(eda_dir), Path(output_dir)
    if out.exists():
        raise ValueError('Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    yearly_chart(eda_dir, out)
    monthly_chart(eda_dir, out)
    season_chart(eda_dir, out)
    state_chart(eda_dir, out)
    fleet_chart(eda_dir, out)
    operation_chart(eda_dir, out)
    return sorted(p.name for p in out.glob('*.png'))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--eda-dir', required=True, help='output directory of analysis.eda_trends')
    parser.add_argument('--output-dir', required=True, help='new directory for PNG charts')
    args = parser.parse_args()
    for name in run(args.eda_dir, args.output_dir):
        print('wrote', name)


if __name__ == '__main__':
    main()
