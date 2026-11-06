import pandas as pd
import argparse
from pathlib import Path

# Fleet size groups
fleet_bins = [-0.1, 0, 1, 5, 20, 100, 1000, float("inf")]
fleet_labels = ["Zero", "1 unit", "2-5", "6-20", "21-100",
                "101-1000", "Over 1000"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-dir", default="analysis/outputs/integrated_eda")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load the integrated data
    print("Loading data...")

    safety = pd.read_parquet(input_dir / "carrier_safety_2016_2025.parquet")
    carriers = pd.read_parquet(input_dir / "carriers.parquet")
    monthly = pd.read_parquet(input_dir / "monthly_activity.parquet")

    # Annual crash and inspection trends
    annual_cols = [
        "TOTAL_CRASHES", "TOTAL_INSPECTIONS",
        "TOTAL_FATALITIES", "TOTAL_INJURIES",
        "TOTAL_VIOLATIONS", "TOTAL_OOS"
    ]

    annual = safety.groupby("YEAR")[annual_cols].sum(min_count=1)
    annual.to_csv(output_dir / "annual_safety_trends.csv")

    print("\nAnnual trends:")
    print(annual)

    # Monthly crash and inspection counts
    for source in ["crash", "inspection"]:
        data = monthly[monthly["source"] == source]

        counts = data.groupby(["YEAR", "MONTH"])["record_count"].sum()
        counts.to_csv(output_dir / f"monthly_{source}_trends.csv")

        print(f"\n{source.title()} monthly counts:")
        print(counts)

    # Fleet size distribution
    carriers["POWER_UNITS"] = pd.to_numeric(
        carriers["POWER_UNITS"], errors="coerce"
    )

    carriers["fleet_group"] = pd.cut(
        carriers["POWER_UNITS"],
        bins=fleet_bins,
        labels=fleet_labels
    )

    carriers["fleet_group"] = (
        carriers["fleet_group"]
        .cat.add_categories(["Missing"])
        .fillna("Missing")
    )

    fleet_counts = carriers["fleet_group"].value_counts(sort=False)

    fleet_summary = pd.DataFrame({
        "carriers": fleet_counts,
        "percentage": (fleet_counts / len(carriers) * 100).round(2)
    })

    fleet_summary.to_csv(output_dir / "fleet_size_distribution.csv")

    print("\nFleet size distribution:")
    print(fleet_summary)

    # Check how many carriers have recorded crashes or inspections
    matched = safety[safety["census_matched"] == True]

    carrier_events = matched.groupby("DOT_NUMBER").agg(
        total_crashes=("TOTAL_CRASHES", "sum"),
        total_inspections=("TOTAL_INSPECTIONS", "sum")
    ).reset_index()

    combined = carriers[["DOT_NUMBER", "fleet_group"]].merge(
        carrier_events,
        on="DOT_NUMBER",
        how="left",
        validate="one_to_one"
    )

    combined[["total_crashes", "total_inspections"]] = (
        combined[["total_crashes", "total_inspections"]].fillna(0)
    )

    combined["has_crash"] = combined["total_crashes"] > 0
    combined["has_inspection"] = combined["total_inspections"] > 0

    fleet_safety = combined.groupby("fleet_group", observed=True).agg(
        carriers=("DOT_NUMBER", "size"),
        carriers_with_crashes=("has_crash", "sum"),
        carriers_with_inspections=("has_inspection", "sum")
    )

    fleet_safety["crash_pct"] = (
        fleet_safety["carriers_with_crashes"] /
        fleet_safety["carriers"] * 100
    ).round(2)

    fleet_safety["inspection_pct"] = (
        fleet_safety["carriers_with_inspections"] /
        fleet_safety["carriers"] * 100
    ).round(2)

    fleet_safety.to_csv(output_dir / "fleet_safety_summary.csv")

    print("\nFleet safety summary:")
    print(fleet_safety)

    # Check missing, zero, and unusually large fleet sizes
    power_units = carriers["POWER_UNITS"]

    quality = {
        "total_carriers": len(carriers),
        "missing_power_units": power_units.isna().sum(),
        "zero_power_units": (power_units == 0).sum(),
        "over_1000_units": (power_units > 1000).sum(),
        "over_10000_units": (power_units > 10000).sum(),
        "max_power_units": power_units.max()
    }

    # Check how many months of inspection data are available each year
    inspections = monthly[monthly["source"] == "inspection"]
    months = inspections.groupby("YEAR")["MONTH"].nunique()

    for year, count in months.items():
        quality[f"inspection_months_{year}"] = count

    quality_df = pd.DataFrame(
        list(quality.items()), columns=["metric", "value"]
    )

    quality_df.to_csv(output_dir / "data_quality_summary.csv", index=False)

    print("\nData quality:")
    print(quality_df)

    print("\nDone! Results saved to:", output_dir)


if __name__ == "__main__":
    main()