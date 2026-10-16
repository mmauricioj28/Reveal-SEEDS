"""
Multi-source FMCSA safety data pipeline (2016–2025).
Integrates Census, Crash, and Vehicle Inspection datasets on DOT_NUMBER
and serializes an analytics-ready Parquet file using pyarrow.
"""

from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_filepath(filename_stem: str) -> Path:
    """Resolve full dataset file if present, else fall back to sample."""
    full_path = DATA_DIR / f"{filename_stem}_File.csv"
    sample_path = DATA_DIR / f"{filename_stem}_Sample.csv"
    if full_path.exists():
        return full_path
    if sample_path.exists():
        return sample_path
    raise FileNotFoundError(f"Neither {full_path} nor {sample_path} was found.")


def canonicalize_dot(series: pd.Series) -> pd.Series:
    """Ensure DOT_NUMBER is uniform string integer across all sources."""
    numeric = pd.to_numeric(series, errors="coerce")
    return numeric.dropna().astype("int64").astype(str)


def process_census(census_path: Path) -> pd.DataFrame:
    """Load core carrier attributes from Census file using memory-efficient usecols."""
    print(f"Loading Census from: {census_path}")
    cols = ["DOT_NUMBER", "PHY_STATE", "PHY_COUNTRY", "POWER_UNITS", "TOTAL_DRIVERS"]

    df = pd.read_csv(
        census_path,
        usecols=lambda c: c.upper().strip() in cols,
        dtype=str,
        low_memory=False,
    )
    df.columns = [c.upper().strip() for c in df.columns]

    # Clean and canonicalize DOT_NUMBER
    df["DOT_NUMBER_CLEAN"] = canonicalize_dot(df["DOT_NUMBER"])
    df = df.dropna(subset=["DOT_NUMBER_CLEAN"])
    df["DOT_NUMBER"] = df["DOT_NUMBER_CLEAN"]
    df = df.drop(columns=["DOT_NUMBER_CLEAN"])

    # Explicitly cast numeric columns to numeric float (handles blanks/NaNs cleanly for Arrow)
    if "POWER_UNITS" in df.columns:
        df["POWER_UNITS"] = pd.to_numeric(df["POWER_UNITS"], errors="coerce")
    if "TOTAL_DRIVERS" in df.columns:
        df["TOTAL_DRIVERS"] = pd.to_numeric(df["TOTAL_DRIVERS"], errors="coerce")

    # Clean text columns
    for col in ["PHY_STATE", "PHY_COUNTRY"]:
        if col in df.columns:
            df[col] = df[col].astype("string")

    # Keep first registered entry per carrier
    df = df.drop_duplicates(subset=["DOT_NUMBER"], keep="first")
    return df


def process_crashes(crash_path: Path) -> pd.DataFrame:
    """Aggregate crashes, injuries, and fatalities (2016–2025) per DOT_NUMBER."""
    print(f"Loading Crashes from: {crash_path}")
    cols = ["DOT_NUMBER", "REPORT_DATE", "FATALITIES", "INJURIES"]

    df = pd.read_csv(
        crash_path,
        usecols=lambda c: c.upper().strip() in cols,
        dtype=str,
        low_memory=False,
    )
    df.columns = [c.upper().strip() for c in df.columns]

    df["DOT_NUMBER_CLEAN"] = canonicalize_dot(df["DOT_NUMBER"])
    df = df.dropna(subset=["DOT_NUMBER_CLEAN"])
    df["DOT_NUMBER"] = df["DOT_NUMBER_CLEAN"]
    df = df.drop(columns=["DOT_NUMBER_CLEAN"])

    # Filter to 2016-2025 window
    df["REPORT_DATE"] = pd.to_datetime(df["REPORT_DATE"], errors="coerce")
    df = df[(df["REPORT_DATE"].dt.year >= 2016) & (df["REPORT_DATE"].dt.year <= 2025)]

    df["FATALITIES"] = pd.to_numeric(df["FATALITIES"], errors="coerce").fillna(0)
    df["INJURIES"] = pd.to_numeric(df["INJURIES"], errors="coerce").fillna(0)

    crash_agg = (
        df.groupby("DOT_NUMBER")
        .agg(
            TOTAL_CRASHES=("REPORT_DATE", "count"),
            TOTAL_FATALITIES=("FATALITIES", "sum"),
            TOTAL_INJURIES=("INJURIES", "sum"),
        )
        .reset_index()
    )
    crash_agg["DOT_NUMBER"] = crash_agg["DOT_NUMBER"].astype(str)
    return crash_agg


