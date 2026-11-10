

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Input and output paths
INPUT = Path(r"C:\Users\bulus\Downloads\Company_Census_File_20260929.csv")
OUTPUT = Path("analysis/outputs/census_selected.parquet")

# Selected variables from the MCMIS Census data dictionary
COLUMNS = [
    "DOT_NUMBER",
    "STATUS_CODE",
    "CARRIER_OPERATION",
    "PHY_STATE",
    "FLEETSIZE",
    "POWER_UNITS",
    "TOTAL_DRIVERS",
    "HM_Ind",
    "MCS150_DATE",
    "CLASSDEF",
    "TRUCK_UNITS",
    "MCS150_MILEAGE",
    "MCS150_MILEAGE_YEAR",
    "SAFETY_RATING",
    "SAFETY_RATING_DATE",
    "REVIEW_DATE",
    "RECORDABLE_CRASH_RATE",
    "CRGO_LIQGAS",
    "CRGO_CHEM",
]

CHUNK_SIZE = 100_000

# Create output directory if needed
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Verify input exists
if not INPUT.exists():
    raise FileNotFoundError(f"Input file not found: {INPUT}")

print("Processing Census data in chunks...", flush=True)

writer = None
total_rows = 0

try:
    for chunk in pd.read_csv(
        INPUT,
        usecols=COLUMNS,
        dtype=str,
        chunksize=CHUNK_SIZE,
        low_memory=False,
    ):
        # Preserve consistent column order
        chunk = chunk[COLUMNS]

        # Convert chunk to an Arrow table
        table = pa.Table.from_pandas(
            chunk,
            preserve_index=False,
        )

        # Initialize Parquet writer on the first chunk
        if writer is None:
            writer = pq.ParquetWriter(
                str(OUTPUT),
                table.schema,
                compression="snappy",
            )

        # Write chunk without loading the full dataset
        writer.write_table(table)

        total_rows += len(chunk)

        print(f"Processed {total_rows:,} rows", flush=True)

finally:
    if writer is not None:
        writer.close()

# Verify output metadata without loading all rows
parquet_file = pq.ParquetFile(OUTPUT)

print("\nProcessing complete!")
print(f"Source rows processed: {total_rows:,}")
print(f"Parquet rows: {parquet_file.metadata.num_rows:,}")
print(f"Columns: {parquet_file.metadata.num_columns}")
print(f"Saved: {OUTPUT}")
print(f"File size: {OUTPUT.stat().st_size / (1024**2):.2f} MB")

assert parquet_file.metadata.num_rows == total_rows, (
    "Row count mismatch between CSV and Parquet!"
)

assert parquet_file.metadata.num_columns == len(COLUMNS), (
    "Column count mismatch!"
)

print("Validation passed!")
