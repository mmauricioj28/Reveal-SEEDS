"""Build a Tableau and browser extract from a reviewed safety integration run."""

import argparse
import calendar
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb


SOURCES = ("crash", "inspection")
STATUSES = ("matched", "unmatched", "unidentified")
INTEGERS = {"TINYINT", "SMALLINT", "INTEGER", "BIGINT", "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT"}
TEXT = {"VARCHAR"}
ACTIVITY_FIELDS = ("source", "year", "month", "state", *STATUSES)
CARRIER_FIELDS = ("year", "dimension", "category", "carrier_years", "crash_records", "inspection_records")
CALENDAR_FIELDS = ("source", "year", "month", "coverage", *STATUSES)


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    fingerprint = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            fingerprint.update(chunk)
    return fingerprint.hexdigest()


def snapshot_metadata(run_dir, receipt_path):
    metadata = read_json(run_dir / "run_metadata.json")
    validation = read_json(run_dir / "integration_validation.json")
    receipt = read_json(receipt_path)
    period = metadata["period"]
    check(isinstance(period, list) and len(period) == 2 and
          all(type(year) is int for year in period) and 1 <= period[0] <= period[1] <= 9999,
          "run_metadata.json requires a valid pair of calendar years")
    check(period == receipt["period_requested"], "Review receipt and run periods differ")
    check(validation["checks_passed"] is True and receipt["checks_passed"] is True and
          validation == receipt["reconciliation"], "Run reconciliation differs from the approved receipt")
    inputs = {}
    for source in ("census", *SOURCES):
        value = metadata["inputs"][source]["sha256"]
        check(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
              and value == receipt["inputs"][source]["sha256"], f"Review receipt differs for {source} SHA-256")
        inputs[source] = value
    snapshot = {"period": period, "inputs": inputs, "coverage": receipt["coverage"]}
    if "pipeline_executed_on" in receipt:
        snapshot["run_date"] = receipt["pipeline_executed_on"]
    return snapshot, validation


def attach(con, name, path, schema):
    if not path.is_file():
        raise FileNotFoundError(f"Missing integration output: {path}")
    table = con.read_parquet(str(path))
    actual = dict(zip(table.columns, map(str, table.types)))
    for column, allowed in schema.items():
        check(actual.get(column) in allowed, f"{path.name}: {column} has type {actual.get(column, 'MISSING')}, "
              f"expected one of {sorted(allowed)}")
    table.create_view(name)


def reject_rows(con, query, message, parameters=()):
    check(con.execute(query, parameters).fetchone() is None, message)


def rows(con, query, fields):
    return [dict(zip(fields, row)) for row in con.execute(query).fetchall()]


