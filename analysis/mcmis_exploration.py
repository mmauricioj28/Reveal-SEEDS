import pandas as pd

file_path = r"C:\Users\bulus\Downloads\Company_Census_File_20260929.csv"

# 2GB big file, so I'm just using a tiny sample for now to check some basics
df_sample = pd.read_csv(file_path, nrows=100)

print("Shape:", df_sample.shape)
print("\nColumns:")
print(df_sample.columns.tolist())

print("\nFirst 5 rows:")
print(df_sample.head())

selected_columns = [
    "DOT_NUMBER",
    "PHY_STATE",
    "CARRIER_OPERATION",
    "TRUCK_UNITS",
    "POWER_UNITS",
    "FLEETSIZE",
    "TOTAL_DRIVERS",
    "TOTAL_CDL",
    "MCS150_MILEAGE",
    "MCS150_MILEAGE_YEAR",
    "RECORDABLE_CRASH_RATE",
    "SAFETY_RATING",
    "REVIEW_DATE",
    "SAFETY_RATING_DATE"
]

missing_columns = [
    col for col in selected_columns
    if col not in df_sample.columns
]

if missing_columns:
    raise ValueError(
        f"Required columns missing from dataset: {missing_columns}"
    )

print("\nSelected variables:")
print(df_sample[selected_columns].head(10))

print("\nMissing values in selected variables:")
print(df_sample[selected_columns].isna().sum())   #yikes, RECORDABLE_CRASH_RATE has 99/100 missing in this small sample

print("\nData types of selected variables:")
print(df_sample[selected_columns].dtypes)

print("\nCarrier operation values:")
print(df_sample["CARRIER_OPERATION"].value_counts(dropna=False))

print("\nFleet size values:")
print(df_sample["FLEETSIZE"].value_counts(dropna=False))

print("\nSafety rating values:")
print(df_sample["SAFETY_RATING"].value_counts(dropna=False))

print("\nPhysical state values:")
print(df_sample["PHY_STATE"].value_counts(dropna=False))

#10/9 - Extended exploration of first 10,000 census records
import pandas as pd

safety_columns = [
    "DOT_NUMBER",
    "PHY_STATE",
    "CARRIER_OPERATION",
    "FLEETSIZE",
    "SAFETY_RATING",
    "RECORDABLE_CRASH_RATE",
    "REVIEW_DATE",
    "SAFETY_RATING_DATE"
]

df_large = pd.read_csv(
    file_path,
    usecols=lambda column: column in safety_columns,
    nrows=10000,
    low_memory=False
)

print("/n Extended MCMIS Exploration")
print("Rows analyzed:", len(df_large))

print("\nColumns available:")
print(df_large.columns.tolist())

missing_summary = pd.DataFrame({
    "Missing Count": df_large.isna().sum(),
    "Missing %": (df_large.isna().mean() * 100).round(2)
}).sort_values("Missing %", ascending=False)

print("\nMissing-data summary:")
print(missing_summary)

for column in ["SAFETY_RATING", "CARRIER_OPERATION", "FLEETSIZE"]:
    if column in df_large.columns:
        print(f"\n{column} distribution:")
        print(df_large[column].value_counts(dropna=False))

missing_summary.to_csv("analysis/mcmis_safety_missingness.csv")
print("\nSaved analysis/mcmis_safety_missingness.csv")