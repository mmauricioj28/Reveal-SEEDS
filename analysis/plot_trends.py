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

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
SNAPSHOT_NOTE = 'Carrier characteristics are a current Census snapshot and may differ in earlier years.'
COLORS = {'matched': '#2a6f97', 'unmatched': '#e07a1f', 'unidentified': '#8d99ae'}


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def yearly_chart(eda_dir, out):
    data = pd.read_csv(eda_dir / 'yearly_activity.csv')
    for source, frame in data.groupby('source'):
        frame = frame.sort_values('YEAR')
        fig, ax = plt.subplots(figsize=(9, 5))
        bottom = pd.Series(0.0, index=frame.index)
        for column, label in (('matched_records', 'matched'), ('unmatched_records', 'unmatched'),
                              ('unidentified_records', 'unidentified')):
            ax.bar(frame['YEAR'].astype(int), frame[column], bottom=bottom, label=label, color=COLORS[label])
            bottom += frame[column]
        ax.set_title(f'{source.title()} records per year, by Census match status')
        ax.set_xlabel('Year')
        ax.set_ylabel('Records')
        ax.set_xticks(frame['YEAR'].astype(int))
        ax.legend(title='Status')
        ax.text(0, -0.2, 'Unidentified = no usable USDOT number. Unmatched = USDOT not found in Census.\n'
                'Recent years may be incomplete because of reporting lag.',
                transform=ax.transAxes, fontsize=8, va='top')
        save(fig, out / f'yearly_{source}.png')


def monthly_chart(eda_dir, out):
    data = pd.read_csv(eda_dir / 'monthly_pattern.csv')
    for source, frame in data.groupby('source'):
        fig, ax = plt.subplots(figsize=(9, 5))
        for year, group in frame.groupby('YEAR'):
            group = group.sort_values('MONTH')
            ax.plot(group['MONTH'].astype(int), group['records_per_day'], marker='o', label=str(int(year)))
        ax.set_title(f'{source.title()} records per calendar day, by month')
        ax.set_xlabel('Month')
        ax.set_ylabel('Records per day')
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(MONTHS)
        ax.legend(title='Year', ncol=2, fontsize=8)
        save(fig, out / f'monthly_{source}.png')


def state_chart(eda_dir, out, top=10):
    data = pd.read_csv(eda_dir / 'state_year_activity.csv')
    for source, frame in data.groupby('source'):
        totals = frame.groupby('event_state')['record_count'].sum().sort_values().tail(top)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(totals.index.astype(str), totals.values, color=COLORS['matched'])
        ax.set_title(f'{source.title()} records by state, top {len(totals)} (all years)')
        ax.set_xlabel('Records (counts, not rates; states differ in size and carriers)')
        save(fig, out / f'states_{source}.png')


def fleet_chart(eda_dir, out):
    path = eda_dir / 'by_fleet_size_matched_only.csv'
    if not path.is_file():
        return
    data = pd.read_csv(path, keep_default_na=False)
    order = ['0', '1', '2-5', '6-20', '21-100', '101+', 'missing']
    data['fleet_bin'] = pd.Categorical(data['fleet_bin'].astype(str), categories=order, ordered=True)
    data = data.sort_values('fleet_bin')
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(data['fleet_bin'].astype(str), data['median_crashes_per_carrier_year'], color=COLORS['matched'])
    ax.set_title('Median crash records per carrier-year, by fleet size (matched carriers only)')
    ax.set_xlabel('Power units (current Census snapshot)')
    ax.set_ylabel('Median crash records per carrier-year')
    ax.text(0, -0.2, SNAPSHOT_NOTE + '\nCarrier-years with at least one observed record only; not a risk rate.',
            transform=ax.transAxes, fontsize=8, va='top')
    save(fig, out / 'fleet_size_crashes.png')


def run(eda_dir, output_dir):
    eda_dir, out = Path(eda_dir), Path(output_dir)
    if out.exists():
        raise ValueError('Output directory already exists; choose a new directory')
    out.mkdir(parents=True)
    yearly_chart(eda_dir, out)
    monthly_chart(eda_dir, out)
    state_chart(eda_dir, out)
    fleet_chart(eda_dir, out)
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
