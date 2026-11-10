
import pandas as pd
from collections import Counter
from pathlib import Path

import sys

file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/Company_Census_File.csv")
#file_path = Path(r"C:\Users\bulus\Downloads\Company_Census_File_20260929.csv")

columns = [
    "DOT_NUMBER",
    "PHY_STATE",
    "CARRIER_OPERATION",
    "FLEETSIZE",
    "SAFETY_RATING",
    "RECORDABLE_CRASH_RATE",
    "REVIEW_DATE",
    "SAFETY_RATING_DATE"
]

missing_counts = Counter()
rating_counts = Counter()
total_rows = 0

for chunk_number, chunk in enumerate(
    pd.read_csv(
        file_path,
        usecols=columns,
        chunksize=100_000,
        low_memory=False
    ),
    start=1
):
    total_rows += len(chunk)

    missing_counts.update(chunk.isna().sum().to_dict())
    rating_counts.update(
        chunk["SAFETY_RATING"].fillna("Missing").value_counts().to_dict()
    )

    print(f"Chunk {chunk_number}: {total_rows:,} rows processed")

summary = pd.DataFrame({
    "Column": columns,
    "Missing Count": [missing_counts[col] for col in columns],
    "Missing %": [
        round(missing_counts[col] / total_rows * 100, 2)
        for col in columns
    ]
})

print("\nFULL DATASET RESULTS")
print(f"Total rows: {total_rows:,}")
print("\nMissing-data summary:")
print(summary.to_string(index=False))

print("\nSafety rating distribution:")
for rating, count in rating_counts.most_common():
    print(f"{rating}: {count:,}")

output_dir = Path("analysis/outputs")
output_dir.mkdir(parents=True, exist_ok=True)

summary.to_csv(output_dir / "full_safety_missingness.csv", index=False)

pd.DataFrame(
    rating_counts.items(),
    columns=["Safety Rating", "Count"]
).to_csv(output_dir / "full_safety_ratings.csv", index=False)

print("\nReports saved to analysis/outputs/")
