"""Analyze unidentified FMCSA crash records by reporting state."""

import argparse
import json
from pathlib import Path

import pandas as pd


def clean_dot_numbers(raw):
    """Replicate the integration pipeline's DOT-number validation."""
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


def clean_state_codes(raw):
    """Replicate the integration pipeline's location-code cleaning."""
    text = raw.fillna("").astype("string").str.strip().str.upper()

    missing = text.eq("") | text.isin(["N/A", "NULL", "NAN"])
    invalid = ~missing & ~text.str.fullmatch(r"[A-Z]{2}").fillna(False)

    return text.mask(missing, "missing").mask(invalid, "invalid")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze FMCSA crash identifier quality by state."
    )

    parser.add_argument("--input", required=True)

    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/crash_identifier_state"
    )

    parser.add_argument(
        "--min-records",
        type=int,
        default=1000,
        help="Minimum state records for comparison."
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    state_counts = {}

    input_rows = 0
    excluded_dates = 0
    excluded_window = 0

    reader = pd.read_csv(
        args.input,
        usecols=["DOT_NUMBER", "REPORT_DATE", "REPORT_STATE"],
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

        excluded_dates += int(years.isna().sum())

        in_window = years.between(2016, 2025).fillna(False)

        excluded_window += int(
            (years.notna() & ~in_window).sum()
        )

        retained = chunk.loc[in_window]

        if retained.empty:
            continue

        valid_dot = clean_dot_numbers(retained["DOT_NUMBER"])

        states = clean_state_codes(retained["REPORT_STATE"])

        grouped = pd.DataFrame({
            "REPORT_STATE": states,
            "UNIDENTIFIED": (~valid_dot).astype(int)
        })

        summary = grouped.groupby(
            "REPORT_STATE",
            dropna=False
        ).agg(
            TOTAL_RECORDS=("UNIDENTIFIED", "size"),
            UNIDENTIFIED_RECORDS=("UNIDENTIFIED", "sum")
        )

        for state, row in summary.iterrows():
            if state not in state_counts:
                state_counts[state] = {
                    "total": 0,
                    "unidentified": 0
                }

            state_counts[state]["total"] += int(
                row["TOTAL_RECORDS"]
            )

            state_counts[state]["unidentified"] += int(
                row["UNIDENTIFIED_RECORDS"]
            )

    rows = []

    for state, values in state_counts.items():
        total = values["total"]
        unidentified = values["unidentified"]

        rows.append({
            "REPORT_STATE": state,
            "TOTAL_CRASH_RECORDS": total,
            "UNIDENTIFIED_RECORDS": unidentified,
            "LINKABLE_RECORDS": total - unidentified,
            "UNIDENTIFIED_PERCENT": round(
                100 * unidentified / total, 2
            ) if total else 0
        })

    result = pd.DataFrame(rows)

    result = result.sort_values(
        "UNIDENTIFIED_PERCENT",
        ascending=False
    ).reset_index(drop=True)

    total = int(result["TOTAL_CRASH_RECORDS"].sum())
    unidentified = int(result["UNIDENTIFIED_RECORDS"].sum())

    overall_percent = (
        100 * unidentified / total if total else 0
    )

    print("\nFMCSA Crash Identifier Quality by Reporting State")
    print("=" * 55)

    print("\nOverall summary:")
    print("Input records:", input_rows)
    print("Excluded invalid dates:", excluded_dates)
    print("Excluded outside window:", excluded_window)
    print("Retained records:", total)
    print("Unidentified records:", unidentified)
    print("Overall unidentified percentage:",
          round(overall_percent, 2))

    print("\nReconciliation checks:")

    expected_total = 1868397
    expected_unidentified = 401528

    if (
        total == expected_total
        and unidentified == expected_unidentified
    ):
        print("PASS: Counts match integration validation report.")
    else:
        print("WARNING: Counts do not match integration report.")
        print("Expected retained:", expected_total)
        print("Expected unidentified:", expected_unidentified)

    result_path = output_dir / "crash_identifier_by_state.csv"
    result.to_csv(result_path, index=False)

    eligible = result[
        result["TOTAL_CRASH_RECORDS"] >= args.min_records
    ].copy()

    eligible["DIFFERENCE_FROM_OVERALL_PP"] = (
        eligible["UNIDENTIFIED_PERCENT"] - overall_percent
    ).round(2)

    eligible = eligible.sort_values(
        "UNIDENTIFIED_PERCENT",
        ascending=False
    )

    eligible_path = (
        output_dir / "state_identifier_comparison.csv"
    )

    eligible.to_csv(eligible_path, index=False)

    print("\nStates with highest unidentified percentages")
    print(f"(Minimum {args.min_records:,} records):")

    print(
        eligible[
            [
                "REPORT_STATE",
                "TOTAL_CRASH_RECORDS",
                "UNIDENTIFIED_RECORDS",
                "UNIDENTIFIED_PERCENT",
                "DIFFERENCE_FROM_OVERALL_PP"
            ]
        ].head(15).to_string(index=False)
    )

    print("\nStates with lowest unidentified percentages:")

    print(
        eligible[
            [
                "REPORT_STATE",
                "TOTAL_CRASH_RECORDS",
                "UNIDENTIFIED_RECORDS",
                "UNIDENTIFIED_PERCENT"
            ]
        ].tail(10).sort_values(
            "UNIDENTIFIED_PERCENT"
        ).to_string(index=False)
    )

    print("\nReports saved:")
    print(result_path)
    print(eligible_path)


if __name__ == "__main__":
    main()