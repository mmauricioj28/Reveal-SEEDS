"""Explore FMCSA crash activity by Census-reported fleet size.

Important:
- Census fleet characteristics represent a snapshot.
- Historical fleet sizes may have differed.
- Results describe crash activity, not crash risk.
"""

import argparse
from pathlib import Path

import pandas as pd


FLEET_LABELS = [
    "Zero reported",
    "Very small (1-10)",
    "Small (11-50)",
    "Medium (51-100)",
    "Large (101-500)",
    "Very large (501+)",
    "Missing",
]


def categorize_fleet_size(values):
    """Assign exploratory fleet-size categories."""
    sizes = pd.to_numeric(values, errors="coerce")

    categories = pd.Series(
        "Missing",
        index=values.index,
        dtype="string",
    )

    categories.loc[sizes == 0] = "Zero reported"
    categories.loc[sizes.between(1, 10)] = "Very small (1-10)"
    categories.loc[sizes.between(11, 50)] = "Small (11-50)"
    categories.loc[sizes.between(51, 100)] = "Medium (51-100)"
    categories.loc[sizes.between(101, 500)] = "Large (101-500)"
    categories.loc[sizes >= 501] = "Very large (501+)"

    return categories


def main():
    parser = argparse.ArgumentParser(
        description="Explore crash activity by Census fleet size."
    )

    parser.add_argument("--input", required=True)

    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/fleet_size_crash_eda",
    )

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    columns = [
        "DOT_NUMBER",
        "YEAR",
        "census_matched",
        "POWER_UNITS",
        "TOTAL_CRASHES",
    ]

    data = pd.read_parquet(args.input, columns=columns)

    input_rows = len(data)

    # Ms. Cabrera requested Census-matched records for
    # comparisons based on carrier characteristics:
    matched = data.loc[data["census_matched"] == 1].copy()

    excluded_unmatched_rows = input_rows - len(matched)

    matched["POWER_UNITS"] = pd.to_numeric(
        matched["POWER_UNITS"],
        errors="coerce",
    )

    matched["TOTAL_CRASHES"] = pd.to_numeric(
        matched["TOTAL_CRASHES"],
        errors="coerce",
    )

    matched["FLEET_CATEGORY"] = categorize_fleet_size(
        matched["POWER_UNITS"]
    )

    missing_fleet_rows = int(
        matched["POWER_UNITS"].isna().sum()
    )

    zero_fleet_rows = int(
        (matched["POWER_UNITS"] == 0).sum()
    )

    missing_crash_rows = int(
        matched["TOTAL_CRASHES"].isna().sum()
    )

    # Preserve missing and zero fleet categories
    # rather than silently dropping these records
    matched["HAS_CRASH"] = (
        matched["TOTAL_CRASHES"] > 0
    ).astype(int)

    grouped = matched.groupby(
        ["YEAR", "FLEET_CATEGORY"],
        dropna=False,
        observed=True,
    ).agg(
        CARRIER_YEAR_RECORDS=("DOT_NUMBER", "size"),
        UNIQUE_CARRIERS=("DOT_NUMBER", "nunique"),
        TOTAL_CRASHES=("TOTAL_CRASHES", "sum"),
        CARRIER_YEARS_WITH_CRASH=("HAS_CRASH", "sum"),
    ).reset_index()

    grouped["PERCENT_WITH_CRASH"] = (
        100
        * grouped["CARRIER_YEARS_WITH_CRASH"]
        / grouped["CARRIER_YEAR_RECORDS"]
    ).round(2)

    grouped["CRASHES_PER_CARRIER_YEAR"] = (
        grouped["TOTAL_CRASHES"]
        / grouped["CARRIER_YEAR_RECORDS"]
    ).round(3)

    grouped["FLEET_CATEGORY"] = pd.Categorical(
        grouped["FLEET_CATEGORY"],
        categories=FLEET_LABELS,
        ordered=True,
    )

    grouped = grouped.sort_values(
        ["YEAR", "FLEET_CATEGORY"]
    )

    yearly_path = output_dir / "fleet_size_crashes_by_year.csv"
    grouped.to_csv(yearly_path, index=False)

    overall = matched.groupby(
        "FLEET_CATEGORY",
        dropna=False,
    ).agg(
        CARRIER_YEAR_RECORDS=("DOT_NUMBER", "size"),
        UNIQUE_CARRIERS=("DOT_NUMBER", "nunique"),
        TOTAL_CRASHES=("TOTAL_CRASHES", "sum"),
        CARRIER_YEARS_WITH_CRASH=("HAS_CRASH", "sum"),
    ).reset_index()

    overall["PERCENT_WITH_CRASH"] = (
        100
        * overall["CARRIER_YEARS_WITH_CRASH"]
        / overall["CARRIER_YEAR_RECORDS"]
    ).round(2)

    overall["CRASHES_PER_CARRIER_YEAR"] = (
        overall["TOTAL_CRASHES"]
        / overall["CARRIER_YEAR_RECORDS"]
    ).round(3)

    overall["FLEET_CATEGORY"] = pd.Categorical(
        overall["FLEET_CATEGORY"],
        categories=FLEET_LABELS,
        ordered=True,
    )

    overall = overall.sort_values("FLEET_CATEGORY")

    overall_path = output_dir / "fleet_size_crashes_overall.csv"
    overall.to_csv(overall_path, index=False)

    # Check that aggregation preserves all matched rows.
    grouped_rows = int(grouped["CARRIER_YEAR_RECORDS"].sum())
    overall_rows = int(overall["CARRIER_YEAR_RECORDS"].sum())

    source_crashes = matched["TOTAL_CRASHES"].sum()
    grouped_crashes = grouped["TOTAL_CRASHES"].sum()
    overall_crashes = overall["TOTAL_CRASHES"].sum()

    rows_pass = (
        grouped_rows == len(matched)
        and overall_rows == len(matched)
    )

    crashes_pass = (
        source_crashes == grouped_crashes
        and source_crashes == overall_crashes
    )

    print("\nFMCSA Fleet-Size Crash EDA")
    print("=" * 55)

    print("\nDataset summary:")
    print("Input carrier-year rows:", input_rows)
    print("Census-matched rows:", len(matched))
    print("Excluded unmatched carrier-year rows:",
          excluded_unmatched_rows)
    print("Missing fleet-size rows:", missing_fleet_rows)
    print("Zero fleet-size rows:", zero_fleet_rows)
    print("Missing crash-count rows:", missing_crash_rows)

    print("\nReconciliation checks:")
    print("Carrier-year rows:",
          "PASS" if rows_pass else "FAIL")
    print("Total crashes:",
          "PASS" if crashes_pass else "FAIL")

    print("\nOverall crash activity by fleet size:")
    print(overall.to_string(index=False))

    print("\nReports saved:")
    print(yearly_path)
    print(overall_path)

    print("\nImportant limitations:")
    print(
        "- Fleet sizes come from a Census snapshot "
        "and may differ in historical years."
    )
    print(
        "- Unmatched carrier-year rows are excluded "
        "from carrier-characteristic comparisons."
    )
    print(
        "- Missing and zero fleet sizes are reported "
        "as separate exploratory categories."
    )
    print(
        "- Crash counts are descriptive and are not "
        "adjusted for mileage or exposure."
    )


if __name__ == "__main__":
    main()