def extract(con, paths, period, validation):
    attach(con, "monthly", paths["monthly_activity"], {
        "source": TEXT, "YEAR": INTEGERS, "MONTH": INTEGERS, "event_state": TEXT, "REPORT_STATE": TEXT,
        "match_status": TEXT, "record_count": INTEGERS})
    attach(con, "integrated", paths["carrier_safety_2016_2025"], {
        "DOT_NUMBER": TEXT, "YEAR": INTEGERS, "census_matched": INTEGERS | {"BOOLEAN"},
        "POWER_UNITS": INTEGERS, "CARRIER_OPERATION": TEXT,
        "TOTAL_CRASHES": INTEGERS, "TOTAL_INSPECTIONS": INTEGERS})
    reject_rows(con, """
        SELECT 1 FROM monthly WHERE source IS NULL OR source NOT IN ('crash','inspection')
        OR match_status IS NULL OR match_status NOT IN ('matched','unmatched','unidentified')
        OR YEAR IS NULL OR YEAR NOT BETWEEN ? AND ? OR MONTH IS NULL OR MONTH NOT BETWEEN 1 AND 12
        OR record_count IS NULL OR record_count <= 0
        OR (source = 'inspection' AND event_state IS DISTINCT FROM REPORT_STATE) LIMIT 1
        """, "Invalid date, source, linkage status, count or inspection geography in monthly_activity", period)
    reject_rows(con, """SELECT 1 FROM monthly GROUP BY source,YEAR,MONTH,event_state,REPORT_STATE,match_status
                        HAVING COUNT(*) > 1 LIMIT 1""", "Duplicate monthly_activity key")
    reject_rows(con, """
        SELECT 1 FROM integrated WHERE DOT_NUMBER IS NULL OR NOT regexp_full_match(DOT_NUMBER, '[1-9][0-9]*')
        OR YEAR IS NULL OR YEAR NOT BETWEEN ? AND ? OR census_matched IS NULL OR census_matched NOT IN (0,1)
        OR POWER_UNITS < 0 OR TOTAL_CRASHES IS NULL OR TOTAL_INSPECTIONS IS NULL OR TOTAL_CRASHES < 0
        OR TOTAL_INSPECTIONS < 0 OR (TOTAL_CRASHES = 0 AND TOTAL_INSPECTIONS = 0) LIMIT 1
        """, "Invalid carrier key, year, match flag, fleet size or event count in carrier-year table", period)
    reject_rows(con, """SELECT 1 FROM integrated GROUP BY DOT_NUMBER,YEAR HAVING COUNT(*) > 1 LIMIT 1""",
                "Duplicate DOT_NUMBER and YEAR in carrier-year table")
    reject_rows(con, """SELECT 1 FROM integrated GROUP BY DOT_NUMBER
                        HAVING count(DISTINCT (census_matched, POWER_UNITS, CARRIER_OPERATION)) > 1 LIMIT 1""",
                "A carrier has conflicting linkage or Census attributes within one snapshot")
    nrows, distinct = con.execute("SELECT count(*), count(DISTINCT DOT_NUMBER) FROM integrated").fetchone()
    check(nrows == validation["integrated_carrier_years"] == validation["event_union_carrier_years"] and
          distinct == validation["integrated_distinct_carriers"], "Carrier counts disagree with the run receipt")

    activity = rows(con, """
        SELECT source,YEAR,MONTH,coalesce(nullif(trim(event_state),''),'Unknown') AS state,
               sum(CASE WHEN match_status='matched' THEN record_count ELSE 0 END),
               sum(CASE WHEN match_status='unmatched' THEN record_count ELSE 0 END),
               sum(CASE WHEN match_status='unidentified' THEN record_count ELSE 0 END)
        FROM monthly GROUP BY 1,2,3,4 ORDER BY 1,2,3,4
        """, ACTIVITY_FIELDS)
    by_year = Counter()
    observed = set()
    for row in activity:
        observed.add((row["year"], row["source"]))
        for status in STATUSES:
            by_year[row["year"], row["source"], status] += row[status]
    for source in SOURCES:
        totals = {s: sum(by_year[y, source, s] for y in range(period[0], period[1] + 1)) for s in STATUSES}
        source_check = validation[source]
        check(all(totals[s] == source_check[s + "_records"] for s in STATUSES)
              and sum(totals.values()) == source_check["monthly_records"]
              and totals["matched"] + totals["unmatched"] == source_check["integrated_records"]
              == source_check["retained_linkable_records"],
              f"Monthly {source} record counts disagree with the run receipt")
    integrated = {}
    for year, flag, crashes, inspections in con.execute("""
            SELECT YEAR,census_matched,sum(TOTAL_CRASHES),sum(TOTAL_INSPECTIONS)
            FROM integrated GROUP BY YEAR,census_matched""").fetchall():
        for source, total in zip(SOURCES, (crashes, inspections)):
            integrated[year, source, "matched" if flag else "unmatched"] = total
    for year in range(period[0], period[1] + 1):
        for source in SOURCES:
            for status in ("matched", "unmatched"):
                key = year, source, status
                check(integrated.get(key, 0) == by_year[key],
                      f"{year} {source} {status}: monthly and carrier-year records disagree")

    carriers = rows(con, """
        SELECT YEAR,dimension,category,count(*),sum(TOTAL_CRASHES),sum(TOTAL_INSPECTIONS)
        FROM integrated, LATERAL (VALUES
            ('fleet', CASE WHEN POWER_UNITS IS NULL THEN 'Missing' WHEN POWER_UNITS = 0 THEN '0'
                           WHEN POWER_UNITS = 1 THEN '1' WHEN POWER_UNITS <= 5 THEN '2-5'
                           WHEN POWER_UNITS <= 20 THEN '6-20' WHEN POWER_UNITS <= 100 THEN '21-100'
                           ELSE '101+' END),
            ('operation',coalesce(nullif(trim(CARRIER_OPERATION),''),'Missing'))
        ) AS attributes(dimension,category)
        WHERE census_matched = 1 GROUP BY 1,2,3 ORDER BY 1,2,3
        """, CARRIER_FIELDS)
    for row in carriers:
        for source in SOURCES:
            if (row["year"], source) not in observed:
                row[source + "_records"] = None
    return activity, carriers


