"""Analyze unidentified FMCSA crash records by year."""

import argparse
from pathlib import Path

import pandas as pd


def clean_dot_numbers(raw):
    """Replicate the integration pipeline's positive-integer rules."""
    text = raw.fillna("").astype("string").str.strip()

    missing = text.eq("") | text.str.upper().isin(
        ["NA", "N/A", "NULL", "NAN"]
    )

    digits = (
        text.str.replace(r"\.0+$", "", regex=True)
        .str.lstrip("0")
    )

    valid = (
        ~missing
        & text.str.fullmatch(r"[0-9]+(?:\.0+)?").fillna(False)
        & digits.str.len().le(15)
        & digits.ne("")
    )

    return valid.fillna(False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output",
        default="analysis/outputs/crash_identifier_by_year.csv"
    )
    args = parser.parse_args()

    counts = {
        year: {"total": 0, "unidentified": 0}
        for year in range(2016, 2026)
    }

    input_rows = 0
    excluded_window = 0
    excluded_date = 0

    reader = pd.read_csv(
        args.input,
        usecols=["DOT_NUMBER", "REPORT_DATE"],
        dtype="string",
        chunksize=50000,
        keep_default_na=False,
    )

    for chunk in reader:
        input_rows += len(chunk)

        dates = pd.to_datetime(
            chunk["REPORT_DATE"],
            errors="coerce"
        )

        years = dates.dt.year

        excluded_date += int(years.isna().sum())

        in_window = years.between(2016, 2025).fillna(False)
        excluded_window += int(
            (years.notna() & ~in_window).sum()
        )

        retained = chunk.loc[in_window]
        retained_years = years.loc[in_window]

        valid_dot = clean_dot_numbers(retained["DOT_NUMBER"])

        for year in range(2016, 2026):
            year_mask = retained_years.eq(year)

            counts[year]["total"] += int(year_mask.sum())
            counts[year]["unidentified"] += int(
                (year_mask & ~valid_dot).sum()
            )

    rows = []

    for year, values in counts.items():
        total = values["total"]
        unidentified = values["unidentified"]

        rows.append({
            "YEAR": year,
            "TOTAL_CRASH_RECORDS": total,
            "UNIDENTIFIED_RECORDS": unidentified,
            "LINKABLE_RECORDS": total - unidentified,
            "UNIDENTIFIED_PERCENT": round(
                100 * unidentified / total, 2
            ) if total else 0,
        })

    result = pd.DataFrame(rows)

    total = int(result["TOTAL_CRASH_RECORDS"].sum())
    unidentified = int(result["UNIDENTIFIED_RECORDS"].sum())

    print("\nYearly crash identifier quality:")
    print(result.to_string(index=False))

    print("\nOverall summary:")
    print("Input records:", input_rows)
    print("Excluded invalid dates:", excluded_date)
    print("Excluded outside window:", excluded_window)
    print("Retained records:", total)
    print("Unidentified records:", unidentified)
    print("Unidentified percentage:", round(
        100 * unidentified / total, 2
    ))

    print("\nReconciliation:")
    print("Expected retained records: 1,868,397")
    print("Expected unidentified records: 401,528")

    if total != 1868397 or unidentified != 401528:
        print("WARNING: Counts do not match integration report.")
        print("Review date parsing and identifier rules.")
    else:
        print("PASS: Counts match integration report.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(output, index=False)
    print("\nSaved report:", output)


if __name__ == "__main__":
    main()