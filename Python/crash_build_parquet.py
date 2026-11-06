"""Step 2 of the Crash pipeline: clean the raw Crash CSVs and split them into relational Parquet tables.

Input : FMCSA_data_raw/crash_parquet/crash_*.parquet  (from crash_download.py)
        Census 2020 county FIPS list (read from census.gov, used for dim_state / dim_county)
Output: FMCSA_data_processed/crash/*.parquet  + _build_report.txt

Run from the repo root:  python Python/crash_build_parquet.py

Grain of the raw file: ONE ROW PER COMMERCIAL MOTOR VEHICLE (CMV) IN A CRASH.
  crash_id       -> unique per row (vehicle-in-crash record)
  report_number  -> shared by every CMV in the same crash (state prefix + 10 chars)
Crash-level fields (date, location, weather, fatalities, injuries...) are repeated on every
vehicle row, so summing fatalities over raw rows double counts multi-CMV crashes.

Tables written (see sql/crash_schema.sql for keys):
  crash            1 row per crash (crash_key)             -> counts, severity, conditions, place, time
  crash_vehicle    1 row per CMV in a crash (crash_id)     -> vehicle type, cargo body, hazmat, carrier DOT#
  crash_carrier    1 row per CMV in a crash (crash_id)     -> carrier as written on the crash report
  crash_event      1 row per crash event per CMV           -> sequence of harmful events
  agg_state_year   dashboard-ready state x year rollup
  agg_state_month  dashboard-ready state x month rollup
  dim_*            code lookups from the MCMIS Crash File Data Dictionary (Rev05, 2025-11-04)
"""
from datetime import date
from pathlib import Path

import pandas as pd

RAW_DIR = Path("FMCSA_data_raw") / "crash_parquet"
COUNTY_URL = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"
OUT_DIR = Path("FMCSA_data_processed") / "crash"
MIN_DATE = pd.Timestamp("2015-01-01")
MAX_DATE = pd.Timestamp(date.today())

STR = "string[pyarrow]"
report = []  # lines for _build_report.txt


def log(msg=""):
    print(msg, flush=True)
    report.append(str(msg))


# lookups (data dictionary)
LOOKUPS = {
    "dim_trafficway": {1: "Two-way, not divided", 2: "Two-way, divided, unprotected median",
                       3: "Two-way, divided, positive median barrier", 4: "One-way, not divided",
                       98: "Not reported", 99: "Unknown"},
    "dim_access_control": {1: "Full access control", 2: "Partial access control", 3: "No access control"},
    "dim_road_surface": {1: "Dry", 2: "Wet", 3: "Water (standing, moving)", 4: "Snow", 5: "Slush", 6: "Ice",
                         7: "Sand, mud, dirt, oil or gravel", 8: "Other", 9: "Unknown or blank"},
    "dim_weather": {1: "No adverse condition", 2: "Rain", 3: "Sleet, hail", 4: "Snow", 5: "Fog",
                    6: "Blowing sand, soil, dirt, or snow", 7: "Severe crosswinds", 8: "Other",
                    9: "Unknown or blank"},
    "dim_light": {1: "Daylight", 2: "Dark - not lighted", 3: "Dark - lighted", 4: "Dark - unknown roadway lighting",
                  5: "Dawn", 6: "Dusk", 8: "Other", 9: "Unknown or blank"},
    "dim_cargo_body": {1: "Bus (9-15 seats)", 2: "Bus (>15 seats)", 3: "Van/enclosed box", 4: "Cargo tank",
                       5: "Flatbed", 6: "Dump", 7: "Concrete mixer", 8: "Auto transporter", 9: "Garbage/refuse",
                       10: "Grain, chips, gravel", 11: "Pole", 12: "Not applicable", 13: "Intermodal",
                       14: "Logging", 15: "Vehicle towing another vehicle", 98: "Other"},
    "dim_gvw_rating": {1: "<= 10,000 lbs", 2: "10,001-26,000 lbs", 3: "> 26,000 lbs"},
    "dim_vehicle_config": {1: "Passenger car (HM placard)", 2: "Light truck (HM placard)", 3: "Bus (9-15 seats)",
                           4: "Bus (>15 seats)", 5: "Single-unit truck (2 axle, 6 tire)",
                           6: "Single-unit truck (3+ axles)", 7: "Truck/trailer", 8: "Truck tractor (bobtail)",
                           9: "Tractor/semitrailer", 10: "Tractor/double", 11: "Tractor/triple",
                           99: "Unknown heavy truck >10,000 lbs"},
    "dim_event": {1: "Non-collision: ran off road", 2: "Non-collision: jackknife", 3: "Non-collision: overturn (rollover)",
                  4: "Non-collision: downhill runaway", 5: "Non-collision: cargo loss or shift",
                  6: "Non-collision: explosion or fire", 7: "Non-collision: separation of units",
                  8: "Non-collision: cross median/centerline", 9: "Non-collision: equipment failure",
                  10: "Non-collision: other", 11: "Non-collision: unknown", 12: "Collision: pedestrian",
                  13: "Collision: motor vehicle in transport", 14: "Collision: parked motor vehicle",
                  15: "Collision: train", 16: "Collision: pedalcycle", 17: "Collision: animal",
                  18: "Collision: fixed object", 19: "Collision: work zone maintenance equipment",
                  20: "Collision: other movable object", 21: "Collision: unknown movable object", 98: "Other"},
}
TEXT_LOOKUPS = {
    "dim_ci_status": {"C": "Complete", "H": "FMCSA hold", "I": "Intrastate", "N": "Non-match",
                      "P": "Potential resolution", "T": "Sent to census search", "U": "Initial upload",
                      "X": "Non motor carrier"},
    "dim_carrier_interstate": {"Y": "Interstate", "N": "Intrastate", "X": "Non motor carrier"},
    "dim_truck_bus": {"T": "Truck", "B": "Bus"},
}
CODE_DIMS = {"trafficway_id": "dim_trafficway", "access_control_id": "dim_access_control",
             "road_surface_condition_id": "dim_road_surface", "weather_condition_id": "dim_weather",
             "light_condition_id": "dim_light", "cargo_body_type_id": "dim_cargo_body",
             "gvw_rating_id": "dim_gvw_rating", "vehicle_configuration_id": "dim_vehicle_config"}