def calendar_rows(activity, period, coverage):
    months = defaultdict(Counter)
    for row in activity:
        months[row["source"], row["year"], row["month"]].update({s: row[s] for s in STATUSES})
    result = []
    for source in SOURCES:
        observed = sorted((y, m) for s, y, m in months if s == source)
        limits = coverage[source]
        check((period[1] - period[0] + 1) * 12 - len(observed) == limits["unobserved_month_count"],
              f"Missing-month count disagrees with {source} coverage")
        if observed:
            first, last = (date.fromisoformat(limits[k]) for k in ("min", "max"))
            check(first <= last and observed[0] == (first.year, first.month)
                  and observed[-1] == (last.year, last.month), f"Date bounds disagree with {source} coverage")
        else:
            check(limits["min"] is None and limits["max"] is None, f"Empty {source} must have null date bounds")
        for year in range(period[0], period[1] + 1):
            for month in range(1, 13):
                counts = months.get((source, year, month))
                state = "unobserved"
                if counts is not None:
                    partial = (first.year == year and first.month == month and first.day != 1) or (
                        last.year == year and last.month == month and last.day != calendar.monthrange(year, month)[1])
                    state = "partial boundary" if partial else "observed"
                result.append(dict(zip(CALENDAR_FIELDS, (source, year, month, state,
                    *(counts[s] if counts is not None else None for s in STATUSES)))))
    return result


def export(run_dir: Path, receipt: Path, output_dir: Path) -> None:
    run_dir, output_dir = Path(run_dir), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Choose a new export directory: {output_dir}")
    paths = {name: run_dir / (name + ".parquet") for name in ("monthly_activity", "carrier_safety_2016_2025")}
    before = {k: p.stat() for k, p in paths.items()}
    try:
        snapshot, validation = snapshot_metadata(run_dir, Path(receipt))
        with duckdb.connect() as con:
            activity, carriers = extract(con, paths, snapshot["period"], validation)
        coverage = calendar_rows(activity, snapshot["period"], snapshot["coverage"])
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Incomplete or invalid run receipt: {exc}") from exc
    snapshot["parquet_sha256"] = {k: digest(p) for k, p in paths.items()}
    for name, path in paths.items():
        after = path.stat()
        check((before[name].st_size, before[name].st_mtime_ns) == (after.st_size, after.st_mtime_ns),
              f"{path.name} changed during export")
    snapshot["id"] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output_dir.parent) as tmp:
        stage = Path(tmp) / "export"
        stage.mkdir()
        for name, fields, records in (("activity", ACTIVITY_FIELDS, activity), ("carriers", CARRIER_FIELDS, carriers),
                                      ("calendar", CALENDAR_FIELDS, coverage)):
            with (stage / (name + ".csv")).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
                writer.writeheader()
                writer.writerows(records)
        payload = {"version": 1, "snapshot": snapshot, "activity": activity, "carriers": carriers}
        (stage / "dashboard.json").write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n",
                                              encoding="utf-8", newline="\n")
        stage.rename(output_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True, help="independent full_dataset_validation.json")
    parser.add_argument("--output-dir", type=Path, required=True, help="new directory for dashboard tables")
    args = parser.parse_args()
    try:
        export(args.run_dir, args.receipt, args.output_dir)
    except (OSError, ValueError, duckdb.Error) as exc:
        parser.exit(1, f"Export failed: {exc}\n")
