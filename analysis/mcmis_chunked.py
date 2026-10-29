"""Stream Company Census CSVs into reproducible quality and carrier summaries."""

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

REQUIRED = ("DOT_NUMBER", "PHY_STATE")
NUMERIC = ("TOTAL_DRIVERS", "POWER_UNITS", "MCS150_MILEAGE")
OPTIONAL = ("PHY_COUNTRY", *NUMERIC, "MCS150_MILEAGE_YEAR")
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
US_TERRITORIES = set("AS GU MP PR VI".split())
FLEET_BINS = ("0", "1", "2-5", "6-20", "21-100", "101+", "missing", "invalid")


def integer_values(raw, positive=False):
    """Accept nonnegative decimal integers (including .0), without float rounding."""
    text = raw.str.strip()
    missing = text.eq("") | text.str.upper().isin(["NA", "N/A", "NULL", "NAN"])
    digits = text.str.replace(r"\.0+$", "", regex=True).str.lstrip("0")
    # Bound corrupted inputs and keep conversion exact on every supported pandas version.
    valid = ~missing & text.str.fullmatch(r"[0-9]+(?:\.0+)?") & digits.str.len().le(15)
    if positive:
        valid &= digits.ne("")
    values = pd.Series(pd.NA, index=raw.index, dtype="Int64")
    values.loc[valid] = pd.to_numeric(digits.loc[valid].replace("", "0")).astype("Int64")
    return values, missing, ~missing & ~valid


def location_codes(raw):
    text = raw.str.strip().str.upper()
    # NA is a legitimate two-letter location code (including Namibia).
    missing = text.eq("") | text.isin(["N/A", "NULL", "NAN"])
    invalid = ~missing & ~text.str.fullmatch(r"[A-Z]{2}")
    return text.mask(missing, "missing").mask(invalid, "invalid"), missing, invalid


def location_group(country, state):
    if country in ("missing", "invalid"):
        return "country_unknown"
    if country != "US":
        return "non_us"
    if state in US_STATES:
        return "us_state_or_dc"
    if state in US_TERRITORIES:
        return "us_territory"
    return "us_unknown_state"


def hashed_lines(handle, digest):
    for index, line in enumerate(handle):
        digest.update(line)
        yield line.decode("utf-8-sig" if index == 0 else "utf-8")


