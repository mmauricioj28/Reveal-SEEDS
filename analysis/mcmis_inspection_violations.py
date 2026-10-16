
import pandas as pd
import requests
from pathlib import Path

# USDOT MCMIS Vehicle Inspection dataset
URL = "https://data.transportation.gov/resource/fx4q-ay7w.json"

# Start with 1,000 inspection records from 2025
YEAR = 2025
LIMIT = 1000

# Where we save  results
OUTPUT = Path("analysis/outputs/mcmis_inspection_violations_2025.csv")


# Requests inspection records from 2025
params = {
    "$select": "inspection_id,insp_date,viol_total,oos_total",
    "$where": f"starts_with(insp_date, '{YEAR}')",
    "$limit": LIMIT
}

response = requests.get(URL, params=params, timeout=60)
response.raise_for_status()

# Converting the API response into a pandas DataFrame
df = pd.DataFrame(response.json())

print(f"Downloaded {len(df)} inspection records from {YEAR}")
print(df.head())


# Converts violation columns from text to numbers
df["viol_total"] = pd.to_numeric(df["viol_total"], errors="coerce")
df["oos_total"] = pd.to_numeric(df["oos_total"], errors="coerce")

# Checks for missing values
print("\nMissing values:")
print(df[["viol_total", "oos_total"]].isna().sum())

# Calculating violation totals
print("\nViolation summary:")
print("Total violations:", df["viol_total"].sum())
print("Total OOS violations:", df["oos_total"].sum())

# Calculating averages per inspection
print("Average violations per inspection:", round(df["viol_total"].mean(), 2))
print("Average OOS violations per inspection:", round(df["oos_total"].mean(), 2))


# summary table
summary = pd.DataFrame([{
    "year": YEAR,
    "sample_size": len(df),
    "total_violations": df["viol_total"].sum(),
    "total_oos_violations": df["oos_total"].sum(),
    "avg_violations": df["viol_total"].mean(),
    "avg_oos_violations": df["oos_total"].mean(),
    "missing_violations": df["viol_total"].isna().sum(),
    "missing_oos": df["oos_total"].isna().sum()
}])

# Saving the summary as a CSV
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
summary.to_csv(OUTPUT, index=False)

print(f"\nSaved summary to: {OUTPUT}")
