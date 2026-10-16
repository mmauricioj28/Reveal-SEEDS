"""Stream FMCSA extracts into carrier/year tables; extends Ayaan's integration entry point."""
import argparse
from collections import Counter
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import tempfile

import pandas as pd
from analysis.mcmis_chunked import hashed_lines, integer_values, location_codes, location_group

DATA_DIR = Path('data')
OUTPUT_DIR = Path('outputs')
CENSUS_NUMBERS = ('POWER_UNITS', 'TOTAL_DRIVERS', 'MCS150_MILEAGE', 'MCS150_MILEAGE_YEAR')
CENSUS_CODES = ('PHY_STATE', 'PHY_COUNTRY', 'CARRIER_OPERATION', 'STATUS_CODE', 'CARSHIP', 'SAFETY_RATING')
SPECS = {
    'census': {'required': ('DOT_NUMBER', 'PHY_STATE'),
               'optional': ('PHY_COUNTRY', *CENSUS_NUMBERS, *CENSUS_CODES[2:]),
               'numbers': CENSUS_NUMBERS, 'key': 'DOT_NUMBER'},
    'crash': {'required': ('CRASH_ID', 'DOT_NUMBER', 'REPORT_DATE'),
              'optional': ('STATE', 'REPORT_STATE', 'FATALITIES', 'INJURIES', 'CI_STATUS_CODE'),
              'numbers': ('FATALITIES', 'INJURIES'), 'key': 'CRASH_ID', 'date': 'REPORT_DATE'},
    'inspection': {'required': ('INSPECTION_ID', 'DOT_NUMBER', 'INSP_DATE'),
                   'optional': ('REPORT_STATE', 'INSP_LEVEL_ID', 'VIOL_TOTAL', 'OOS_TOTAL',
                                'VEHICLE_OOS_TOTAL', 'DRIVER_OOS_TOTAL', 'CI_STATUS_CODE'),
                   'numbers': ('VIOL_TOTAL', 'OOS_TOTAL', 'VEHICLE_OOS_TOTAL', 'DRIVER_OOS_TOTAL'),
                   'key': 'INSPECTION_ID', 'date': 'INSP_DATE'},
}
METRICS = {'crash': {'FATALITIES': 'TOTAL_FATALITIES', 'INJURIES': 'TOTAL_INJURIES'},
           'inspection': {'VIOL_TOTAL': 'TOTAL_VIOLATIONS', 'OOS_TOTAL': 'TOTAL_OOS',
                          'VEHICLE_OOS_TOTAL': 'TOTAL_VEHICLE_OOS', 'DRIVER_OOS_TOTAL': 'TOTAL_DRIVER_OOS'}}
EVENT_COUNTS = {'crash': 'TOTAL_CRASHES', 'inspection': 'TOTAL_INSPECTIONS'}


def get_filepath(filename_stem):
    """Retain the original full-file then sample-file lookup."""
    for suffix in ('_File.csv', '_Sample.csv'):
        path = DATA_DIR / (filename_stem + suffix)
        if path.is_file():
            return path
    raise FileNotFoundError(f'No full or sample CSV for {filename_stem} in {DATA_DIR}')


def canonicalize_dot(series):
    """Return valid canonical IDs at their original indexes, without float rounding."""
    values, _, _ = integer_values(series.astype('string').fillna(''), positive=True)
    return values.dropna().astype('string')


def parse_dates(raw):
    """Accept documented compact dates and explicit ISO dates only."""
    text = raw.str.strip()
    missing = text.eq('') | text.str.upper().isin(['NA', 'N/A', 'NULL', 'NAN'])
    compact = text.str.fullmatch(r'[0-9]{8}')
    iso = text.str.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
    dates = pd.to_datetime(text.where(compact), format='%Y%m%d', errors='coerce')
    dates = dates.fillna(pd.to_datetime(text.where(iso), format='%Y-%m-%d', errors='coerce'))
    return dates, missing, ~missing & dates.isna()


def inspect_csv(path, spec):
    """Validate every CSV record, including unselected fields, and hash source bytes."""
    path = Path(path)
    initial = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        records = csv.reader(hashed_lines(handle, digest), strict=True)
        header = next(records, [])
        names = [n.strip().upper() for n in header]
        if not names or any(not n for n in names) or len(names) != len(set(names)):
            raise ValueError(f'{path.name}: CSV headers must be nonempty and unique')
        absent = set(spec['required']) - set(names)
        if absent:
            raise ValueError(f'{path.name}: Missing required columns: {sorted(absent)}')
        for row in records:
            if row and len(row) != len(header):
                raise ValueError(f'{path.name}: malformed record at line {records.line_num}')
    selected = [n for n in (*spec['required'], *spec['optional']) if n in names]
    return {'filename': path.name, 'sha256': digest.hexdigest(), 'bytes': initial.st_size,
            'selected_columns': selected,
            'unavailable_columns': [n for n in spec['optional'] if n not in names]}, dict(zip(names, header)), initial