def process_csv(input_path, output_dir, chunk_size=100_000):
    """Write reports to a new directory; retain the first valid occurrence of each DOT."""
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    source, destination = Path(input_path), Path(output_dir)
    if not source.is_file():
        raise ValueError(f"Input is not a file: {source}")
    if destination.exists():
        raise ValueError("Output directory already exists; choose a new run directory")
    initial_stat = source.stat()
    with source.open(encoding="utf-8-sig", newline="") as handle:
        header = next(csv.reader(handle), [])
    names = [name.strip().upper() for name in header]
    if not names:
        raise ValueError("Input CSV is empty")
    if len(names) != len(set(names)) or any(not name for name in names):
        raise ValueError("CSV headers must be nonempty and unique after normalization")
    absent = set(REQUIRED) - set(names)
    if absent:
        raise ValueError("Missing required columns: " + ", ".join(sorted(absent)))
    selected = [name for name in (*REQUIRED, *OPTIONAL) if name in names]
    original = dict(zip(names, header))
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        try:
            records = csv.reader(hashed_lines(handle, digest), strict=True)
            next(records)
            for row in records:
                if row and len(row) != len(header):
                    raise ValueError(f"CSV record ending at line {records.line_num} has {len(row)} fields; expected {len(header)}")
        except csv.Error as error:
            raise ValueError(f"Malformed CSV: {error}") from error

    quality = {name: Counter() for name in selected}
    states, carriers, fleets = Counter(), Counter(), Counter()
    stats = {name: {"valid_count": 0, "missing_count": 0, "invalid_count": 0,
                    "zero_count": 0, "sum": 0, "min": None, "max": None} for name in NUMERIC}
    totals = Counter()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mcmis-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "reports"
        stage.mkdir()
        with closing(sqlite3.connect(Path(temporary) / "carriers.sqlite")) as database:
            database.execute("PRAGMA cache_size = -8192")
            database.execute("CREATE TABLE seen (dot TEXT PRIMARY KEY, first_row INTEGER NOT NULL)")
            database.execute("CREATE INDEX seen_first_row ON seen(first_row)")
            with pd.read_csv(source, usecols=[original[n] for n in selected], dtype="string",
                             keep_default_na=False, encoding="utf-8-sig", chunksize=chunk_size) as reader:
                for chunk in reader:
                    chunk = chunk.rename(columns={original[n]: n for n in selected}).reset_index(drop=True)
                    start = totals["processed_rows"]
                    totals["processed_rows"] += len(chunk)
                    values, missing, invalid = integer_values(chunk["DOT_NUMBER"], positive=True)
                    quality["DOT_NUMBER"].update(missing_count=int(missing.sum()), invalid_count=int(invalid.sum()))
                    identifiers = values.dropna()
                    database.executemany("INSERT OR IGNORE INTO seen VALUES (?, ?)",
                                         ((str(int(dot)), start + int(i)) for i, dot in identifiers.items()))
                    database.commit()
                    first = [row[0] - start for row in database.execute(
                        "SELECT first_row FROM seen WHERE first_row >= ? AND first_row < ?",
                        (start, totals["processed_rows"]))]
                    totals["unique_carriers"] += len(first)
                    totals["duplicate_rows"] += len(identifiers) - len(first)
                    totals["missing_identifier_rows"] += int(missing.sum())
                    totals["invalid_identifier_rows"] += int(invalid.sum())
                    state, missing, invalid = location_codes(chunk["PHY_STATE"])
                    quality["PHY_STATE"].update(missing_count=int(missing.sum()), invalid_count=int(invalid.sum()))
                    country = pd.Series("missing", index=chunk.index)
                    if "PHY_COUNTRY" in chunk:
                        country, missing, invalid = location_codes(chunk["PHY_COUNTRY"])
                        quality["PHY_COUNTRY"].update(missing_count=int(missing.sum()), invalid_count=int(invalid.sum()))
                    states.update(zip(country, state))
                    carriers.update(zip(country.loc[first], state.loc[first]))
                    for name in (*NUMERIC, "MCS150_MILEAGE_YEAR"):
                        if name not in chunk:
                            continue
                        values, missing, invalid = integer_values(chunk[name])
                        if name == "MCS150_MILEAGE_YEAR":
                            invalid |= values.notna() & ~values.between(1900, 2100).fillna(False)
                            values = values.mask(invalid)
                        quality[name].update(missing_count=int(missing.sum()), invalid_count=int(invalid.sum()),
                                             zero_count=int(values.eq(0).sum()))
                        if name not in NUMERIC:
                            continue
                        unique = values.loc[first]
                        valid = unique.dropna()
                        aggregate = stats[name]
                        aggregate["missing_count"] += int(missing.loc[first].sum())
                        aggregate["invalid_count"] += int(invalid.loc[first].sum())
                        aggregate["zero_count"] += int(valid.eq(0).sum())
                        aggregate["valid_count"] += len(valid)
                        if len(valid):
                            aggregate["sum"] += sum(int(value) for value in valid)
                            low, high = int(valid.min()), int(valid.max())
                            aggregate["min"] = low if aggregate["min"] is None else min(aggregate["min"], low)
                            aggregate["max"] = high if aggregate["max"] is None else max(aggregate["max"], high)
                        if name == "POWER_UNITS":
                            bins = pd.Series("invalid", index=first, dtype="string")
                            bins.loc[missing.loc[first]] = "missing"
                            for label, low, high in (("0", 0, 0), ("1", 1, 1), ("2-5", 2, 5),
                                                     ("6-20", 6, 20), ("21-100", 21, 100),
                                                     ("101+", 101, 999_999_999_999_999)):
                                bins.loc[unique.between(low, high).fillna(False)] = label
                            fleets.update(bins)
            if not totals["processed_rows"]:
                raise ValueError("Input CSV has headers but no data records")
            final_stat = source.stat()
            if (initial_stat.st_size, initial_stat.st_mtime_ns) != (final_stat.st_size, final_stat.st_mtime_ns):
                raise ValueError("Input changed during processing; no reports published")

        pd.DataFrame([{"metric": name, "value": totals[name]} for name in
                      ("processed_rows", "unique_carriers", "duplicate_rows", "missing_identifier_rows",
                       "invalid_identifier_rows")]).to_csv(stage / "overview.csv", index=False)
        pd.DataFrame([{"column": name, "row_count": totals["processed_rows"],
                       "missing_count": quality[name]["missing_count"],
                       "missing_fraction": quality[name]["missing_count"] / totals["processed_rows"],
                       "invalid_count": quality[name]["invalid_count"],
                       "zero_count": quality[name]["zero_count"] if name in NUMERIC else None}
                      for name in selected]).to_csv(stage / "data_quality.csv", index=False)
        pd.DataFrame([{"physical_country": country, "physical_state": state,
                       "location_group": location_group(country, state), "row_count": states[country, state],
                       "unique_carriers": carriers[country, state]}
                      for country, state in sorted(states)]).to_csv(stage / "state_counts.csv", index=False)
        pd.DataFrame([{"power_units_bin": label, "available": "POWER_UNITS" in selected,
                       "unique_carriers": fleets[label] if "POWER_UNITS" in selected else None}
                      for label in FLEET_BINS]).to_csv(stage / "fleet_distribution.csv", index=False)
        pd.DataFrame([{"column": name, "available": name in selected,
                       **(aggregate if name in selected else {key: None for key in aggregate}),
                       "sum": aggregate["sum"] if aggregate["valid_count"] else None,
                       "mean": aggregate["sum"] / aggregate["valid_count"] if aggregate["valid_count"] else None}
                      for name, aggregate in stats.items()], dtype=object).to_csv(stage / "numeric_summary.csv", index=False)
        metadata = {"input_filename": source.name, "input_bytes": initial_stat.st_size,
                    "input_sha256": digest.hexdigest(), "chunk_size": chunk_size,
                    "python_version": platform.python_version(), "pandas_version": pd.__version__,
                    "analyzed_columns": selected, "unavailable_columns": [n for n in OPTIONAL if n not in selected],
                    "deduplication": "first valid occurrence in input order; state row_count and data_quality use all rows"}
        (stage / "run_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        stage.rename(destination)
    return dict(totals)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Company Census CSV (UTF-8)")
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for this run")
    parser.add_argument("--chunk-size", type=int, default=100_000)
    args = parser.parse_args(argv)
    try:
        totals = process_csv(args.input, args.output_dir, args.chunk_size)
    except (ValueError, OSError, sqlite3.Error, pd.errors.ParserError) as error:
        parser.exit(2, f"Error: {error}\n")
    print(f"Processed {totals['processed_rows']:,} rows; {totals['unique_carriers']:,} unique carriers; "
          f"{totals['duplicate_rows']:,} duplicate rows; "
          f"{totals['missing_identifier_rows'] + totals['invalid_identifier_rows']:,} unidentified rows.")
    print(f"Reports: {args.output_dir}")


if __name__ == "__main__":
    main()
