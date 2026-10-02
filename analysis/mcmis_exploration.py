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