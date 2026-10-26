import argparse
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(
        description="Investigate FMCSA Census fleet-size data quality"
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output-dir",
        default="analysis/outputs/fleet_quality"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load only the columns needed for this analysis
    print("Loading Census carrier data...")

    carriers = pd.read_parquet(
        args.input,
        columns=["DOT_NUMBER", "POWER_UNITS", "TOTAL_DRIVERS"]
    )

    for column in ["POWER_UNITS", "TOTAL_DRIVERS"]:
        carriers[column] = pd.to_numeric(
            carriers[column], errors="coerce"
        )

    # Identify carriers reporting unusually large fleets
    outliers = carriers.loc[
        carriers["POWER_UNITS"] > 10000
    ].copy()

    # Calculate ratios only when the driver count is positive
    outliers["units_per_driver"] = (
        outliers["POWER_UNITS"]
        / outliers["TOTAL_DRIVERS"].where(
            outliers["TOTAL_DRIVERS"] > 0
        )
    )

    # Flag potential reporting inconsistencies
    outliers["missing_drivers"] = (
        outliers["TOTAL_DRIVERS"].isna()
    )

    outliers["zero_drivers"] = (
        outliers["TOTAL_DRIVERS"] == 0
    )

    outliers["fewer_than_100_drivers"] = (
        outliers["TOTAL_DRIVERS"] < 100
    )

    outliers["over_100_units_per_driver"] = (
        outliers["units_per_driver"] > 100
    )

    # Summarize the identified records
    summary = {
        "total_carriers": len(carriers),
        "carriers_over_10000_units": len(outliers),
        "outliers_fewer_than_100_drivers": int(
            outliers["fewer_than_100_drivers"].sum()
        ),
        "outliers_zero_drivers": int(
            outliers["zero_drivers"].sum()
        ),
        "outliers_missing_drivers": int(
            outliers["missing_drivers"].sum()
        ),
        "outliers_over_100_units_per_driver": int(
            outliers["over_100_units_per_driver"].sum()
        ),
        "median_outlier_power_units": outliers[
            "POWER_UNITS"
        ].median(),
        "median_outlier_drivers": outliers[
            "TOTAL_DRIVERS"
        ].median(),
        "max_power_units": carriers["POWER_UNITS"].max()
    }

    summary_df = pd.DataFrame(
        list(summary.items()),
        columns=["metric", "value"]
    )

    # Group the unusually large fleet sizes
    bins = [
        10000, 50000, 100000,
        500000, 1000000, float("inf")
    ]

    labels = [
        "10k-50k",
        "50k-100k",
        "100k-500k",
        "500k-1M",
        "Over 1M"
    ]

    outliers["fleet_size_range"] = pd.cut(
        outliers["POWER_UNITS"],
        bins=bins,
        labels=labels
    )

    distribution = (
        outliers["fleet_size_range"]
        .value_counts(sort=False)
        .rename_axis("fleet_size_range")
        .reset_index(name="carriers")
    )

    # Export results without modifying source records
    summary_df.to_csv(
        output_dir / "fleet_quality_summary.csv",
        index=False
    )

    distribution.to_csv(
        output_dir / "fleet_outlier_distribution.csv",
        index=False
    )

    outliers.sort_values(
        "POWER_UNITS", ascending=False
    ).to_csv(
        output_dir / "flagged_fleet_records.csv",
        index=False
    )

    print("\nFleet-size quality summary:")
    print(summary_df.to_string(index=False))

    print("\nOutlier distribution:")
    print(distribution.to_string(index=False))

    print("\nResults saved to:", output_dir)


if __name__ == "__main__":
    main()