TEXT_CODE_DIMS = {"ci_status_code": "dim_ci_status", "crash_carrier_interstate": "dim_carrier_interstate",
                  "truck_bus_ind": "dim_truck_bus"}
STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


DATE_ONLY = ["report_date", "report_month_start", "final_status_date"]


def write(df, name):
    df = df.copy()
    for c in DATE_ONLY:  # write as SQL DATE instead of TIMESTAMP
        if c in df.columns:
            df[c] = df[c].dt.date
    df.to_parquet(OUT_DIR / f"{name}.parquet", index=False)
    log(f"  wrote {name:22s} {len(df):>10,} rows  {df.shape[1]:>3} cols")


def yn(s):
    """'Y'/'N' text -> nullable boolean (anything else -> NA)."""
    return s.str.upper().map({"Y": True, "N": False}).astype("boolean")


def to_int(s, dtype="Int32"):
    return pd.to_numeric(s, errors="coerce").astype(dtype)


def to_ts(s, fmt):
    return pd.to_datetime(s, format=fmt, errors="coerce")


#1. load
def load_raw():
    files = sorted(RAW_DIR.glob("crash_*.parquet"))
    if not files:
        raise SystemExit(f"No parquet files in {RAW_DIR} - run Python/crash_download.py first")
    df = pd.concat((pd.read_parquet(f).astype(STR) for f in files), ignore_index=True)
    for c in df.columns:  # trim + blank -> NA
        df[c] = df[c].str.strip().replace("", pd.NA)
    log(f"[1] Loaded {len(df):,} raw vehicle rows from {len(files)} files")
    return df


# 2. clean / type
def load_counties():
    return pd.read_csv(COUNTY_URL, sep="|", dtype=str)