def ingest(database, kind, path, chunk_size):
    spec = SPECS[kind]
    metadata, original, initial = inspect_csv(path, spec)
    columns = list(dict.fromkeys((*spec['required'], *spec['optional'])))
    stored = columns + (['LOCATION_GROUP'] if kind == 'census' else ['YEAR', 'MONTH'])
    numeric_columns = set(spec['numbers']) | {'YEAR', 'MONTH'}
    definition = ', '.join(f'{n} {"INTEGER" if n in numeric_columns else "TEXT"}' for n in stored)
    database.execute(f"CREATE TABLE {kind} ({definition}, PRIMARY KEY ({spec['key']}))")
    totals = Counter({k: 0 for k in ('input_rows', 'retained_rows', 'duplicate_rows', 'conflicting_duplicate_rows',
                                    'excluded_identifier', 'excluded_date', 'excluded_window', 'excluded_status',
                                    'retained_unidentified', 'retained_linkable')})
    quality = {n: Counter({'missing': 0, 'invalid': 0, 'zero': 0}) for n in metadata['selected_columns']}
    coverage = {'min': None, 'max': None}
    selected = metadata['selected_columns']
    with pd.read_csv(path, usecols=[original[n] for n in selected], dtype='string', keep_default_na=False,
                     encoding='utf-8-sig', chunksize=chunk_size) as reader:
        for raw in reader:
            raw = raw.rename(columns={original[n]: n for n in selected}).reset_index(drop=True)
            totals['input_rows'] += len(raw)
            clean = pd.DataFrame(index=raw.index)
            for name in columns:
                if name not in raw:
                    clean[name] = None
                    continue
                if name in (*spec['numbers'], 'DOT_NUMBER', spec['key']):
                    values, missing, invalid = integer_values(raw[name], positive=name in ('DOT_NUMBER', spec['key']))
                    if name == 'MCS150_MILEAGE_YEAR':
                        invalid |= values.notna() & ~values.between(1900, 2100).fillna(False)
                        values = values.mask(invalid)
                    clean[name] = values if name in spec['numbers'] else values.astype('string')
                    quality[name].update(missing=int(missing.sum()), invalid=int(invalid.sum()), zero=int(values.eq(0).sum()))
                elif name == spec.get('date'):
                    dates, missing, invalid = parse_dates(raw[name])
                    clean[name] = dates.dt.strftime('%Y-%m-%d')
                    clean['YEAR'] = dates.dt.year.astype('Int64')
                    clean['MONTH'] = dates.dt.month.astype('Int64')
                    quality[name].update(missing=int(missing.sum()), invalid=int(invalid.sum()))
                    valid_dates = clean[name].dropna()
                    if len(valid_dates):
                        coverage['min'] = min(filter(None, (coverage['min'], valid_dates.min())))
                        coverage['max'] = max(filter(None, (coverage['max'], valid_dates.max())))
                elif name in ('PHY_STATE', 'PHY_COUNTRY', 'STATE', 'REPORT_STATE'):
                    values, missing, invalid = location_codes(raw[name])
                    clean[name] = values
                    quality[name].update(missing=int(missing.sum()), invalid=int(invalid.sum()))
                else:
                    text = raw[name].str.strip().str.upper()
                    missing = text.eq('') | text.isin(['N/A', 'NULL', 'NAN'])
                    clean[name] = text.mask(missing)
                    quality[name].update(missing=int(missing.sum()))
            if kind == 'census':
                clean['LOCATION_GROUP'] = [location_group(c or 'missing', s or 'missing')
                                           for c, s in zip(clean['PHY_COUNTRY'], clean['PHY_STATE'])]
            insert = f"INSERT INTO {kind} VALUES ({','.join('?' for _ in stored)})"
            key_index = stored.index(spec['key'])
            for row in clean[stored].itertuples(index=False, name=None):
                row = tuple(None if pd.isna(v) else int(v) if n in numeric_columns else str(v)
                            for n, v in zip(stored, row))
                if row[key_index] is None:
                    totals['excluded_identifier'] += 1
                    continue
                if kind != 'census':
                    if row[stored.index(spec['date'])] is None:
                        totals['excluded_date'] += 1
                        continue
                    if not 2016 <= row[stored.index('YEAR')] <= 2025:
                        totals['excluded_window'] += 1
                        continue
                    if kind == 'inspection' and row[stored.index('CI_STATUS_CODE')] == 'D':
                        totals['excluded_status'] += 1
                        continue
                try:
                    database.execute(insert, row)
                except sqlite3.IntegrityError:
                    previous = database.execute(f"SELECT * FROM {kind} WHERE {spec['key']}=?", (row[key_index],)).fetchone()
                    totals['duplicate_rows'] += 1
                    totals['conflicting_duplicate_rows'] += previous != row
                    continue
                totals['retained_rows'] += 1
                totals['retained_unidentified' if row[stored.index('DOT_NUMBER')] is None else 'retained_linkable'] += 1
            database.commit()
    if kind != 'census':
        database.execute(f'CREATE INDEX {kind}_dot_year ON {kind}(DOT_NUMBER,YEAR)')
    if (initial.st_size, initial.st_mtime_ns) != (Path(path).stat().st_size, Path(path).stat().st_mtime_ns):
        raise ValueError(f'Input changed during processing: {path}')
    return {'metadata': metadata, 'counts': dict(totals), 'variables': quality, 'parsed_date_coverage': coverage}


