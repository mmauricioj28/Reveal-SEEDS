from pathlib import Path

import pandas as pd
import requests

URL = "https://data.transportation.gov/resource/fx4q-ay7w.json"
OUTPUT = Path("analysis/outputs/mcmis_inspection_annual_counts.csv")

session = requests.Session()
results = []

for year in range(2023, 2026):
    params = {
        "$select": "count(*)",
        "$where": f"starts_with(insp_date, '{year}')",
    }

    response = session.get(URL, params=params, timeout=120)
    response.raise_for_status()

    count = int(response.json()[0]["count"])
    results.append({
    "year": year,
    "inspection_records": count,
    "coverage_note": (
        "Partial year: data begins October 14"
        if year == 2023
        else "Full calendar year in available dataset"
    )
})

    print(f"{year}: {count:,}", flush=True)

df = pd.DataFrame(results)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)

print(f"\nTotal inspection records: {df['inspection_records'].sum():,}")
print(f"Saved to: {OUTPUT}")