def process_inspections(insp_path: Path) -> pd.DataFrame:
    """Aggregate vehicle & driver Out-Of-Service violations (2016–2025) per DOT_NUMBER."""
    print(f"Loading Inspections from: {insp_path}")
    cols = ["DOT_NUMBER", "INSP_DATE", "VEHICLE_OOS_TOTAL", "DRIVER_OOS_TOTAL"]

    df = pd.read_csv(
        insp_path,
        usecols=lambda c: c.upper().strip() in cols,
        dtype=str,
        low_memory=False,
    )
    df.columns = [c.upper().strip() for c in df.columns]

    df["DOT_NUMBER_CLEAN"] = canonicalize_dot(df["DOT_NUMBER"])
    df = df.dropna(subset=["DOT_NUMBER_CLEAN"])
    df["DOT_NUMBER"] = df["DOT_NUMBER_CLEAN"]
    df = df.drop(columns=["DOT_NUMBER_CLEAN"])

    # Filter to 2016-2025 window
    df["INSP_DATE"] = pd.to_datetime(df["INSP_DATE"], errors="coerce")
    df = df[(df["INSP_DATE"].dt.year >= 2016) & (df["INSP_DATE"].dt.year <= 2025)]

    df["VEHICLE_OOS_TOTAL"] = pd.to_numeric(df["VEHICLE_OOS_TOTAL"], errors="coerce").fillna(0)
    df["DRIVER_OOS_TOTAL"] = pd.to_numeric(df["DRIVER_OOS_TOTAL"], errors="coerce").fillna(0)

    insp_agg = (
        df.groupby("DOT_NUMBER")
        .agg(
            TOTAL_INSPECTIONS=("INSP_DATE", "count"),
            TOTAL_VEHICLE_OOS=("VEHICLE_OOS_TOTAL", "sum"),
            TOTAL_DRIVER_OOS=("DRIVER_OOS_TOTAL", "sum"),
        )
        .reset_index()
    )
    insp_agg["DOT_NUMBER"] = insp_agg["DOT_NUMBER"].astype(str)
    return insp_agg


def build_pipeline() -> Path:
    census_file = get_filepath("Company_Census")
    crash_file = get_filepath("Crash")
    insp_file = get_filepath("Vehicle_Inspection")

    census_df = process_census(census_file)
    crash_df = process_crashes(crash_file)
    insp_df = process_inspections(insp_file)

    # Left join to preserve all Census carriers
    merged = census_df.merge(crash_df, on="DOT_NUMBER", how="left")
    merged = merged.merge(insp_df, on="DOT_NUMBER", how="left")

    # Unreviewed carriers or those with no events get 0 for aggregated metrics
    metric_cols = [c for c in merged.columns if c.startswith("TOTAL_")]
    for col in metric_cols:
        merged[col] = merged[col].fillna(0).astype("int64")

    # Ensure DOT_NUMBER is explicitly string for Parquet
    merged["DOT_NUMBER"] = merged["DOT_NUMBER"].astype("string")

    parquet_out = OUTPUT_DIR / "carrier_safety_2016_2025.parquet"
    merged.to_parquet(parquet_out, engine="pyarrow", index=False)

    print("\nPipeline execution complete!")
    print(f"Artifact created at: {parquet_out}")
    print(f"Dimensions: {merged.shape[0]} rows x {merged.shape[1]} columns")
    print(f"Columns: {list(merged.columns)}")
    return parquet_out


if __name__ == "__main__":
    build_pipeline()