def aggregate(database, kind):
    pieces = [f'COUNT(*) AS {EVENT_COUNTS[kind]}']
    for source, target in METRICS[kind].items():
        pieces += [f'SUM({source}) AS {target}', f'COUNT({source}) AS {target}_observed']
    database.execute(f"CREATE TABLE {kind}_year AS SELECT DOT_NUMBER,YEAR,{','.join(pieces)} "
                     f'FROM {kind} WHERE DOT_NUMBER IS NOT NULL GROUP BY DOT_NUMBER,YEAR')
    database.execute(f'CREATE UNIQUE INDEX {kind}_year_key ON {kind}_year(DOT_NUMBER,YEAR)')


def integrate(database):
    """Join preaggregated sources at one unioned DOT/year key; keep census separate."""
    database.execute('CREATE TABLE event_keys AS SELECT DOT_NUMBER,YEAR FROM crash_year UNION SELECT DOT_NUMBER,YEAR FROM inspection_year')
    census = [r[1] for r in database.execute('PRAGMA table_info(census)') if r[1] != 'DOT_NUMBER']
    fields = ['k.DOT_NUMBER', 'k.YEAR', 'CASE WHEN c.DOT_NUMBER IS NULL THEN 0 ELSE 1 END AS census_matched']
    fields += [f'c.{n}' for n in census]
    for kind, alias in (('crash', 'r'), ('inspection', 'i')):
        fields += [f'COALESCE({alias}.{EVENT_COUNTS[kind]},0) AS {EVENT_COUNTS[kind]}']
        for target in METRICS[kind].values():
            fields += [f'{alias}.{target}', f'COALESCE({alias}.{target}_observed,0) AS {target}_observed']
    database.execute(f"CREATE TABLE integrated AS SELECT {','.join(fields)} FROM event_keys k "
                     'LEFT JOIN census c ON k.DOT_NUMBER=c.DOT_NUMBER '
                     'LEFT JOIN crash_year r ON k.DOT_NUMBER=r.DOT_NUMBER AND k.YEAR=r.YEAR '
                     'LEFT JOIN inspection_year i ON k.DOT_NUMBER=i.DOT_NUMBER AND k.YEAR=i.YEAR')
    database.execute('CREATE UNIQUE INDEX integrated_key ON integrated(DOT_NUMBER,YEAR)')
    database.execute('CREATE TABLE monthly AS ' + ' UNION ALL '.join(
        f"SELECT '{kind}' AS source,YEAR,MONTH,{geo} AS event_state,REPORT_STATE,COUNT(*) AS record_count "
        f'FROM {kind} GROUP BY YEAR,MONTH,{geo},REPORT_STATE'
        for kind, geo in (('crash', 'STATE'), ('inspection', 'REPORT_STATE'))))


