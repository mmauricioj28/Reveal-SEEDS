
import pandas as pd
import requests
from pathlib import Path

# USDOT MCMIS Vehicle Inspection dataset
URL = "https://data.transportation.gov/resource/fx4q-ay7w.json"

# Analyzes all 12 months of 2025
YEAR = 2025
MONTHS = range(1, 13)

# Where the monthly results saved
OUTPUT = Path("analysis/outputs/mcmis_inspection_monthly_counts_2025.csv")


# Store the monthly results here
results = []

# Request the inspection count for each month
for month in MONTHS:
    month_str = f"{YEAR}{month:02d}"

    params = {
        "$select": "count(*) as inspections",
        "$where": f"starts_with(insp_date, '{month_str}')"
    }

    response = requests.get(URL, params=params, timeout=60)
    response.raise_for_status()

    count = int(response.json()[0]["inspections"])

    results.append({
        "year": YEAR,
        "month": month,
        "inspection_count": count
    })

    print(f"{YEAR}-{month:02d}: {count:,} inspections")


# Convert the monthly results into a DataFrame
df = pd.DataFrame(results)

# Calculate the total number of inspections in 2025
annual_total = df["inspection_count"].sum()

print("\nMonthly inspection summary:")
print(df.to_string(index=False))

print(f"\nTotal inspections in {YEAR}: {annual_total:,}")

# Create the output folder if it doesn't exist
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Save the monthly counts to CSV
df.to_csv(OUTPUT, index=False)

print(f"\nSaved monthly counts to: {OUTPUT}")
