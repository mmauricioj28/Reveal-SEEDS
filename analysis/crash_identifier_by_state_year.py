"""Analyze FMCSA crash identifier completeness by state and year."""

import argparse
from pathlib import Path

import pandas as pd


def valid_dot_numbers(raw):
    """Identify usable positive DOT numbers."""
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


def clean_states(raw):
    """Standardize reporting-state codes."""
    text = raw.fillna("").astype("string").str.strip().str.upper()

    missing = text.eq("") | text.isin(["N/A", "NULL", "NAN"])
    invalid = ~missing & ~text.str.fullmatch(r"[A-Z]{2}").fillna(False)

    return text.mask(missing, "missing").mask(invalid, "invalid")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/crash_identifier_state_year"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []

    reader = pd.read_csv(
        args.input,
        usecols=["DOT_NUMBER", "REPORT_DATE", "REPORT_STATE"],
        dtype="string",
        keep_default_na=False,
        chunksize=50000
    )

    for chunk in reader:
        dates = pd.to_datetime(
            chunk["REPORT_DATE"],
            errors="coerce"
        )

        years = dates.dt.year
        retained = chunk.loc[years.between(2016, 2025).fillna(False)].copy()

        if retained.empty:
            continue

        retained["YEAR"] = years.loc[retained.index].astype(int)
        retained["REPORT_STATE"] = clean_states(
            retained["REPORT_STATE"]
        )
        retained["UNIDENTIFIED"] = (
            ~valid_dot_numbers(retained["DOT_NUMBER"])
        ).astype(int)

        grouped = retained.groupby(
            ["YEAR", "REPORT_STATE"]
        ).agg(
            TOTAL_CRASH_RECORDS=("UNIDENTIFIED", "size"),
            UNIDENTIFIED_RECORDS=("UNIDENTIFIED", "sum")
        ).reset_index()

        summaries.append(grouped)

    combined = pd.concat(summaries, ignore_index=True)

    result = combined.groupby(
        ["YEAR", "REPORT_STATE"],
        as_index=False
    )[
        ["TOTAL_CRASH_RECORDS", "UNIDENTIFIED_RECORDS"]
    ].sum()

    result["LINKABLE_RECORDS"] = (
        result["TOTAL_CRASH_RECORDS"]
        - result["UNIDENTIFIED_RECORDS"]
    )

    result["UNIDENTIFIED_PERCENT"] = (
        100
        * result["UNIDENTIFIED_RECORDS"]
        / result["TOTAL_CRASH_RECORDS"]
    ).round(2)

    result = result.sort_values(["YEAR", "REPORT_STATE"])

    result.to_csv(
        output_dir / "crash_identifier_by_state_year.csv",
        index=False
    )

    yearly = result.groupby("YEAR", as_index=False)[
        ["TOTAL_CRASH_RECORDS", "UNIDENTIFIED_RECORDS"]
    ].sum()

    yearly["NATIONAL_UNIDENTIFIED_PERCENT"] = (
        100
        * yearly["UNIDENTIFIED_RECORDS"]
        / yearly["TOTAL_CRASH_RECORDS"]
    ).round(2)

    focus = result[
        result["REPORT_STATE"].isin(["TX", "NC", "NJ"])
    ].merge(
        yearly[["YEAR", "NATIONAL_UNIDENTIFIED_PERCENT"]],
        on="YEAR",
        how="left"
    )

    focus["DIFFERENCE_FROM_NATIONAL_PP"] = (
        focus["UNIDENTIFIED_PERCENT"]
        - focus["NATIONAL_UNIDENTIFIED_PERCENT"]
    ).round(2)

    focus.to_csv(
        output_dir / "focus_state_year_comparison.csv",
        index=False
    )

    total = int(result["TOTAL_CRASH_RECORDS"].sum())
    unidentified = int(result["UNIDENTIFIED_RECORDS"].sum())

    print("\nState-by-Year Crash Identifier Analysis")
    print("=" * 45)

    print("Retained crash records:", total)
    print("Unidentified records:", unidentified)
    print("State-year combinations:", len(result))

    if total == 1868397 and unidentified == 401528:
        print("PASS: Totals match integration validation.")
    else:
        print("WARNING: Totals do not match integration validation.")

    print("\nTexas, North Carolina, and New Jersey:")
    print(
        focus[
            [
                "YEAR",
                "REPORT_STATE",
                "TOTAL_CRASH_RECORDS",
                "UNIDENTIFIED_PERCENT",
                "NATIONAL_UNIDENTIFIED_PERCENT",
                "DIFFERENCE_FROM_NATIONAL_PP"
            ]
        ].sort_values(
            ["REPORT_STATE", "YEAR"]
        ).to_string(index=False)
    )

    print("\nReports saved to:", output_dir)


if __name__ == "__main__":
    main()