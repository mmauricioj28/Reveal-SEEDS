"""Download selected FMCSA columns and require the official row count.

A page cap or a short sample is not a full extract. The file is published only
when the written row count equals the portal count(*) before and after the
download. National files stay in the ignored data/ directory.
"""
import argparse
import csv
import hashlib
import io
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = 'https://data.transportation.gov/resource'
PAGE = 50_000
WINDOW = "between '20160101' and '20251231'"
SOURCES = {
    'census': {
        'id': 'az4n-8mr2',
        'where': None,
        'columns': ('dot_number', 'phy_state', 'phy_country', 'power_units', 'total_drivers',
                    'mcs150_mileage', 'mcs150_mileage_year', 'carrier_operation', 'status_code',
                    'carship', 'safety_rating'),
    },
    'crash': {
        'id': 'aayw-vxb3',
        'where': f'report_date {WINDOW}',
        'columns': ('crash_id', 'dot_number', 'report_date', 'state', 'report_state',
                    'fatalities', 'injuries', 'ci_status_code'),
    },
    'inspection': {
        'id': 'fx4q-ay7w',
        'where': f'insp_date {WINDOW}',
        'columns': ('inspection_id', 'dot_number', 'insp_date', 'report_state', 'insp_level_id',
                    'viol_total', 'oos_total', 'vehicle_oos_total', 'driver_oos_total', 'ci_status_code'),
    },
}


def require_complete(written, before, after):
    """Exit unless the extract matches both official counts."""
    if written != before or written != after:
        raise SystemExit(f'incomplete extract: wrote {written}, count before {before}, count after {after}')


def _get(resource, params):
    url = f'{BASE}/{resource}?' + urlencode(params)
    request = Request(url, headers={'User-Agent': 'Reveal-SEEDS-fmcsa-fetch'})
    for attempt in range(5):
        try:
            with urlopen(request, timeout=600) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError('unreachable')


def official_count(spec):
    params = {'$select': 'count(*)'}
    if spec['where']:
        params['$where'] = spec['where']
    payload = json.loads(_get(f"{spec['id']}.json", params))
    return int(payload[0]['count'])


def _page(spec, offset):
    params = {'$select': ','.join(spec['columns']), '$order': ':id', '$limit': PAGE, '$offset': offset}
    if spec['where']:
        params['$where'] = spec['where']
    text = _get(f"{spec['id']}.csv", params).decode('utf-8-sig')
    return list(csv.DictReader(io.StringIO(text)))


def download(dataset, output):
    spec = SOURCES[dataset]
    output = Path(output)
    if output.exists():
        raise SystemExit(f'{output} already exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    before = official_count(spec)
    partial = output.with_suffix(output.suffix + '.partial')
    written = 0
    started = time.perf_counter()
    with partial.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=spec['columns'], extrasaction='ignore', lineterminator='\n')
        writer.writeheader()
        offset = 0
        while written < before:
            rows = _page(spec, offset)
            if not rows:
                break
            missing = [name for name in spec['columns'] if name not in rows[0]]
            if missing:
                partial.unlink(missing_ok=True)
                raise SystemExit(f'{dataset}: portal response missing {missing}')
            writer.writerows(rows)
            written += len(rows)
            offset += len(rows)
            print(f'{dataset} {written}/{before}', flush=True)
            if len(rows) < PAGE:
                break
    after = official_count(spec)
    try:
        require_complete(written, before, after)
    except SystemExit:
        partial.unlink(missing_ok=True)
        raise
    digest = hashlib.sha256(partial.read_bytes()).hexdigest()
    partial.replace(output)
    receipt = {'dataset': dataset, 'resource': spec['id'], 'where': spec['where'],
               'columns': list(spec['columns']), 'official_count_before': before,
               'official_count_after': after, 'written_rows': written, 'sha256': digest,
               'bytes': output.stat().st_size, 'runtime_seconds': round(time.perf_counter() - started, 3)}
    output.with_suffix('.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(f'FETCH COMPLETE {dataset} rows={written} sha256={digest}', flush=True)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, choices=[*SOURCES, 'all'])
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args(argv)
    names = list(SOURCES) if args.dataset == 'all' else [args.dataset]
    for name in names:
        download(name, args.output_dir / f'{name}.csv')


if __name__ == '__main__':
    main()
