"""Reconcile streaming FMCSA outputs before publication; all checks run on disk."""


def validate_integration(database, quality, metrics):
    """Raise on lost/inflated counts and return machine-readable linkage evidence."""
    def scalar(query):
        return database.execute(query).fetchone()[0]

    def require(condition, message):
        if not condition:
            raise ValueError('Integration validation failed: ' + message)

    for kind, report in quality.items():
        counts = report['counts']
        excluded = sum(counts[n] for n in ('excluded_identifier', 'excluded_date', 'excluded_window', 'excluded_status'))
        require(counts['input_rows'] == excluded + counts['duplicate_rows'] + counts['retained_rows'],
                f'{kind} raw row partition')
        require(counts['retained_rows'] == counts['retained_linkable'] + counts['retained_unidentified'],
                f'{kind} retained identifier partition')
        require(scalar(f'SELECT COUNT(*) FROM {kind}') == counts['retained_rows'], f'{kind} retained storage')
        for name, field in report['variables'].items():
            field['row_count'] = counts['input_rows']
            field['missing_fraction'] = field['missing'] / counts['input_rows'] if counts['input_rows'] else None
        report['retained_geography'] = {}
        geo_columns = ('PHY_COUNTRY', 'PHY_STATE', 'LOCATION_GROUP') if kind == 'census' else (
            ('STATE', 'REPORT_STATE') if kind == 'crash' else ('REPORT_STATE',))
        for column in geo_columns:
            report['retained_geography'][column] = {
                value if value is not None else 'unavailable': count
                for value, count in database.execute(f'SELECT {column},COUNT(*) FROM {kind} GROUP BY {column}')}
        if kind == 'census':
            continue
        date = 'REPORT_DATE' if kind == 'crash' else 'INSP_DATE'
        report['retained_date_coverage'] = dict(zip(('min', 'max'), database.execute(
            f'SELECT MIN({date}),MAX({date}) FROM {kind}').fetchone()))
        report['retained_month_counts'] = {f'{year}-{month:02d}': count for year, month, count in database.execute(
            f'SELECT YEAR,MONTH,COUNT(*) FROM {kind} GROUP BY YEAR,MONTH ORDER BY YEAR,MONTH')}
        report['unobserved_months'] = [f'{year}-{month:02d}' for year in range(2016, 2026) for month in range(1, 13)
                                     if f'{year}-{month:02d}' not in report['retained_month_counts']]
        profile_columns = ['CI_STATUS_CODE'] + (['INSP_LEVEL_ID'] if kind == 'inspection' else [])
        report['retained_codes'] = {column: {value if value is not None else 'unavailable_or_blank': count
            for value, count in database.execute(f'SELECT {column},COUNT(*) FROM {kind} GROUP BY {column}')}
            for column in profile_columns}

    result = {'census_carriers': scalar('SELECT COUNT(*) FROM census'),
              'integrated_carrier_years': scalar('SELECT COUNT(*) FROM integrated'),
              'event_union_carrier_years': scalar('SELECT COUNT(*) FROM event_keys'),
              'integrated_distinct_carriers': scalar('SELECT COUNT(DISTINCT DOT_NUMBER) FROM integrated'),
              'census_carriers_with_events': scalar('SELECT COUNT(*) FROM census WHERE DOT_NUMBER IN (SELECT DOT_NUMBER FROM event_keys)'),
              'census_carriers_without_events': scalar('SELECT COUNT(*) FROM census WHERE DOT_NUMBER NOT IN (SELECT DOT_NUMBER FROM event_keys)')}
    require(result['integrated_carrier_years'] == result['event_union_carrier_years'], 'event union keys')
    require(result['census_carriers'] == result['census_carriers_with_events'] + result['census_carriers_without_events'],
            'census carrier partition')
    for kind, count_column in (('crash', 'TOTAL_CRASHES'), ('inspection', 'TOTAL_INSPECTIONS')):
        counts = quality[kind]['counts']
        grouped = scalar(f'SELECT COALESCE(SUM({count_column}),0) FROM {kind}_year')
        integrated = scalar(f'SELECT COALESCE(SUM({count_column}),0) FROM integrated')
        monthly = scalar(f"SELECT COALESCE(SUM(record_count),0) FROM monthly WHERE source='{kind}'")
        matched = scalar(f'SELECT COALESCE(SUM({count_column}),0) FROM integrated WHERE census_matched=1')
        unmatched = scalar(f'SELECT COALESCE(SUM({count_column}),0) FROM integrated WHERE census_matched=0')
        require(counts['retained_linkable'] == grouped == integrated == matched + unmatched, f'{kind} event totals')
        require(monthly == counts['retained_rows'], f'{kind} monthly totals including unidentified')
        measurements = {}
        for source, target in metrics[kind].items():
            raw_sum, observed = database.execute(
                f'SELECT SUM({source}),COUNT({source}) FROM {kind} WHERE DOT_NUMBER IS NOT NULL').fetchone()
            joined_sum, joined_observed = database.execute(
                f'SELECT SUM({target}),COALESCE(SUM({target}_observed),0) FROM integrated').fetchone()
            require(raw_sum == joined_sum and observed == joined_observed, f'{kind} {source} measurement totals')
            measurements[source] = {'observed_records': observed, 'observed_sum': raw_sum}
        result[kind] = {'retained_linkable_records': grouped, 'integrated_records': integrated,
                        'monthly_records': monthly, 'matched_records': matched, 'unmatched_records': unmatched,
                        'matched_distinct_carriers': scalar(f'SELECT COUNT(DISTINCT DOT_NUMBER) FROM integrated WHERE census_matched=1 AND {count_column}>0'),
                        'unmatched_distinct_carriers': scalar(f'SELECT COUNT(DISTINCT DOT_NUMBER) FROM integrated WHERE census_matched=0 AND {count_column}>0'),
                        'measurements': measurements}
    result['checks_passed'] = True
    return result