def clean(df, counties):
    log("\n[2] Clean + type")
    dupes = df.duplicated("crash_id").sum()
    log(f"  duplicate crash_id rows dropped: {dupes:,}")
    df = df.drop_duplicates("crash_id")

    df["crash_id"] = to_int(df["crash_id"], "Int64")
    df["report_date"] = to_ts(df["report_date"], "%Y%m%d")
    bad = ~df["report_date"].between(MIN_DATE, MAX_DATE)
    log(f"  rows outside {MIN_DATE.date()}..{MAX_DATE.date()} or unparseable report_date dropped: {bad.sum():,}")
    df = df[~bad].copy()

    # report_time is HHMM military; keep only valid times
    t = to_int(df["report_time"], "Int32")
    valid_t = t.between(0, 2359) & ((t % 100) < 60)
    log(f"  invalid report_time set to NA: {(~valid_t.fillna(False)).sum() - t.isna().sum():,} "
        f"(plus {t.isna().sum():,} blank)")
    df["report_hour"] = (t // 100).where(valid_t).astype("Int8")
    df["report_time"] = df["report_time"].where(valid_t.fillna(False))

    for c in ["report_seq_no", "vehicles_in_accident"]:
        df[c] = to_int(df[c], "Int16")
    for c in ["fatalities", "injuries"]:  # Int32 so state/year sums can't overflow
        df[c] = to_int(df[c], "Int32")
    for c in ["trafficway_id", "access_control_id", "road_surface_condition_id", "cargo_body_type_id",
              "gvw_rating_id", "weather_condition_id", "vehicle_configuration_id", "light_condition_id"]:
        df[c] = to_int(df[c], "Int16")
    # codes not defined in the data dictionary can't be labelled -> NA (so FKs to dim_* hold in SQL)
    for c, dim in CODE_DIMS.items():
        undefined = df[c].notna() & ~df[c].isin(list(LOOKUPS[dim]))
        if undefined.any():
            log(f"  {c}: {undefined.sum():,} rows with undefined codes "
                f"{sorted(df.loc[undefined, c].unique().tolist())[:10]} -> NA")
        df[c] = df[c].mask(undefined)
    for c, dim in TEXT_CODE_DIMS.items():
        df[c] = df[c].str.upper()
        undefined = df[c].notna() & ~df[c].isin(list(TEXT_LOOKUPS[dim]))
        if undefined.any():
            log(f"  {c}: {undefined.sum():,} rows with undefined codes "
                f"{sorted(df.loc[undefined, c].unique().tolist())[:10]} -> NA")
        df[c] = df[c].mask(undefined)
    for c in ["dot_number", "crash_carrier_id"]:
        df[c] = to_int(df[c], "Int64")
    df["dot_number"] = df["dot_number"].where(df["dot_number"] > 0)
    for c in ["vehicle_hazmat_placard", "hazmat_released", "tow_away", "federal_recordable", "state_recordable"]:
        df[c] = yn(df[c])
    df["no_id_flag"] = df["no_id_flag"].map({"1": True, "0": False}).astype("boolean")
    for c in ["add_date", "change_date", "upload_date", "transaction_date"]:
        df[c] = to_ts(df[c], "%Y%m%d %H%M")
    df["final_status_date"] = to_ts(df["final_status_date"], "%Y%m%d")

    # geography: county_code is the 3-digit FIPS county code (verified against MCMIS County Codes table)
    df["state"] = df["state"].str.upper()
    df["county_code"] = df["county_code"].str.zfill(3)
    state_fips = counties.drop_duplicates("STATE").set_index("STATE")["STATEFP"]
    df["state_fips"] = df["state"].map(state_fips).astype(STR)
    df["county_fips"] = (df["state_fips"] + df["county_code"]).astype(STR)
    known = df["county_fips"].isin(set(counties["STATEFP"] + counties["COUNTYFP"]))
    log(f"  county_fips not matching a 2020 Census county: {(~known).sum():,} "
        f"({(~known).mean():.1%}) -> kept, flagged by county_fips_valid")
    df["county_fips_valid"] = known

    df["city"] = df["city"].str.upper()
    df["crash_carrier_zip5"] = df["crash_carrier_zip_code"].str[:5]
    return df


#3. crash-level table
CRASH_COLS = ["report_number", "report_state", "report_date", "report_time", "report_hour", "state",
              "state_fips", "county_code", "county_fips", "county_fips_valid", "city", "location", "agency",
              "trafficway_id", "access_control_id", "road_surface_condition_id", "weather_condition_id",
              "light_condition_id", "vehicles_in_accident", "fatalities", "injuries", "tow_away",
              "federal_recordable", "state_recordable"]


def build_crash(df):
    log("\n[3] Crash-level table (1 row per crash)")
    # A report_number is the state's crash report id. Check it never spans two dates before using it as key.
    dates_per_report = df.groupby("report_number")["report_date"].nunique()
    multi = (dates_per_report > 1).sum()
    log(f"  report_numbers with >1 distinct report_date: {multi:,}")
    df["crash_key"] = (df["report_number"] + "_" + df["report_date"].dt.strftime("%Y%m%d")).astype(STR)

    # How consistent are 'crash-level' fields across the CMV rows of one crash?
    df["is_truck"] = (df["truck_bus_ind"] == "T").fillna(False).astype("int8")
    df["is_bus"] = (df["truck_bus_ind"] == "B").fillna(False).astype("int8")
    g = df.groupby("crash_key")
    for c in ["fatalities", "injuries", "vehicles_in_accident", "weather_condition_id", "county_code"]:
        n = (g[c].nunique() > 1).sum()
        log(f"  crashes whose {c:22s} differs between vehicle rows: {n:,}")

    # Take crash attributes from the lowest report_seq_no row (the first CMV); for counts use the max
    # reported across vehicle rows so a later correction on one row isn't lost.
    first = df.sort_values(["crash_key", "report_seq_no", "crash_id"]).drop_duplicates("crash_key")
    crash = first[["crash_key"] + CRASH_COLS].reset_index(drop=True)
    agg = g.agg(
        fatalities_max=("fatalities", "max"),
        injuries_max=("injuries", "max"),
        vehicles_in_accident_max=("vehicles_in_accident", "max"),
        cmv_count=("crash_id", "size"),
        truck_count=("is_truck", "sum"),
        bus_count=("is_bus", "sum"),
        any_hazmat_placard=("vehicle_hazmat_placard", "max"),
        any_hazmat_released=("hazmat_released", "max"),
        tow_away_any=("tow_away", "max"),
        carrier_count=("dot_number", "nunique"),
    ).reset_index()
    crash = crash.merge(agg, on="crash_key", how="left")
    crash["fatalities"] = crash["fatalities_max"]
    crash["injuries"] = crash["injuries_max"]
    crash["vehicles_in_accident"] = crash[["vehicles_in_accident_max", "cmv_count"]].max(axis=1).astype("Int16")
    crash["tow_away"] = crash["tow_away_any"]
    crash = crash.drop(columns=["fatalities_max", "injuries_max", "vehicles_in_accident_max", "tow_away_any"])

    crash["severity"] = pd.Series("Non-recordable", index=crash.index, dtype=STR)
    crash.loc[crash["tow_away"].fillna(False), "severity"] = "Tow-away"
    crash.loc[crash["injuries"] > 0, "severity"] = "Injury"
    crash.loc[crash["fatalities"] > 0, "severity"] = "Fatal"
    crash["is_fatal"] = crash["fatalities"] > 0
    crash["report_year"] = crash["report_date"].dt.year.astype("Int16")
    crash["report_month"] = crash["report_date"].dt.month.astype("Int8")
    crash["report_month_start"] = crash["report_date"].dt.to_period("M").dt.to_timestamp()
    crash["report_dow"] = crash["report_date"].dt.dayofweek.astype("Int8")  # 0 = Monday
    crash["report_state_mismatch"] = crash["report_state"] != crash["state"]
    log(f"  crashes: {len(crash):,}  (from {len(df):,} vehicle rows, "
        f"{(crash['cmv_count'] > 1).mean():.1%} involve 2+ CMVs)")
    log(f"  crash state != reporting state: {crash['report_state_mismatch'].sum():,}")
    log(f"  severity mix: {crash['severity'].value_counts(dropna=False).to_dict()}")
    return df, crash


#4. vehicle, carrier, event tables
def build_vehicle(df):
    cols = ["crash_id", "crash_key", "report_number", "report_seq_no", "dot_number", "truck_bus_ind",
            "vehicle_configuration_id", "cargo_body_type_id", "gvw_rating_id", "vehicle_hazmat_placard",
            "hazmat_released", "vehicle_lic_state", "ci_status_code", "final_status_date",
            "transaction_code", "add_date", "change_date", "upload_date"]
    v = df[cols].copy()
    v["has_dot_number"] = v["dot_number"].notna()
    return v


def build_carrier(df):
    cols = ["crash_id", "crash_key", "crash_carrier_id", "dot_number", "upload_dot_number",
            "upload_search_indicator", "crash_carrier_name", "crash_carrier_city", "crash_carrier_state",
            "crash_carrier_zip5", "docket_number", "crash_carrier_interstate", "no_id_flag", "state_number",
            "state_issuing_number"]
    c = df[cols].copy()
    c["crash_carrier_name"] = c["crash_carrier_name"].str.upper()
    return c


def build_event(df):
    """'2:3:NONCOLLISION:OVERTURN (ROLLOVER);1:1:NONCOLLISION:RAN OFF ROAD' -> one row per event."""
    s = df.set_index("crash_id")["crash_event_seq_id_desc"].dropna().astype(str).str.split(";").explode()
    s = s[s.str.strip() != ""]
    parts = s.str.split(":", n=2, expand=True)
    ev = pd.DataFrame({
        "crash_id": s.index.astype("int64"),
        "event_seq": pd.to_numeric(parts[0], errors="coerce").astype("Int16").values,
        "event_id": pd.to_numeric(parts[1], errors="coerce").astype("Int16").values,
        "event_desc_raw": parts[2].astype(STR).values,
    }).merge(df[["crash_id", "crash_key"]].astype({"crash_id": "int64"}), on="crash_id")
    ev = ev.drop_duplicates(["crash_id", "event_seq", "event_id"]).sort_values(["crash_id", "event_seq"])
    ev["is_first_event"] = ev.groupby("crash_id")["event_seq"].transform("min") == ev["event_seq"]
    log(f"  vehicle rows with no crash events recorded: {df['crash_event_seq_id_desc'].isna().sum():,}")
    return ev[["crash_id", "crash_key", "event_seq", "event_id", "is_first_event", "event_desc_raw"]]


# ---------------------------------------------------------------- 5. dashboard rollups
def build_aggs(crash, vehicle):
    v = vehicle.merge(crash[["crash_key", "state", "report_year", "report_month_start"]], on="crash_key")

    def roll(keys):
        a = crash.groupby(keys, dropna=False).agg(
            crashes=("crash_key", "size"),
            fatal_crashes=("is_fatal", "sum"),
            injury_crashes=("severity", lambda s: (s == "Injury").sum()),
            towaway_crashes=("severity", lambda s: (s == "Tow-away").sum()),
            fatalities=("fatalities", "sum"),
            injuries=("injuries", "sum"),
            hazmat_placard_crashes=("any_hazmat_placard", "sum"),
            hazmat_release_crashes=("any_hazmat_released", "sum"),
            bus_crashes=("bus_count", lambda s: (s > 0).sum()),
        )
        b = v.groupby(keys, dropna=False).agg(
            cmv_involved=("crash_id", "size"),
            carriers_involved=("dot_number", "nunique"),
            interstate_carrier_vehicles=("dot_number", "count"),
        )
        out = a.join(b).reset_index()
        out["fatalities_per_100_crashes"] = (100 * out["fatalities"] / out["crashes"]).round(2)
        return out.drop(columns="interstate_carrier_vehicles")

    return roll(["state", "report_year"]), roll(["state", "report_month_start"])


# ---------------------------------------------------------------- 6. dims
def build_dims(counties):
    dims = {name: pd.DataFrame({"code": list(m.keys()), "description": list(m.values())}).astype(
        {"code": "Int16", "description": STR}) for name, m in LOOKUPS.items()}
    dims.update({name: pd.DataFrame({"code": list(m.keys()), "description": list(m.values())}).astype(STR)
                 for name, m in TEXT_LOOKUPS.items()})
    st = counties.drop_duplicates("STATE")[["STATE", "STATEFP"]].rename(
        columns={"STATE": "state", "STATEFP": "state_fips"})
    st["state_name"] = st["state"].map(STATE_NAMES)
    st["is_50_states_dc"] = st["state_name"].notna()
    st["state_name"] = st["state_name"].fillna(st["state"])
    dims["dim_state"] = st.astype({"state": STR, "state_fips": STR, "state_name": STR})
    dims["dim_county"] = pd.DataFrame({
        "county_fips": counties["STATEFP"] + counties["COUNTYFP"],
        "state": counties["STATE"], "state_fips": counties["STATEFP"],
        "county_code": counties["COUNTYFP"], "county_name": counties["COUNTYNAME"],
    }).astype(STR)
    return dims


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    counties = load_counties()
    df = clean(load_raw(), counties)
    df, crash = build_crash(df)

    log("\n[4] Vehicle / carrier / event tables")
    vehicle = build_vehicle(df)
    log(f"  vehicle rows with no USDOT number: {(~vehicle['has_dot_number']).sum():,} "
        f"({(~vehicle['has_dot_number']).mean():.1%}) -> cannot join to carrier census")
    carrier = build_carrier(df)
    event = build_event(df)

    log("\n[5] Dashboard rollups")
    agg_year, agg_month = build_aggs(crash, vehicle)

    log("\n[6] Writing parquet")
    write(crash, "crash")
    write(vehicle, "crash_vehicle")
    write(carrier, "crash_carrier")
    write(event, "crash_event")
    write(agg_year, "agg_state_year")
    write(agg_month, "agg_state_month")
    for name, d in build_dims(counties).items():
        write(d, name)

    (OUT_DIR / "_build_report.txt").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
