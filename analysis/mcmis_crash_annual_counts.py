
from pathlib import Path

import pandas as pd
import requests

URL = "https://data.transportation.gov/resource/aayw-vxb3.json"
OUTPUT = Path("analysis/outputs/mcmis_crash_annual_counts.csv")

session = requests.Session()
results = []

for year in range(2015, 2026):
    params = {
        "$select": "count(*)",
        "$where": f"starts_with(report_date, '{year}')",
    }

    response = session.get(URL, params=params, timeout=120)
    response.raise_for_status()

    count = int(response.json()[0]["count"])
    results.append({"year": year, "crash_records": count})

    print(f"{year}: {count:,}", flush=True)

df = pd.DataFrame(results)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(OUTPUT, index=False)

print(f"\nTotal records: {df['crash_records'].sum():,}")
print(f"Saved to: {OUTPUT}")