def export_query(database, query, path, chunk_size, parquet=False):
    """Stream batches with explicit Arrow types, including empty/null-first outputs."""
    cursor = database.execute(query)
    names = [d[0] for d in cursor.description]
    strings = {'DOT_NUMBER', *CENSUS_CODES, 'LOCATION_GROUP', 'source', 'event_state', 'REPORT_STATE'}
    writer = None
    if parquet:
        import pyarrow as pa
        import pyarrow.parquet as pq
        schema = pa.schema([(n, pa.string() if n in strings else pa.int64()) for n in names])
        writer = pq.ParquetWriter(path.with_suffix('.parquet'), schema, compression='snappy')
    try:
        with path.open('w', encoding='utf-8', newline='') as handle:
            output = csv.writer(handle)
            output.writerow(names)
            while rows := cursor.fetchmany(chunk_size):
                output.writerows(rows)
                if writer:
                    arrays = [pa.array([r[j] for r in rows], type=field.type) for j, field in enumerate(schema)]
                    writer.write_table(pa.Table.from_arrays(arrays, schema=schema))
    finally:
        if writer:
            writer.close()


def build_pipeline(census_path=None, crash_path=None, inspection_path=None, output_dir=None,
                   chunk_size=100_000, parquet=False):
    """Publish a new run directory; no-argument calls retain data/ file lookup.

    Explicit paths prevent accidental sample/full mixing. No source is modified.
    """
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError('chunk_size must be a positive integer')
    if parquet:
        try:
            import pyarrow
        except ImportError as error:
            raise ValueError('Parquet requires: pip install -r requirements-parquet.txt') from error
    paths = {'census': Path(census_path) if census_path is not None else get_filepath('Company_Census'),
             'crash': Path(crash_path) if crash_path is not None else get_filepath('Crash'),
             'inspection': Path(inspection_path) if inspection_path is not None else get_filepath('Vehicle_Inspection')}
    destination = Path(output_dir) if output_dir is not None else OUTPUT_DIR / 'safety_run'
    if destination.exists():
        raise ValueError('Output directory already exists; choose a new run directory')
    destination.parent.mkdir(parents=True, exist_ok=True)
    original_stats = {k: (p.stat().st_size, p.stat().st_mtime_ns) for k, p in paths.items()}
    with tempfile.TemporaryDirectory(prefix='.fmcsa-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'reports'
        stage.mkdir()
        with closing(sqlite3.connect(Path(temporary) / 'records.sqlite')) as database:
            database.execute('PRAGMA cache_size=-8192')
            database.execute('PRAGMA temp_store=FILE')
            quality = {k: ingest(database, k, p, chunk_size) for k, p in paths.items()}
            for kind in METRICS:
                aggregate(database, kind)
            integrate(database)
            for table, filename, order in (('census', 'carriers', 'DOT_NUMBER'),
                                            ('crash_year', 'crash_carrier_year', 'DOT_NUMBER,YEAR'),
                                            ('inspection_year', 'inspection_carrier_year', 'DOT_NUMBER,YEAR'),
                                            ('integrated', 'carrier_safety_2016_2025', 'DOT_NUMBER,YEAR'),
                                            ('monthly', 'monthly_activity', 'source,YEAR,MONTH,event_state,REPORT_STATE')):
                export_query(database, f'SELECT * FROM {table} ORDER BY {order}', stage / (filename + '.csv'), chunk_size, parquet)
            (stage / 'quality.json').write_text(json.dumps(quality, indent=2) + '\n', encoding='utf-8')
        for kind, path in paths.items():
            if original_stats[kind] != (path.stat().st_size, path.stat().st_mtime_ns):
                raise ValueError(f'Input changed during processing: {path}')
        metadata = {'period': [2016, 2025], 'chunk_size': chunk_size, 'python': platform.python_version(),
                    'pandas': pd.__version__, 'pyarrow': pyarrow.__version__ if parquet else None,
                    'inputs': {k: v['metadata'] for k, v in quality.items()},
                    'grain': 'observed event DOT/year union; census-only carriers separate'}
        (stage / 'run_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
        stage.rename(destination)
    return destination / ('carrier_safety_2016_2025.parquet' if parquet else 'carrier_safety_2016_2025.csv')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--census', required=True, type=Path)
    parser.add_argument('--crashes', required=True, type=Path)
    parser.add_argument('--inspections', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--chunk-size', type=int, default=100_000)
    parser.add_argument('--parquet', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = build_pipeline(args.census, args.crashes, args.inspections, args.output_dir, args.chunk_size, args.parquet)
    except (ValueError, OSError, sqlite3.Error, csv.Error, pd.errors.ParserError) as error:
        parser.exit(2, f'Error: {error}\n')
    print(f'Analytical output: {result}')


if __name__ == '__main__':
    main()
